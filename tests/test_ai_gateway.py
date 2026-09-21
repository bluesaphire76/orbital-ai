from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from backend.app.services.ai.config import AIConfig
from backend.app.services.ai.errors import (
    AIDisabledError,
    AIInvalidResponseError,
    AIProviderUnavailableError,
    AIQueueFullError,
    AITimeoutError,
)
from backend.app.services.ai.gateway import AIGateway
from backend.app.services.ai.llama_cpp import LlamaCppProvider
from backend.app.services.ai.models import (
    AITask,
    ChatMessage,
    ChatRole,
    GenerationRequest,
    JSONSchemaResponseFormat,
    ProviderHealthStatus,
)
from scripts.probe_ai_gateway import _validate_content


def _config(**overrides) -> AIConfig:
    values = {
        "ORBITAL_AI_ENABLED": "true",
        "ORBITAL_AI_API_KEY": "test-private-key",
        "ORBITAL_AI_MODEL": "test-model",
    }
    values.update(overrides)
    return AIConfig.from_env(values)


def _request(**overrides) -> GenerationRequest:
    values = {
        "task": AITask.FOUNDATION_PROBE,
        "messages": (ChatMessage(ChatRole.USER, "Return a probe result."),),
    }
    values.update(overrides)
    return GenerationRequest(**values)


def _provider(handler, **config_overrides) -> LlamaCppProvider:
    return LlamaCppProvider(
        _config(**config_overrides),
        transport=httpx.MockTransport(handler),
    )


def test_llama_health_ready():
    provider = _provider(lambda request: httpx.Response(200, json={"status": "ok"}))
    result = asyncio.run(provider.health())
    assert result.status is ProviderHealthStatus.READY
    assert result.latency_ms is not None


def test_llama_health_loading():
    provider = _provider(lambda request: httpx.Response(503, json={
        "error": {"code": 503, "message": "Loading model"},
    }))
    result = asyncio.run(provider.health())
    assert result.status is ProviderHealthStatus.LOADING


@pytest.mark.parametrize("error_type", (httpx.ReadTimeout, httpx.ConnectError))
def test_llama_health_transport_error_is_unavailable(error_type):
    def handler(request):
        raise error_type("sensitive upstream details", request=request)

    result = asyncio.run(_provider(handler).health())
    assert result.status is ProviderHealthStatus.UNAVAILABLE
    assert result.latency_ms is None


def test_llama_health_malformed_or_unexpected_response_is_unavailable():
    malformed = _provider(lambda request: httpx.Response(200, content=b"not-json"))
    unexpected = _provider(lambda request: httpx.Response(500, json={"status": "ok"}))
    assert asyncio.run(malformed.health()).status is ProviderHealthStatus.UNAVAILABLE
    assert asyncio.run(unexpected.health()).status is ProviderHealthStatus.UNAVAILABLE


def test_llama_chat_request_is_bounded_and_disables_reasoning():
    captured = {}

    def handler(request):
        captured["request"] = request
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
        })

    provider = _provider(handler)
    result = asyncio.run(provider.chat_completion(_request(max_output_tokens=999)))
    assert result.content == "ok"
    assert captured["request"].url.path == "/v1/chat/completions"
    assert captured["request"].headers["Authorization"] == "Bearer test-private-key"
    assert captured["payload"] == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Return a probe result."}],
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 512,
        "reasoning_effort": "none",
        "chat_template_kwargs": {"enable_thinking": False},
    }


def test_llama_chat_supports_json_schema_response_format():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}],
        })

    schema = JSONSchemaResponseFormat(
        name="probe",
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )
    asyncio.run(_provider(handler).chat_completion(_request(response_format=schema)))
    assert captured["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "probe",
            "strict": True,
            "schema": schema.schema,
        },
    }


def test_llama_chat_extracts_known_usage_and_timings_only():
    provider = _provider(lambda request: httpx.Response(200, json={
        "choices": [{
            "finish_reason": "stop",
            "message": {"content": "result", "reasoning_content": None},
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
            "unknown": "ignored",
        },
        "timings": {
            "prompt_ms": 12.5,
            "predicted_ms": 20,
            "prompt_per_second": 8.0,
            "predicted_per_second": 5.0,
            "secret_field": "ignored",
        },
        "unknown": "ignored",
    }))
    result = asyncio.run(provider.chat_completion(_request()))
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 4
    assert result.timings.prompt_ms == 12.5
    assert result.timings.predicted_per_second == 5.0
    assert result.finish_reason == "stop"
    assert result.reasoning_content is None
    assert result.provider_latency_ms is not None


@pytest.mark.parametrize(
    "payload",
    (
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": "  "}}]},
    ),
)
def test_llama_chat_rejects_invalid_or_empty_content(payload):
    provider = _provider(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(AIInvalidResponseError):
        asyncio.run(provider.chat_completion(_request()))


def test_llama_chat_rejects_malformed_json():
    provider = _provider(lambda request: httpx.Response(200, content=b"invalid"))
    with pytest.raises(AIInvalidResponseError):
        asyncio.run(provider.chat_completion(_request()))


def test_llama_chat_maps_timeout_and_connection_without_secret_leak():
    secret = "private-key-and-upstream-url"

    def timeout(request):
        raise httpx.ReadTimeout(secret, request=request)

    with pytest.raises(AITimeoutError) as timed_out:
        asyncio.run(_provider(timeout).chat_completion(_request()))
    assert secret not in str(timed_out.value)

    def unavailable(request):
        raise httpx.ConnectError(secret, request=request)

    with pytest.raises(AIProviderUnavailableError) as failed:
        asyncio.run(_provider(unavailable).chat_completion(_request()))
    assert secret not in str(failed.value)


def test_llama_chat_non_success_does_not_propagate_body_or_retry():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, text="secret upstream body")

    with pytest.raises(AIProviderUnavailableError) as raised:
        asyncio.run(_provider(handler).chat_completion(_request()))
    assert len(calls) == 1
    assert "secret" not in str(raised.value)


def test_foundation_probe_accepts_only_the_closed_bounded_schema():
    assert _validate_content(
        '{"status":"ok","summary":"Local AI is operational."}'
    ) == {
        "status": "ok",
        "summary": "Local AI is operational.",
    }


@pytest.mark.parametrize(
    "content",
    (
        "not-json",
        '{"status":"ok","summary":"valid","extra":true}',
        '{"status":"error","summary":"valid"}',
        '{"status":"ok","summary":""}',
        '{"status":"ok","summary":"<think>hidden</think>"}',
    ),
)
def test_foundation_probe_rejects_invalid_or_thinking_content(content):
    with pytest.raises(ValueError):
        _validate_content(content)


class ControlledProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def health(self):
        raise AssertionError("health is not part of generation queue tests")

    async def chat_completion(self, request):
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.entered.set()
        try:
            await self.release.wait()
            return __import__(
                "backend.app.services.ai.models", fromlist=["GenerationResult"]
            ).GenerationResult(content="ok")
        finally:
            self.active -= 1


def test_gateway_disabled_never_calls_provider():
    async def scenario():
        provider = ControlledProvider()
        gateway = AIGateway(_config(ORBITAL_AI_ENABLED="false"), provider)
        with pytest.raises(AIDisabledError):
            await gateway.generate(_request())
        assert provider.calls == 0
    asyncio.run(scenario())


def test_gateway_enforces_concurrency_and_bounded_waiting_queue():
    async def scenario():
        provider = ControlledProvider()
        gateway = AIGateway(
            _config(ORBITAL_AI_CONCURRENCY="1", ORBITAL_AI_MAX_QUEUE="1"),
            provider,
        )
        first = asyncio.create_task(gateway.generate(_request()))
        await provider.entered.wait()
        second = asyncio.create_task(gateway.generate(_request()))
        await asyncio.sleep(0)
        assert gateway.running == 1
        assert gateway.waiting == 1
        with pytest.raises(AIQueueFullError):
            await gateway.generate(_request())
        provider.release.set()
        assert (await first).content == "ok"
        assert (await second).content == "ok"
        assert provider.max_active == 1
        assert gateway.running == 0
        assert gateway.waiting == 0
    asyncio.run(scenario())


def test_gateway_timeout_releases_slot_and_counters():
    async def scenario():
        provider = ControlledProvider()
        gateway = AIGateway(
            _config(ORBITAL_AI_TIMEOUT_SECONDS="0.01"), provider
        )
        with pytest.raises(AITimeoutError):
            await gateway.generate(_request())
        assert gateway.running == 0
        assert gateway.waiting == 0
        provider.release.set()
        assert (await gateway.generate(_request())).content == "ok"
    asyncio.run(scenario())


def test_gateway_cancellation_releases_waiting_counter_and_slot():
    async def scenario():
        provider = ControlledProvider()
        gateway = AIGateway(
            _config(ORBITAL_AI_CONCURRENCY="1", ORBITAL_AI_MAX_QUEUE="1"),
            provider,
        )
        first = asyncio.create_task(gateway.generate(_request()))
        await provider.entered.wait()
        waiting = asyncio.create_task(gateway.generate(_request()))
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert gateway.waiting == 0
        provider.release.set()
        await first
        assert gateway.running == 0
        assert gateway.waiting == 0
    asyncio.run(scenario())


def test_gateway_health_bypasses_generation_queue():
    async def scenario():
        from backend.app.services.ai.models import ProviderHealth

        provider = ControlledProvider()
        provider.health = lambda: asyncio.sleep(
            0, result=ProviderHealth(ProviderHealthStatus.READY)
        )
        gateway = AIGateway(_config(), provider)
        active = asyncio.create_task(gateway.generate(_request()))
        await provider.entered.wait()
        assert (await gateway.health()).status is ProviderHealthStatus.READY
        assert gateway.waiting == 0
        provider.release.set()
        await active
    asyncio.run(scenario())

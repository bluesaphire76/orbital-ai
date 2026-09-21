from __future__ import annotations

import asyncio

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from backend.app.observability.ai_metrics import (
    AI_OUTCOMES,
    AI_TASKS,
    get_ai_metrics,
)
from backend.app.services.ai.config import AIConfig
from backend.app.services.ai.errors import (
    AIDisabledError,
    AIProviderUnavailableError,
    AIQueueFullError,
    AITimeoutError,
)
from backend.app.services.ai.gateway import AIGateway
from backend.app.services.ai.models import (
    AITask,
    ChatMessage,
    ChatRole,
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    ProviderHealthStatus,
    TokenUsage,
)


def _config(**overrides) -> AIConfig:
    values = {
        "ORBITAL_AI_ENABLED": "true",
        "ORBITAL_AI_MODEL": "metrics-model",
        "ORBITAL_AI_API_KEY": "metrics-private-key",
    }
    values.update(overrides)
    return AIConfig.from_env(values)


REQUEST = GenerationRequest(
    task=AITask.FOUNDATION_PROBE,
    messages=(ChatMessage(ChatRole.USER, "probe"),),
)


class Provider:
    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def health(self):
        return ProviderHealth(ProviderHealthStatus.READY)

    async def chat_completion(self, request):
        if self.mode == "error":
            raise AIProviderUnavailableError()
        if self.mode == "blocked":
            self.entered.set()
            await self.release.wait()
        if self.mode == "timeout":
            await asyncio.sleep(60)
        return GenerationResult(
            content="ok",
            usage=TokenUsage(prompt_tokens=7, completion_tokens=3),
        )


def _value(registry, name, labels=None):
    return registry.get_sample_value(name, labels or {})


def test_ai_metrics_register_idempotently_and_expose_all_families():
    registry = CollectorRegistry()
    first = get_ai_metrics(registry)
    assert get_ai_metrics(registry) is first
    output = generate_latest(registry).decode()
    for name in (
        "orbitalai_ai_runtime_ready",
        "orbitalai_ai_requests_total",
        "orbitalai_ai_request_duration_seconds",
        "orbitalai_ai_queue_depth",
        "orbitalai_ai_queue_capacity",
        "orbitalai_ai_active_requests",
        "orbitalai_ai_concurrency_capacity",
        "orbitalai_ai_timeouts_total",
        "orbitalai_ai_prompt_tokens_total",
        "orbitalai_ai_completion_tokens_total",
    ):
        assert name in output


def test_ai_metric_labels_are_fixed_and_contain_no_secrets():
    registry = CollectorRegistry()
    get_ai_metrics(registry)
    for family in registry.collect():
        for sample in family.samples:
            if "task" in sample.labels:
                assert sample.labels["task"] in AI_TASKS
            if "outcome" in sample.labels:
                assert sample.labels["outcome"] in AI_OUTCOMES
    output = generate_latest(registry).decode()
    assert "metrics-private-key" not in output
    assert "metrics-model" not in output


def test_gateway_records_success_tokens_error_timeout_and_disabled():
    async def scenario():
        registry = CollectorRegistry()
        metrics = get_ai_metrics(registry)

        await AIGateway(_config(), Provider(), metrics=metrics).generate(REQUEST)
        with pytest.raises(AIProviderUnavailableError):
            await AIGateway(
                _config(), Provider("error"), metrics=metrics
            ).generate(REQUEST)
        with pytest.raises(AITimeoutError):
            await AIGateway(
                _config(ORBITAL_AI_TIMEOUT_SECONDS="0.001"),
                Provider("timeout"),
                metrics=metrics,
            ).generate(REQUEST)
        with pytest.raises(AIDisabledError):
            await AIGateway(
                _config(ORBITAL_AI_ENABLED="false"),
                Provider(),
                metrics=metrics,
            ).generate(REQUEST)

        labels = {"task": "foundation_probe"}
        assert _value(registry, "orbitalai_ai_requests_total", labels | {"outcome": "success"}) == 1
        assert _value(registry, "orbitalai_ai_requests_total", labels | {"outcome": "error"}) == 1
        assert _value(registry, "orbitalai_ai_requests_total", labels | {"outcome": "timeout"}) == 1
        assert _value(registry, "orbitalai_ai_requests_total", labels | {"outcome": "disabled"}) == 1
        assert _value(registry, "orbitalai_ai_timeouts_total", labels) == 1
        assert _value(registry, "orbitalai_ai_prompt_tokens_total", labels) == 7
        assert _value(registry, "orbitalai_ai_completion_tokens_total", labels) == 3
        assert _value(registry, "orbitalai_ai_request_duration_seconds_count", labels) == 3
    asyncio.run(scenario())


def test_gateway_records_queue_full_and_depth_returns_to_zero():
    async def scenario():
        registry = CollectorRegistry()
        metrics = get_ai_metrics(registry)
        provider = Provider("blocked")
        gateway = AIGateway(
            _config(ORBITAL_AI_MAX_QUEUE="1"), provider, metrics=metrics
        )
        first = asyncio.create_task(gateway.generate(REQUEST))
        await provider.entered.wait()
        second = asyncio.create_task(gateway.generate(REQUEST))
        await asyncio.sleep(0)
        assert _value(registry, "orbitalai_ai_queue_depth") == 1
        assert _value(registry, "orbitalai_ai_active_requests") == 1
        assert _value(registry, "orbitalai_ai_concurrency_capacity") == 1
        with pytest.raises(AIQueueFullError):
            await gateway.generate(REQUEST)
        provider.release.set()
        await first
        await second
        assert _value(registry, "orbitalai_ai_queue_depth") == 0
        assert _value(registry, "orbitalai_ai_active_requests") == 0
        assert _value(registry, "orbitalai_ai_queue_capacity") == 1
        assert _value(
            registry,
            "orbitalai_ai_requests_total",
            {"task": "foundation_probe", "outcome": "queue_full"},
        ) == 1
    asyncio.run(scenario())


def test_health_updates_runtime_ready_without_using_generation_queue():
    async def scenario():
        registry = CollectorRegistry()
        metrics = get_ai_metrics(registry)
        gateway = AIGateway(_config(), Provider(), metrics=metrics)
        await gateway.health()
        assert _value(registry, "orbitalai_ai_runtime_ready") == 1
        assert _value(registry, "orbitalai_ai_queue_depth") == 0
    asyncio.run(scenario())

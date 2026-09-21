from __future__ import annotations

from time import perf_counter
from typing import Mapping

import httpx

from backend.app.services.ai.config import AIConfig
from backend.app.services.ai.errors import (
    AIInvalidResponseError,
    AIProviderUnavailableError,
    AITimeoutError,
)
from backend.app.services.ai.models import (
    GenerationRequest,
    GenerationResult,
    GenerationTimings,
    ProviderHealth,
    ProviderHealthStatus,
    TokenUsage,
)


class LlamaCppProvider:
    def __init__(
        self,
        config: AIConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._config.base_url,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(
                self._config.timeout_seconds,
                connect=self._config.connect_timeout_seconds,
            ),
            transport=self._transport,
        )

    async def health(self) -> ProviderHealth:
        started = perf_counter()
        try:
            async with self._client() as client:
                response = await client.get("/health")
        except (httpx.TimeoutException, httpx.NetworkError):
            return ProviderHealth(status=ProviderHealthStatus.UNAVAILABLE)

        latency_ms = (perf_counter() - started) * 1000
        try:
            payload = response.json()
        except ValueError:
            return ProviderHealth(status=ProviderHealthStatus.UNAVAILABLE)

        if (
            response.status_code == 200
            and isinstance(payload, dict)
            and payload.get("status") == "ok"
        ):
            return ProviderHealth(
                status=ProviderHealthStatus.READY,
                latency_ms=latency_ms,
            )

        if response.status_code == 503 and _is_loading_response(payload):
            return ProviderHealth(
                status=ProviderHealthStatus.LOADING,
                latency_ms=latency_ms,
            )

        return ProviderHealth(status=ProviderHealthStatus.UNAVAILABLE)

    async def chat_completion(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        max_tokens = min(
            request.max_output_tokens or self._config.max_output_tokens,
            self._config.max_output_tokens,
        )
        payload: dict[str, object] = {
            "model": self._config.model,
            "messages": [
                {
                    "role": message.role.value,
                    "content": message.content,
                }
                for message in request.messages
            ],
            "stream": False,
            "temperature": self._config.temperature,
            "max_tokens": max_tokens,
            "reasoning_effort": "none",
            "chat_template_kwargs": {
                "enable_thinking": False,
            },
        }
        if request.response_format is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.response_format.name,
                    "strict": request.response_format.strict,
                    "schema": dict(request.response_format.schema),
                },
            }

        started = perf_counter()
        try:
            async with self._client() as client:
                response = await client.post(
                    "/v1/chat/completions",
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise AITimeoutError() from exc
        except httpx.NetworkError as exc:
            raise AIProviderUnavailableError() from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise AIProviderUnavailableError()

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise AIInvalidResponseError() from exc
        return _parse_chat_response(
            response_payload,
            provider_latency_ms=(perf_counter() - started) * 1000,
        )


def _is_loading_response(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    error = payload.get("error")
    return (
        isinstance(error, dict)
        and error.get("message") == "Loading model"
    )


def _known_non_negative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _known_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _parse_usage(payload: object) -> TokenUsage | None:
    if not isinstance(payload, Mapping):
        return None
    usage = TokenUsage(
        prompt_tokens=_known_non_negative_int(payload.get("prompt_tokens")),
        completion_tokens=_known_non_negative_int(
            payload.get("completion_tokens")
        ),
        total_tokens=_known_non_negative_int(payload.get("total_tokens")),
    )
    if all(value is None for value in (
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.total_tokens,
    )):
        return None
    return usage


def _parse_timings(payload: object) -> GenerationTimings | None:
    if not isinstance(payload, Mapping):
        return None
    timings = GenerationTimings(
        prompt_ms=_known_number(payload.get("prompt_ms")),
        predicted_ms=_known_number(payload.get("predicted_ms")),
        prompt_per_second=_known_number(payload.get("prompt_per_second")),
        predicted_per_second=_known_number(payload.get("predicted_per_second")),
    )
    if all(value is None for value in (
        timings.prompt_ms,
        timings.predicted_ms,
        timings.prompt_per_second,
        timings.predicted_per_second,
    )):
        return None
    return timings


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _parse_chat_response(
    payload: object,
    *,
    provider_latency_ms: float | None = None,
) -> GenerationResult:
    if not isinstance(payload, dict):
        raise AIInvalidResponseError()
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIInvalidResponseError()
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise AIInvalidResponseError()
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise AIInvalidResponseError()
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AIInvalidResponseError()
    return GenerationResult(
        content=content,
        usage=_parse_usage(payload.get("usage")),
        timings=_parse_timings(payload.get("timings")),
        finish_reason=_optional_string(first_choice.get("finish_reason")),
        reasoning_content=_optional_string(message.get("reasoning_content")),
        provider_latency_ms=provider_latency_ms,
    )

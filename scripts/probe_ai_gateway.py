from __future__ import annotations

import asyncio
import json
import sys
from time import perf_counter

from prometheus_client import CollectorRegistry

from backend.app.observability.ai_metrics import AIMetrics
from backend.app.services.ai.config import AIConfig
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


PROBE_PROMPT = (
    "Return the required JSON object confirming that the OrbitalAI local AI "
    "foundation is operational. Do not perform orbital calculations."
)
PROBE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "summary"],
    "properties": {
        "status": {"type": "string", "enum": ["ok"]},
        "summary": {
            "type": "string",
            "minLength": 1,
            "maxLength": 300,
        },
    },
}


def _metric(
    registry: CollectorRegistry,
    name: str,
    labels: dict[str, str] | None = None,
) -> float:
    value = registry.get_sample_value(name, labels or {})
    return float(value) if value is not None else 0.0


def _metric_snapshot(registry: CollectorRegistry) -> dict[str, float]:
    task = {"task": AITask.FOUNDATION_PROBE.value}
    return {
        "runtime_ready": _metric(registry, "orbitalai_ai_runtime_ready"),
        "requests_success": _metric(
            registry,
            "orbitalai_ai_requests_total",
            task | {"outcome": "success"},
        ),
        "requests_error": _metric(
            registry,
            "orbitalai_ai_requests_total",
            task | {"outcome": "error"},
        ),
        "duration_count": _metric(
            registry,
            "orbitalai_ai_request_duration_seconds_count",
            task,
        ),
        "duration_sum_seconds": _metric(
            registry,
            "orbitalai_ai_request_duration_seconds_sum",
            task,
        ),
        "prompt_tokens": _metric(
            registry,
            "orbitalai_ai_prompt_tokens_total",
            task,
        ),
        "completion_tokens": _metric(
            registry,
            "orbitalai_ai_completion_tokens_total",
            task,
        ),
        "queue_depth": _metric(registry, "orbitalai_ai_queue_depth"),
        "queue_capacity": _metric(registry, "orbitalai_ai_queue_capacity"),
        "active_requests": _metric(
            registry,
            "orbitalai_ai_active_requests",
        ),
        "concurrency_capacity": _metric(
            registry,
            "orbitalai_ai_concurrency_capacity",
        ),
    }


def _validate_content(content: str) -> dict[str, str]:
    if "<think>" in content.lower() or "</think>" in content.lower():
        raise ValueError("probe response contains thinking tags")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("probe response is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"status", "summary"}:
        raise ValueError("probe response does not match the closed schema")
    if payload.get("status") != "ok":
        raise ValueError("probe status is not ok")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not 1 <= len(summary) <= 300:
        raise ValueError("probe summary is outside its bounds")
    return {"status": "ok", "summary": summary}


async def _run() -> dict[str, object]:
    config = AIConfig.from_env()
    if not config.enabled:
        raise RuntimeError("local AI is disabled")

    registry = CollectorRegistry()
    metrics = AIMetrics(registry)
    gateway = AIGateway(config, LlamaCppProvider(config), metrics=metrics)
    health = await gateway.health()
    if health.status is not ProviderHealthStatus.READY:
        raise RuntimeError("local AI provider is not ready")
    before = _metric_snapshot(registry)

    request = GenerationRequest(
        task=AITask.FOUNDATION_PROBE,
        messages=(
            ChatMessage(
                ChatRole.SYSTEM,
                "Return only the JSON object required by the supplied schema.",
            ),
            ChatMessage(ChatRole.USER, PROBE_PROMPT),
        ),
        max_output_tokens=256,
        response_format=JSONSchemaResponseFormat(
            name="orbitalai_foundation_probe",
            schema=PROBE_SCHEMA,
        ),
    )

    started = perf_counter()
    pending = asyncio.create_task(gateway.generate(request))
    during = _metric_snapshot(registry)
    for _ in range(100):
        if during["active_requests"] == 1 or pending.done():
            break
        await asyncio.sleep(0.01)
        during = _metric_snapshot(registry)
    result = await pending
    gateway_latency_ms = (perf_counter() - started) * 1000

    content = _validate_content(result.content)
    if result.reasoning_content:
        raise ValueError("probe response contains reasoning content")
    if result.finish_reason != "stop":
        raise ValueError("probe response did not finish with stop")
    if gateway.running != 0 or gateway.waiting != 0:
        raise RuntimeError("gateway execution state was not released")

    after = _metric_snapshot(registry)
    if during["active_requests"] != 1:
        raise RuntimeError("active-request metric did not observe the probe")
    if after["active_requests"] != 0 or after["queue_depth"] != 0:
        raise RuntimeError("gateway metrics did not return to idle")

    usage = result.usage
    timings = result.timings
    return {
        "status": "pass",
        "response": content,
        "finish_reason": result.finish_reason,
        "reasoning_content": None,
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else None,
            "completion_tokens": usage.completion_tokens if usage else None,
            "total_tokens": usage.total_tokens if usage else None,
        },
        "timings": {
            "gateway_latency_ms": gateway_latency_ms,
            "provider_latency_ms": result.provider_latency_ms,
            "prompt_ms": timings.prompt_ms if timings else None,
            "predicted_ms": timings.predicted_ms if timings else None,
            "prompt_tokens_per_second": (
                timings.prompt_per_second if timings else None
            ),
            "generation_tokens_per_second": (
                timings.predicted_per_second if timings else None
            ),
        },
        "gateway_state": {
            "running": gateway.running,
            "waiting": gateway.waiting,
        },
        "metrics": {
            "before": before,
            "during": during,
            "after": after,
        },
    }


def main() -> int:
    try:
        result = asyncio.run(_run())
    except Exception as exc:
        print(f"AI gateway foundation probe: FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

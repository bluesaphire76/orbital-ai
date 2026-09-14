from __future__ import annotations

from prometheus_client import Gauge, REGISTRY

from backend.app.observability.propagation_metrics import (
    PropagationMetricsCollector,
)


PLATFORM_INFO = Gauge(
    "orbitalai_platform_info",
    "OrbitalAI platform information",
    ["service"],
)

_initialized = False


def initialize_metrics() -> None:
    global _initialized

    if _initialized:
        return

    PLATFORM_INFO.labels(
        service="api",
    ).set(1)

    REGISTRY.register(
        PropagationMetricsCollector()
    )

    _initialized = True

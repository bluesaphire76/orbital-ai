from __future__ import annotations

from prometheus_client import (
    Gauge,
    REGISTRY,
)

from backend.app.observability.conjunction_metrics import (
    ConjunctionMetricsCollector,
)
from backend.app.observability.propagation_metrics import (
    PropagationMetricsCollector,
)
from backend.app.observability.catalog_metrics import CatalogMetricsCollector
from backend.app.observability.catalog_sync_metrics import (
    CatalogSyncMetricsCollector,
)
from backend.app.observability.operations import OperationsMetricsCollector


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
        service="api"
    ).set(1)

    REGISTRY.register(
        PropagationMetricsCollector()
    )

    REGISTRY.register(
        ConjunctionMetricsCollector()
    )

    REGISTRY.register(CatalogMetricsCollector())
    REGISTRY.register(OperationsMetricsCollector())
    REGISTRY.register(CatalogSyncMetricsCollector())

    _initialized = True

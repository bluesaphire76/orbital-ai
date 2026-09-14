from prometheus_client import Gauge


PLATFORM_INFO = Gauge(
    "orbitalai_platform_info",
    "OrbitalAI platform information",
    ["service"],
)


def initialize_metrics() -> None:
    PLATFORM_INFO.labels(service="api").set(1)

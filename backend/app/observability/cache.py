"""Small, independently refreshed snapshots; no catalog work on every scrape."""

from threading import Lock
from time import monotonic, time

from prometheus_client.core import GaugeMetricFamily


def gauge(name, description, value):
    metric = GaugeMetricFamily(name, description)
    metric.add_metric([], value)
    return metric


class CachedCollector:
    refresh_seconds = 60.0

    def __init__(self, component, loader, *, clock=monotonic, wall_clock=time):
        self.component = component
        self.loader = loader
        self.clock = clock
        self.wall_clock = wall_clock
        self._lock = Lock()
        self._next_refresh = float("-inf")
        self._last_success = 0.0
        self._available = 0
        self._snapshot = ()

    def describe(self):
        # Registration must not query the database or filesystem.
        return []

    def collect(self):
        with self._lock:
            if self.clock() >= self._next_refresh:
                try:
                    snapshot = tuple(self.loader())
                except Exception:
                    # Keep the last complete snapshot; never emit exception text
                    # (DB/provider errors can contain credentials or payloads).
                    self._available = 0
                else:
                    self._snapshot = snapshot
                    self._available = 1
                    self._last_success = self.wall_clock()
                self._next_refresh = self.clock() + self.refresh_seconds
            snapshot = self._snapshot
            available, last_success = self._available, self._last_success

        yield gauge(f"orbitalai_{self.component}_metrics_available",
                    "Whether the latest metrics refresh succeeded", available)
        yield gauge(f"orbitalai_{self.component}_metrics_last_refresh_timestamp_seconds",
                    "Last successful snapshot refresh; zero means never refreshed", last_success)
        yield from snapshot

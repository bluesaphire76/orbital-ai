"""Bounded operational state shared by one-shot workers and the API on one host.

Only counters, timestamps, durations and fixed record categories are written.
Metrics failures must not change the observed operation's result or exception.
"""

from contextvars import ContextVar
from functools import wraps
import fcntl
import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter, time

from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily

from backend.app.observability.cache import CachedCollector


PROVIDERS = ("satcat", "celestrak", "space-track")
SOURCES = ("canonical", "celestrak", "space-track", "other")
RECORD_RESULTS = ("received", "matched", "imported", "unmatched")
DURATION_BUCKETS = (1, 5, 15, 30, 60, 120, 300, 600, 1800, 3600, float("inf"))
_active_ingestion = ContextVar("orbitalai_ingestion_observation", default=None)
_logger = logging.getLogger(__name__)


class OperationStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "operations.json"

    def read(self):
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {}

    def update(self, kind, label, *, started=None, success=None, duration=None, records=None):
        allowed = SOURCES if kind == "conjunction" else PROVIDERS if kind == "ingestion" else ()
        if label not in allowed:
            raise ValueError("Unsupported operational metric label")
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "operations.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = self.read()
            row = data.setdefault(kind, {}).setdefault(label, {})
            if started is not None:
                row["last_attempt"] = max(started, row.get("last_attempt", 0))
            if success is not None:
                row["runs"] = row.get("runs", 0) + 1
                row["failures"] = row.get("failures", 0) + int(not success)
                row["success"] = int(success)
                row["duration"] = duration
                if success:
                    row["last_success"] = time()
                    row["records"] = {key: int(records.get(key, 0)) for key in RECORD_RESULTS} if records else {}
                    row["duration_sum"] = row.get("duration_sum", 0) + duration
                    buckets = row.setdefault("duration_buckets", [0] * len(DURATION_BUCKETS))
                    for index, upper in enumerate(DURATION_BUCKETS):
                        buckets[index] += int(duration <= upper)
            temporary = None
            try:
                with NamedTemporaryFile(mode="w", dir=self.directory, delete=False) as output:
                    temporary = Path(output.name)
                    json.dump(data, output, allow_nan=False)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


def get_operation_store():
    # The existing Compose /app/data bind mount is shared by API and workers.
    return OperationStore(os.getenv("ORBITAL_METRICS_DIR", "data/observability"))


def _record(kind, label, **values):
    try:
        get_operation_store().update(kind, label, **values)
    except Exception:
        _logger.warning("Operational metrics update failed")


def observe_screening(function):
    @wraps(function)
    def observed(*args, **kwargs):
        source = kwargs.get("source", "celestrak")
        label = source if source in SOURCES else "other"
        _record("conjunction", label, started=time())
        timer = perf_counter()
        try:
            result = function(*args, **kwargs)
        except Exception:
            _record("conjunction", label, success=False, duration=perf_counter() - timer)
            raise
        _record("conjunction", label, success=True, duration=result.duration_ms / 1000)
        return result
    return observed


def _ingestion_records(provider, result, args, kwargs):
    received = kwargs.get("records", args[1] if len(args) > 1 else None)
    return {
        "received": len(received) if hasattr(received, "__len__") else result.records,
        "matched": (result.matched_objects if provider == "space-track" else
                    result.created + result.updated if provider == "satcat" else
                    result.objects_created + result.objects_updated),
        "imported": result.created if provider == "satcat" else result.elements_created,
        "unmatched": result.unmatched_objects if provider == "space-track" else 0,
    }


def observe_ingestion(provider):
    if provider not in PROVIDERS:
        raise ValueError("Unsupported ingestion provider")

    def decorate(function):
        @wraps(function)
        def observed(*args, **kwargs):
            active = _active_ingestion.get()
            owns_observation = active is None or active[0] != provider
            records = {} if owns_observation else active[1]
            token = _active_ingestion.set((provider, records))
            if owns_observation:
                _record("ingestion", provider, started=time())
            timer = perf_counter()
            try:
                result = function(*args, **kwargs)
                try:
                    if hasattr(result, "records"):
                        records.update(_ingestion_records(provider, result, args, kwargs))
                except Exception:
                    _logger.warning("Ingestion record metrics unavailable")
            except Exception:
                if owns_observation:
                    _record("ingestion", provider, success=False, duration=perf_counter() - timer)
                raise
            else:
                if owns_observation:
                    _record("ingestion", provider, success=True,
                            duration=perf_counter() - timer, records=records)
                return result
            finally:
                _active_ingestion.reset(token)
        return observed
    return decorate


class OperationsMetricsCollector(CachedCollector):
    def __init__(self, store=None):
        self.store = store
        super().__init__("operations", self.load)

    def load(self):
        data = (self.store or get_operation_store()).read()
        for kind, labels, label_name in (("conjunction", SOURCES, "source"), ("ingestion", PROVIDERS, "provider")):
            prefix = f"orbitalai_{kind}"
            definitions = (
                ("last_attempt_timestamp_seconds", "last_attempt", "Last attempted execution; zero means unobserved", 0),
                ("last_success_timestamp_seconds", "last_success", "Last successful execution; zero means unobserved", 0),
                ("last_execution_success", "success", "Last execution outcome; NaN means unobserved", float("nan")),
                ("last_execution_duration_seconds", "duration", "Latest execution duration (screening time on conjunction success)", float("nan")),
            )
            for suffix, field, help_text, default in definitions:
                metric = GaugeMetricFamily(f"{prefix}_{suffix}", help_text, labels=[label_name])
                for label in labels:
                    metric.add_metric([label], data.get(kind, {}).get(label, {}).get(field, default))
                yield metric
            for suffix, field in (("runs", "runs"), ("failures", "failures")):
                metric = CounterMetricFamily(f"{prefix}_{suffix}", "Finished executions since instrumentation enabled", labels=[label_name])
                for label in labels:
                    metric.add_metric([label], data.get(kind, {}).get(label, {}).get(field, 0))
                yield metric

        histogram = HistogramMetricFamily(
            "orbitalai_conjunction_screening_duration_seconds",
            "Screening duration of successful runs since instrumentation enabled; excludes persistence",
            labels=["source"],
        )
        for source in SOURCES:
            row = data.get("conjunction", {}).get(source, {})
            counts = row.get("duration_buckets", [0] * len(DURATION_BUCKETS))
            histogram.add_metric([source], [("+Inf" if bound == float("inf") else str(bound), count)
                                           for bound, count in zip(DURATION_BUCKETS, counts)], row.get("duration_sum", 0))
        yield histogram

        records = GaugeMetricFamily("orbitalai_ingestion_records", "Record counts from the last successful sync", labels=["provider", "result"])
        for provider in PROVIDERS:
            for result in RECORD_RESULTS:
                records.add_metric([provider, result], data.get("ingestion", {}).get(provider, {}).get("records", {}).get(result, float("nan")))
        yield records

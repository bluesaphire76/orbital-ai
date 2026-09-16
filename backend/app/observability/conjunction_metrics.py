from datetime import datetime, timezone

from sqlalchemy import select

from backend.app.db.models.conjunction import ConjunctionRun
from backend.app.db.session import get_session_factory
from backend.app.observability.cache import CachedCollector, gauge


# Preserve established names and the unlabeled latest-run contract, including
# duration_ms for compatibility; new dashboards use the standard seconds unit.
RUN_FIELDS = {
    "objects": "Objects screened", "samples": "Global grid samples",
    "chunk_count": "Chunks processed", "chunk_seconds": "Configured chunk width in seconds",
    "propagation_attempts": "Grid propagation attempts",
    "propagation_failures": "Grid propagation failures", "expired_skips": "Expired grid states skipped",
    "raw_candidates": "Raw candidate detections, including chunk overlap",
    "unique_candidates": "Sum of chunk-unique candidate pair evaluations",
    "refinement_attempts": "Numerical refinement attempts",
    "refinement_failures": "Numerical refinement failures",
    "duplicate_events_suppressed": "Final events merged within continuous encounter episodes",
    "suppressed_shared_pairs": "Sum of distinct suppressed shared-orbit pairs per chunk",
    "max_chunk_raw_candidates": "Largest raw candidate count in one chunk",
    "max_chunk_unique_candidates": "Largest retained candidate count in one chunk",
    "max_chunk_refinement_attempts": "Largest refinement count in one chunk",
    "duration_ms": "Screening duration in milliseconds (legacy metric)",
}


def run_metrics(run, now=None):
    prefix = "orbitalai_conjunction_last_run_"
    for field, description in RUN_FIELDS.items():
        yield gauge(prefix + field, description, getattr(run, field))
    yield gauge(prefix + "events", "Final conjunction encounter events", run.event_count)
    yield gauge(prefix + "duration_seconds", "Screening duration excluding persistence", run.duration_ms / 1000)
    completed = run.completed_at
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=timezone.utc)
    yield gauge(prefix + "completed_timestamp_seconds", "Latest completed screening timestamp", completed.timestamp())
    yield gauge(prefix + "age_seconds", "Latest run age at snapshot refresh",
                max(0, ((now or datetime.now(timezone.utc)) - completed).total_seconds()))


class ConjunctionMetricsCollector(CachedCollector):
    def __init__(self, session_factory=None):
        self.session_factory = session_factory
        super().__init__("conjunction", self.load)

    def load(self):
        with (self.session_factory or get_session_factory())() as session:
            run = session.scalar(select(ConjunctionRun).order_by(ConjunctionRun.id.desc()).limit(1))
            return tuple(run_metrics(run)) if run is not None else ()

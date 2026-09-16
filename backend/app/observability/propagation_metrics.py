from datetime import datetime, timezone

from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import func, select

from backend.app.db.models.propagation import PropagatedState, PropagationRun
from backend.app.db.session import get_session_factory
from backend.app.observability.cache import CachedCollector, gauge


class PropagationMetricsCollector(CachedCollector):
    def __init__(self, session_factory=None):
        self.session_factory = session_factory
        super().__init__("propagation", self.load)

    def load(self):
        with (self.session_factory or get_session_factory())() as session:
            run = session.scalar(select(PropagationRun).order_by(PropagationRun.id.desc()).limit(1))
            if run is None:
                return
            for suffix, field in (("objects", "total_objects"), ("successful", "successful"),
                                  ("failed", "failed"), ("duration_ms", "duration_ms")):
                yield gauge("orbitalai_propagation_last_run_" + suffix,
                            "Latest propagation run " + suffix, getattr(run, field) or 0)
            target = run.target_time
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            yield gauge("orbitalai_propagation_last_run_age_seconds",
                        "Latest propagation target age at snapshot refresh",
                        max(0, (datetime.now(timezone.utc) - target).total_seconds()))
            counts = dict(session.execute(
                select(PropagatedState.ephemeris_status, func.count())
                .where(PropagatedState.run_id == run.id)
                .group_by(PropagatedState.ephemeris_status)
            ).all())
            quality = GaugeMetricFamily(
                "orbitalai_propagation_ephemeris_objects",
                "Objects by ephemeris quality in the latest propagation run", labels=["status"],
            )
            for status in ("fresh", "aging", "stale", "expired"):
                quality.add_metric([status], counts.get(status, 0))
            yield quality

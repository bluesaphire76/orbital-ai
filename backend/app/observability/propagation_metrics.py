from __future__ import annotations

from datetime import datetime, timezone

from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import func, select

from backend.app.db.models.propagation import (
    PropagatedState,
    PropagationRun,
)
from backend.app.db.session import get_session_factory


class PropagationMetricsCollector:
    def collect(self):
        available = GaugeMetricFamily(
            "orbitalai_propagation_metrics_available",
            "Whether propagation metrics could be read",
        )

        try:
            session_factory = get_session_factory()

            with session_factory() as session:
                latest_run = session.scalar(
                    select(PropagationRun)
                    .order_by(PropagationRun.id.desc())
                    .limit(1)
                )

                available.add_metric([], 1)

                if latest_run is None:
                    yield available
                    return

                total = GaugeMetricFamily(
                    "orbitalai_propagation_last_run_objects",
                    "Objects processed in the latest propagation run",
                )
                total.add_metric(
                    [],
                    latest_run.total_objects,
                )

                successful = GaugeMetricFamily(
                    "orbitalai_propagation_last_run_successful",
                    "Successful propagations in the latest run",
                )
                successful.add_metric(
                    [],
                    latest_run.successful,
                )

                failed = GaugeMetricFamily(
                    "orbitalai_propagation_last_run_failed",
                    "Failed propagations in the latest run",
                )
                failed.add_metric(
                    [],
                    latest_run.failed,
                )

                duration = GaugeMetricFamily(
                    "orbitalai_propagation_last_run_duration_ms",
                    "Duration of the latest propagation run",
                )
                duration.add_metric(
                    [],
                    latest_run.duration_ms or 0.0,
                )

                run_age = GaugeMetricFamily(
                    "orbitalai_propagation_last_run_age_seconds",
                    "Age of the latest propagation run target time",
                )

                target_time = latest_run.target_time

                if target_time.tzinfo is None:
                    target_time = target_time.replace(
                        tzinfo=timezone.utc
                    )

                age_seconds = max(
                    0.0,
                    (
                        datetime.now(timezone.utc)
                        - target_time
                    ).total_seconds(),
                )

                run_age.add_metric(
                    [],
                    age_seconds,
                )

                ephemeris_quality = GaugeMetricFamily(
                    "orbitalai_propagation_ephemeris_objects",
                    "Objects by ephemeris quality in the latest run",
                    labels=["status"],
                )

                rows = session.execute(
                    select(
                        PropagatedState.ephemeris_status,
                        func.count(
                            PropagatedState.id
                        ),
                    )
                    .where(
                        PropagatedState.run_id
                        == latest_run.id
                    )
                    .group_by(
                        PropagatedState.ephemeris_status
                    )
                )

                counts = {
                    status: count
                    for status, count in rows
                    if status is not None
                }

                for status in (
                    "fresh",
                    "aging",
                    "stale",
                    "expired",
                ):
                    ephemeris_quality.add_metric(
                        [status],
                        counts.get(status, 0),
                    )

                yield available
                yield total
                yield successful
                yield failed
                yield duration
                yield run_age
                yield ephemeris_quality

        except Exception:
            available.add_metric([], 0)
            yield available

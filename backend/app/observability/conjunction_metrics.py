from __future__ import annotations

from datetime import datetime, timezone

from prometheus_client.core import (
    GaugeMetricFamily,
)
from sqlalchemy import select

from backend.app.db.models.conjunction import (
    ConjunctionRun,
)
from backend.app.db.session import (
    get_session_factory,
)


class ConjunctionMetricsCollector:
    def collect(self):
        available = GaugeMetricFamily(
            "orbitalai_conjunction_metrics_available",
            "Whether conjunction metrics could be read",
        )

        try:
            session_factory = (
                get_session_factory()
            )

            with session_factory() as session:
                run = session.scalar(
                    select(ConjunctionRun)
                    .order_by(
                        ConjunctionRun.id.desc()
                    )
                    .limit(1)
                )

                available.add_metric(
                    [],
                    1,
                )

                yield available

                if run is None:
                    return

                metrics = (
                    (
                        "orbitalai_conjunction_last_run_objects",
                        "Objects screened",
                        run.objects,
                    ),
                    (
                        "orbitalai_conjunction_last_run_raw_candidates",
                        "Raw candidate detections",
                        run.raw_candidates,
                    ),
                    (
                        "orbitalai_conjunction_last_run_unique_candidates",
                        "Unique candidate pairs",
                        run.unique_candidates,
                    ),
                    (
                        "orbitalai_conjunction_last_run_refinement_attempts",
                        "Numerical refinement attempts",
                        run.refinement_attempts,
                    ),
                    (
                        "orbitalai_conjunction_last_run_refinement_failures",
                        "Numerical refinement failures",
                        run.refinement_failures,
                    ),
                    (
                        "orbitalai_conjunction_last_run_events",
                        "Refined conjunction events",
                        run.event_count,
                    ),
                    (
                        "orbitalai_conjunction_last_run_suppressed_shared_pairs",
                        "Suppressed shared-orbit pairs",
                        run.suppressed_shared_pairs,
                    ),
                    (
                        "orbitalai_conjunction_last_run_duration_ms",
                        "Conjunction screening duration",
                        run.duration_ms,
                    ),
                )

                for (
                    name,
                    description,
                    value,
                ) in metrics:
                    metric = (
                        GaugeMetricFamily(
                            name,
                            description,
                        )
                    )

                    metric.add_metric(
                        [],
                        value,
                    )

                    yield metric

                run_age = GaugeMetricFamily(
                    "orbitalai_conjunction_last_run_age_seconds",
                    "Age of latest completed conjunction run",
                )

                completed_at = (
                    run.completed_at
                )

                if (
                    completed_at.tzinfo
                    is None
                ):
                    completed_at = (
                        completed_at.replace(
                            tzinfo=timezone.utc
                        )
                    )

                age_seconds = max(
                    0.0,
                    (
                        datetime.now(
                            timezone.utc
                        )
                        - completed_at
                    ).total_seconds(),
                )

                run_age.add_metric(
                    [],
                    age_seconds,
                )

                yield run_age

        except Exception:
            available.add_metric(
                [],
                0,
            )

            yield available

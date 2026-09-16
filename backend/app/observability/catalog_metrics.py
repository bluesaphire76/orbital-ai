"""SQL aggregates of catalog coverage, refreshed at most once per minute."""

from datetime import datetime, timedelta, timezone

from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import case, func, select

from backend.app.core.config import get_settings
from backend.app.db.models.orbital_element import OrbitalElement
from backend.app.db.models.orbital_object import OrbitalObject
from backend.app.db.session import get_session_factory
from backend.app.observability.cache import CachedCollector, gauge


def catalog_metrics(session, settings, now):
    total, earth, current = session.execute(select(
        func.count(),
        func.count().filter(OrbitalObject.is_earth_orbit.is_(True)),
        func.count().filter(OrbitalObject.has_current_elements.is_(True)),
    ).select_from(OrbitalObject)).one()

    # Canonical ordering is epoch DESC, provider priority, id DESC. Ties have
    # the same age, so MAX(epoch) suffices for coverage and quality counts.
    # No element selection or provider priority is changed or reimplemented.
    latest = select(OrbitalElement.orbital_object_id,
                    func.max(OrbitalElement.epoch).label("epoch")).group_by(
                        OrbitalElement.orbital_object_id).subquery()
    canonical = session.scalar(select(func.count()).select_from(latest))
    status = case(
        (latest.c.epoch >= now - timedelta(hours=settings.ephemeris_warning_hours), "fresh"),
        (latest.c.epoch >= now - timedelta(hours=settings.ephemeris_stale_hours), "aging"),
        (latest.c.epoch >= now - timedelta(hours=settings.ephemeris_max_hours), "stale"),
        else_="expired",
    )
    counts = dict(session.execute(select(status, func.count()).select_from(latest).join(
        OrbitalObject, OrbitalObject.id == latest.c.orbital_object_id,
    ).where(OrbitalObject.is_earth_orbit.is_(True)).group_by(status)).all())
    values = (
        ("catalog_total_objects", "All SATCAT/catalog objects", total),
        ("earth_orbit_objects", "Objects classified as independent Earth-orbit objects", earth),
        ("objects_with_current_elements", "Catalog has_current_elements flag; not a freshness guarantee", current),
        ("canonical_elements_total", "Objects with a canonical latest element across the full catalog", canonical),
        ("screening_eligible_objects", "Earth-orbit objects with non-expired canonical elements at refresh time",
         sum(counts.get(s, 0) for s in ("fresh", "aging", "stale"))),
    )
    for name, description, value in values:
        yield gauge("orbitalai_" + name, description, value)
    quality = GaugeMetricFamily("orbitalai_ephemeris_objects", "Earth-orbit canonical elements by age at refresh time", labels=["status"])
    for label in ("fresh", "aging", "stale", "expired"):
        quality.add_metric([label], counts.get(label, 0))
    yield quality


class CatalogMetricsCollector(CachedCollector):
    def __init__(self, session_factory=None, settings=None):
        self.session_factory = session_factory
        self.settings = settings
        super().__init__("catalog", self.load)

    def load(self):
        settings = self.settings or get_settings()
        with (self.session_factory or get_session_factory())() as session:
            return tuple(catalog_metrics(session, settings, datetime.now(timezone.utc)))

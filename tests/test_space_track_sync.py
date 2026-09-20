from copy import deepcopy
from types import SimpleNamespace

from backend.app.services import space_track_sync


def _record(norad_cat_id):
    return {
        "NORAD_CAT_ID": norad_cat_id,
        "EPOCH": "2026-09-20T08:00:00Z",
        "INCLINATION": 51.6,
        "RA_OF_ASC_NODE": 123.4,
        "ECCENTRICITY": 0.0001,
        "ARG_OF_PERICENTER": 42.0,
        "MEAN_ANOMALY": 180.0,
        "MEAN_MOTION": 15.5,
    }


def test_space_track_ignores_unmatched_objects_and_preserves_catalog_fields(
    monkeypatch,
):
    orbital_object = SimpleNamespace(
        id=7,
        norad_cat_id=25544,
        object_type="PAYLOAD",
        owner="US",
        is_earth_orbit=True,
    )
    original = deepcopy(vars(orbital_object))

    class Repository:
        def __init__(self, session):
            pass

        def list_by_norad_cat_ids(self, identifiers):
            assert identifiers == [25544, 99999]
            return [orbital_object]

    class ScalarResult:
        def all(self):
            return [101]

    class Session:
        def __init__(self):
            self.updates = []
            self.committed = False

        def scalars(self, statement):
            return ScalarResult()

        def execute(self, statement):
            self.updates.append(statement)

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("successful sync must not roll back")

    monkeypatch.setattr(
        space_track_sync,
        "OrbitalObjectRepository",
        Repository,
    )
    session = Session()

    result = space_track_sync.sync_space_track_gp(
        session,
        [
            _record(25544),
            _record(99999),
        ],
    )

    assert result.records == 2
    assert result.matched_objects == 1
    assert result.unmatched_objects == 1
    assert result.elements_created == 1
    assert result.elements_existing == 0
    assert vars(orbital_object) == original
    assert session.committed is True
    assert len(session.updates) == 1
    assert session.updates[0].compile().params == {
        "has_current_elements": True,
        "id_1": [7],
    }

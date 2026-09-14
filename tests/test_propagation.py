import json
import math
from datetime import datetime
from pathlib import Path

import pytest
from sgp4.conveniences import sat_epoch_datetime

from orbital_engine.propagation import propagate_utc, satrec_from_omm


FIXTURE = Path(__file__).parent / "fixtures" / "iss_omm.json"


def load_iss_record() -> dict:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return records[0]


def test_satrec_from_omm():
    record = load_iss_record()

    satellite = satrec_from_omm(record)

    assert satellite.satnum == 25544


def test_propagation_returns_physical_state_vector():
    record = load_iss_record()
    satellite = satrec_from_omm(record)

    epoch = sat_epoch_datetime(satellite)

    position, velocity = propagate_utc(satellite, epoch)

    assert len(position) == 3
    assert len(velocity) == 3

    assert all(math.isfinite(value) for value in position)
    assert all(math.isfinite(value) for value in velocity)

    orbital_radius_km = math.sqrt(sum(value * value for value in position))
    speed_km_s = math.sqrt(sum(value * value for value in velocity))

    # Broad sanity bounds for an ISS-like LEO orbit.
    assert 6500 < orbital_radius_km < 7500
    assert 7.0 < speed_km_s < 8.5


def test_propagation_rejects_naive_datetime():
    record = load_iss_record()
    satellite = satrec_from_omm(record)

    with pytest.raises(ValueError, match="timezone-aware"):
        propagate_utc(
            satellite,
            datetime(2026, 9, 14, 12, 0, 0),
        )

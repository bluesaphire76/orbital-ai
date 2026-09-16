from datetime import datetime, timedelta, timezone
import weakref

import pytest

from orbital_engine.conjunction.episodes import (
    EncounterContinuityError,
    RelativeState,
    continuously_inside_threshold,
)


START = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _check(state_at, *, threshold=10.0, duration=60, **overrides):
    kwargs = dict(
        start=START, end=START + timedelta(seconds=duration),
        sample_times=[START + timedelta(seconds=s) for s in range(0, duration + 1, 60)],
        state_at=state_at, threshold_km=threshold, acceleration_bound_km_s2=0.157,
    )
    kwargs.update(overrides)
    return continuously_inside_threshold(**kwargs)


def test_inside_endpoints_alone_do_not_certify_continuity():
    seen = []

    def state_at(when):
        t = (when - START).total_seconds()
        seen.append(t)
        # Acceleration 0.02 km/s^2 is below the supplied 0.157 bound.
        return RelativeState((1 + .01*t*(60-t), 0, 0), (.6-.02*t, 0, 0))

    assert not _check(state_at, threshold=2)
    assert 30 in seen


def test_unresolved_grazing_threshold_fails_closed():
    with pytest.raises(EncounterContinuityError, match="unresolved"):
        _check(lambda when: RelativeState((10, 0, 0), (0, 0, 0)))


def test_propagation_failure_cannot_authorize_merge():
    def state_at(when):
        raise RuntimeError("SGP4 failed")

    with pytest.raises(EncounterContinuityError, match="propagation failed"):
        _check(state_at)


def test_nonfinite_state_cannot_authorize_merge():
    with pytest.raises(EncounterContinuityError, match="Non-finite"):
        _check(lambda when: RelativeState((float('nan'), 0, 0), (0, 0, 0)))


def test_observed_acceleration_bound_violation_fails_closed():
    def state_at(when):
        t = (when - START).total_seconds()
        return RelativeState((1, 0, 0), (t, 0, 0))

    with pytest.raises(EncounterContinuityError, match="acceleration bound"):
        _check(state_at)


def test_position_chord_bound_violation_fails_closed():
    def state_at(when):
        t = (when - START).total_seconds()
        # Inside the threshold, but inconsistent with the supplied bound.
        return RelativeState((10.8 - .01*t*(60-t), 0, 0), (0, 0, 0))

    with pytest.raises(EncounterContinuityError, match="Relative position"):
        _check(state_at, threshold=11, acceleration_bound_km_s2=0.001)


def test_submillisecond_overlap_does_not_assume_velocity_is_position_derivative():
    def state_at(when):
        t = (when - START).total_seconds()
        # The real 188/39320 overlap has a 0.000683 s gap and a ~0.069 m/s
        # difference between finite-difference and reported SGP4 velocity.
        return RelativeState((1 + t, 0, 0), (1.000069, 0, 0))

    assert _check(state_at, end=START + timedelta(seconds=0.000683))


def test_state_memory_does_not_scale_with_interval_length():
    class TrackedState(RelativeState):
        pass

    live = weakref.WeakSet()
    maximum_live = evaluations = 0

    def state_at(when):
        nonlocal maximum_live, evaluations
        # Unique velocities avoid equal dataclass values collapsing WeakSet entries.
        t = (when - START).total_seconds()
        state = TrackedState((1 + 1e-9*t*t, 0, 0), (2e-9*t, 0, 0))
        live.add(state)
        evaluations += 1
        maximum_live = max(maximum_live, len(live))
        return state

    assert _check(state_at, duration=3600)
    assert evaluations > 100
    assert maximum_live < 20
    assert not live

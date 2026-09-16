"""Threshold-connected encounter episodes, using final events only.

The continuity test requires an upper bound on relative acceleration over the
whole interval. It encloses the relative-position chord with A * dt**2 / 8.
Endpoint samples alone are never treated as evidence of continuous proximity.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace
from datetime import datetime
from math import isfinite
from typing import Callable, Iterable, Sequence

from orbital_engine.conjunction.distance import magnitude, subtract
from orbital_engine.conjunction.models import ClosestApproach, Vector3


# Outward numerical padding, in km; never an enlargement of the threshold.
POSITION_PADDING_KM = 1e-9


class EncounterContinuityError(RuntimeError):
    """Continuity could not be established; do not silently merge or split."""


@dataclass(frozen=True, slots=True)
class RelativeState:
    position_km: Vector3
    velocity_km_s: Vector3


RelativeStateAt = Callable[[datetime], RelativeState]


def continuously_inside_threshold(
    *,
    start: datetime,
    end: datetime,
    sample_times: Sequence[datetime],
    state_at: RelativeStateAt,
    threshold_km: float,
    acceleration_bound_km_s2: float,
    resolution_seconds: float = 0.01,
) -> bool:
    """Certify a connected inside-threshold interval, or observe an exit.

    The caller must supply a conservative relative-acceleration bound valid
    throughout the interval. For |r''| <= A, the vector chord interpolation
    error is <= A*dt**2/8; the norm of the chord cannot exceed the larger
    endpoint norm. Intervals that cannot be enclosed are bisected, evaluating
    the authoritative propagator again. The numerical resolution is a failure
    cutoff, never permission to assume continuity or suppress a nearby event.

    Work streams over global sample intervals. The subdivision stack retains
    only O(log(step/resolution)) states, with no global propagation cache.
    """
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError("Continuity bounds must be ordered and timezone-aware")
    if not isfinite(threshold_km) or threshold_km <= 0:
        raise ValueError("threshold_km must be finite and positive")
    if not isfinite(acceleration_bound_km_s2) or acceleration_bound_km_s2 < 0:
        raise ValueError("acceleration_bound_km_s2 must be finite and nonnegative")
    if not isfinite(resolution_seconds) or resolution_seconds <= 0:
        raise ValueError("resolution_seconds must be finite and positive")
    if not sample_times or start < sample_times[0] or end > sample_times[-1]:
        raise ValueError("Continuity interval must lie inside the global grid")

    def evaluate(when: datetime) -> RelativeState:
        try:
            state = state_at(when)
        except Exception as exc:
            raise EncounterContinuityError(
                f"Continuity propagation failed at {when.isoformat()}"
            ) from exc
        if not all(isfinite(value) for value in (*state.position_km, *state.velocity_km_s)):
            raise EncounterContinuityError(
                f"Non-finite continuity state at {when.isoformat()}"
            )
        return state

    left_time = start
    left = evaluate(start)
    if magnitude(left.position_km) > threshold_km:
        return False

    index = bisect_right(sample_times, start)
    while left_time < end:
        right_time = min(sample_times[index], end)
        right = evaluate(right_time)
        stack = [(left_time, left, right_time, right)]
        while stack:
            first_time, first, last_time, last = stack.pop()
            first_distance = magnitude(first.position_km)
            last_distance = magnitude(last.position_km)
            if max(first_distance, last_distance) > threshold_km:
                return False

            seconds = (last_time - first_time).total_seconds()
            # Reject observed velocity changes outside the caller's bound.
            # SGP4's reported velocity is not an exact numerical derivative
            # of its position series. In particular, a |dr - v*dt| check at
            # sub-millisecond gaps would reject valid overlap duplicates.
            # The continuity enclosure uses positions, not that identity.
            velocity_change = magnitude(subtract(last.velocity_km_s, first.velocity_km_s))
            if velocity_change > acceleration_bound_km_s2 * seconds + 1e-9:
                raise EncounterContinuityError(
                    "Relative state violates the continuity acceleration bound "
                    f"on {first_time.isoformat()} -> {last_time.isoformat()}"
                )

            upper_distance = (
                max(first_distance, last_distance)
                + acceleration_bound_km_s2 * seconds**2 / 8.0
                + POSITION_PADDING_KM
            )
            if upper_distance <= threshold_km:
                continue

            if seconds <= resolution_seconds:
                raise EncounterContinuityError(
                    "Threshold continuity unresolved at numerical resolution "
                    f"{resolution_seconds} s on "
                    f"{first_time.isoformat()} -> {last_time.isoformat()}; "
                    "refusing to classify the events as one or two episodes"
                )
            middle_time = first_time + (last_time - first_time) / 2
            middle = evaluate(middle_time)
            if magnitude(middle.position_km) > threshold_km:
                return False
            offset = (middle_time - first_time).total_seconds()
            fraction = offset / seconds
            chord_position = tuple(
                first.position_km[i] * (1 - fraction) + last.position_km[i] * fraction
                for i in range(3)
            )
            chord_error = magnitude(subtract(middle.position_km, chord_position))
            chord_bound = acceleration_bound_km_s2 * offset * (seconds - offset) / 2
            if chord_error > chord_bound + 2 * POSITION_PADDING_KM:
                raise EncounterContinuityError(
                    "Relative position violates the continuity acceleration bound "
                    f"at {middle_time.isoformat()}"
                )
            stack.append((middle_time, middle, last_time, last))
            stack.append((first_time, first, middle_time, middle))

        left_time, left = right_time, right
        index += 1

    return True


def _representative_order(event: ClosestApproach) -> tuple:
    return (
        event.miss_distance_km, event.tca, event.relative_velocity_km_s,
        event.delta_t_seconds, event.method,
    )


def merge_encounter_episodes(
    events: Iterable[ClosestApproach],
    *,
    continuous_between: Callable[[ClosestApproach, ClosestApproach], bool],
) -> tuple[tuple[ClosestApproach, ...], int]:
    """Merge connected TCAs for a pair, retaining the deterministic best event.

    Link neighboring TCAs, independently of the best representative's TCA:
    this avoids repeatedly checking a growing episode from its beginning.
    Equal TCAs already identify the same threshold state. Every nonzero gap,
    including gaps below one second, requires a continuity check.
    """
    ordered = [
        replace(event, primary_object_id=event.secondary_object_id,
                secondary_object_id=event.primary_object_id)
        if event.primary_object_id > event.secondary_object_id else event
        for event in events
    ]
    ordered.sort(key=lambda event: (
        event.primary_object_id, event.secondary_object_id, event.tca,
        _representative_order(event),
    ))
    retained: list[ClosestApproach] = []
    previous: ClosestApproach | None = None
    best: ClosestApproach | None = None
    for event in ordered:
        same_pair = previous is not None and (
            event.primary_object_id, event.secondary_object_id
        ) == (previous.primary_object_id, previous.secondary_object_id)
        if same_pair and (
            event.tca == previous.tca or continuous_between(previous, event)
        ):
            if _representative_order(event) < _representative_order(best):
                best = event
        else:
            if best is not None:
                retained.append(best)
            best = event
        previous = event
    if best is not None:
        retained.append(best)

    retained.sort(key=lambda event: (
        event.tca, event.miss_distance_km,
        event.primary_object_id, event.secondary_object_id,
    ))
    return tuple(retained), len(ordered) - len(retained)

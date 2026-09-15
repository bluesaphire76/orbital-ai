from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Collection, Iterable

from orbital_engine.conjunction.models import (
    CandidatePair,
    ClosestApproach,
    StateVector,
)
from orbital_engine.conjunction.refinement import (
    refine_closest_approach,
)
from orbital_engine.conjunction.screening import (
    find_candidate_pairs,
)


PairId = tuple[int, int]


@dataclass(frozen=True, slots=True)
class GridScreeningResult:
    samples: int
    raw_candidates: int
    suppressed_shared_pairs: int
    unique_candidates: int
    conjunctions: tuple[ClosestApproach, ...]


def inflated_screening_distance_km(
    *,
    candidate_distance_km: float,
    step_seconds: float,
    max_relative_speed_km_s: float,
) -> float:
    if candidate_distance_km <= 0:
        raise ValueError(
            "candidate_distance_km must be greater than zero"
        )

    if step_seconds <= 0:
        raise ValueError(
            "step_seconds must be greater than zero"
        )

    if max_relative_speed_km_s <= 0:
        raise ValueError(
            "max_relative_speed_km_s must be greater than zero"
        )

    return (
        candidate_distance_km
        + max_relative_speed_km_s
        * step_seconds
        / 2.0
    )


def _normalize_pair(
    first: int,
    second: int,
) -> PairId:
    if first < second:
        return first, second

    return second, first


def screen_propagation_grid(
    snapshots: Iterable[
        tuple[
            datetime,
            Iterable[StateVector],
        ]
    ],
    *,
    candidate_distance_km: float,
    step_seconds: float,
    max_relative_speed_km_s: float = 16.0,
    excluded_pairs: Collection[
        PairId
    ] | None = None,
) -> GridScreeningResult:
    screening_distance_km = (
        inflated_screening_distance_km(
            candidate_distance_km=(
                candidate_distance_km
            ),
            step_seconds=step_seconds,
            max_relative_speed_km_s=(
                max_relative_speed_km_s
            ),
        )
    )

    exclusions = set(
        excluded_pairs or ()
    )

    best_candidates: dict[
        PairId,
        CandidatePair,
    ] = {}

    suppressed_pairs_seen: set[
        PairId
    ] = set()

    sample_count = 0
    raw_candidate_count = 0

    first_sample_time: datetime | None = None
    last_sample_time: datetime | None = None

    for sample_time, states_iterable in snapshots:
        states = list(
            states_iterable
        )

        sample_count += 1

        if first_sample_time is None:
            first_sample_time = (
                sample_time
            )

        last_sample_time = (
            sample_time
        )

        candidates = find_candidate_pairs(
            states,
            screening_distance_km=(
                screening_distance_km
            ),
        )

        raw_candidate_count += len(
            candidates
        )

        for candidate in candidates:
            pair_id = _normalize_pair(
                candidate.primary.object_id,
                candidate.secondary.object_id,
            )

            if pair_id in exclusions:
                suppressed_pairs_seen.add(
                    pair_id
                )
                continue

            existing = best_candidates.get(
                pair_id
            )

            if (
                existing is None
                or candidate.screening_distance_km
                < existing.screening_distance_km
            ):
                best_candidates[
                    pair_id
                ] = candidate

    conjunctions: list[
        ClosestApproach
    ] = []

    half_window_seconds = (
        step_seconds / 2.0
    )

    for candidate in best_candidates.values():
        closest = refine_closest_approach(
            candidate,
            half_window_seconds=(
                half_window_seconds
            ),
        )

        if (
            closest.miss_distance_km
            > candidate_distance_km
        ):
            continue

        if (
            first_sample_time is not None
            and closest.tca
            < first_sample_time
        ):
            continue

        if (
            last_sample_time is not None
            and closest.tca
            > last_sample_time
        ):
            continue

        conjunctions.append(
            closest
        )

    conjunctions.sort(
        key=lambda result: (
            result.tca,
            result.miss_distance_km,
            result.primary_object_id,
            result.secondary_object_id,
        )
    )

    return GridScreeningResult(
        samples=sample_count,
        raw_candidates=(
            raw_candidate_count
        ),
        suppressed_shared_pairs=len(
            suppressed_pairs_seen
        ),
        unique_candidates=len(
            best_candidates
        ),
        conjunctions=tuple(
            conjunctions
        ),
    )

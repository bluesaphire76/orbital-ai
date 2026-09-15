from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import floor
from typing import Iterable

from orbital_engine.conjunction.distance import (
    distance_km,
)
from orbital_engine.conjunction.models import (
    CandidatePair,
    StateVector,
)


GridCell = tuple[int, int, int]


_NEIGHBOR_OFFSETS = tuple(
    (x, y, z)
    for x in (-1, 0, 1)
    for y in (-1, 0, 1)
    for z in (-1, 0, 1)
)


def _grid_cell(
    state: StateVector,
    cell_size_km: float,
) -> GridCell:
    x, y, z = state.position_km

    return (
        floor(x / cell_size_km),
        floor(y / cell_size_km),
        floor(z / cell_size_km),
    )


def _validate_states(
    states: list[StateVector],
) -> None:
    if not states:
        return

    object_ids = [
        state.object_id
        for state in states
    ]

    if len(object_ids) != len(set(object_ids)):
        raise ValueError(
            "State vectors must contain unique object IDs"
        )

    reference_time: datetime = states[0].when

    for state in states[1:]:
        if state.when != reference_time:
            raise ValueError(
                "All state vectors must use the same timestamp"
            )


def find_candidate_pairs(
    states: Iterable[StateVector],
    *,
    screening_distance_km: float,
) -> list[CandidatePair]:
    if screening_distance_km <= 0:
        raise ValueError(
            "screening_distance_km must be greater than zero"
        )

    state_list = list(states)

    _validate_states(
        state_list
    )

    grid: dict[
        GridCell,
        list[StateVector],
    ] = defaultdict(list)

    for state in state_list:
        grid[
            _grid_cell(
                state,
                screening_distance_km,
            )
        ].append(state)

    candidates: list[CandidatePair] = []
    seen_pairs: set[tuple[int, int]] = set()

    for cell, members in grid.items():
        cx, cy, cz = cell

        for dx, dy, dz in _NEIGHBOR_OFFSETS:
            neighbor = (
                cx + dx,
                cy + dy,
                cz + dz,
            )

            for primary in members:
                for secondary in grid.get(
                    neighbor,
                    (),
                ):
                    if (
                        primary.object_id
                        == secondary.object_id
                    ):
                        continue

                    pair_id = tuple(
                        sorted(
                            (
                                primary.object_id,
                                secondary.object_id,
                            )
                        )
                    )

                    if pair_id in seen_pairs:
                        continue

                    seen_pairs.add(
                        pair_id
                    )

                    separation = distance_km(
                        primary.position_km,
                        secondary.position_km,
                    )

                    if (
                        separation
                        <= screening_distance_km
                    ):
                        if (
                            primary.object_id
                            < secondary.object_id
                        ):
                            first = primary
                            second = secondary
                        else:
                            first = secondary
                            second = primary

                        candidates.append(
                            CandidatePair(
                                primary=first,
                                secondary=second,
                                screening_distance_km=(
                                    separation
                                ),
                            )
                        )

    candidates.sort(
        key=lambda candidate: (
            candidate.primary.object_id,
            candidate.secondary.object_id,
        )
    )

    return candidates

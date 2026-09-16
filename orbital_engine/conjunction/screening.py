from __future__ import annotations

from datetime import datetime
from typing import Iterable

import numpy as np
from scipy.spatial import cKDTree

from orbital_engine.conjunction.models import (
    CandidatePair,
    StateVector,
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

    reference_time: datetime = (
        states[0].when
    )

    for state in states[1:]:
        if state.when != reference_time:
            raise ValueError(
                "All state vectors must use "
                "the same timestamp"
            )


def find_candidate_pairs(
    states: Iterable[StateVector],
    *,
    screening_distance_km: float,
) -> list[CandidatePair]:
    if screening_distance_km <= 0:
        raise ValueError(
            "screening_distance_km "
            "must be greater than zero"
        )

    state_list = list(
        states
    )

    _validate_states(
        state_list
    )

    if len(state_list) < 2:
        return []

    positions = np.asarray(
        [
            state.position_km
            for state in state_list
        ],
        dtype=np.float64,
    )

    tree = cKDTree(
        positions
    )

    pair_indices = tree.query_pairs(
        r=screening_distance_km,
        p=2.0,
        eps=0.0,
        output_type="ndarray",
    )

    if pair_indices.size == 0:
        return []

    first_indices = (
        pair_indices[:, 0]
    )

    second_indices = (
        pair_indices[:, 1]
    )

    deltas = (
        positions[first_indices]
        - positions[second_indices]
    )

    separation_squared = np.einsum(
        "ij,ij->i",
        deltas,
        deltas,
    )

    separations = np.sqrt(
        separation_squared
    )

    candidates: list[
        CandidatePair
    ] = []

    for (
        first_index,
        second_index,
        separation,
    ) in zip(
        first_indices,
        second_indices,
        separations,
        strict=True,
    ):
        first_state = state_list[
            int(first_index)
        ]

        second_state = state_list[
            int(second_index)
        ]

        if (
            first_state.object_id
            < second_state.object_id
        ):
            primary = first_state
            secondary = second_state
        else:
            primary = second_state
            secondary = first_state

        candidates.append(
            CandidatePair(
                primary=primary,
                secondary=secondary,
                screening_distance_km=(
                    float(separation)
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
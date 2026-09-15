from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from backend.app.db.models.orbital_element import OrbitalElement


OrbitalFingerprint = tuple[
    str,
    object,
    float,
    float,
    float,
    float,
    float,
    float,
    float | None,
    float | None,
    float | None,
]


@dataclass(frozen=True, slots=True)
class SharedSolutionAnalysis:
    pairs: frozenset[tuple[int, int]]
    groups: int
    objects: int


def orbital_solution_fingerprint(
    element: OrbitalElement,
) -> OrbitalFingerprint:
    """
    Fingerprint only the values that define the propagated
    orbital solution.

    Catalog metadata such as element-set number or revolution
    number is deliberately excluded.
    """
    return (
        element.source,
        element.epoch,
        element.inclination,
        element.ra_of_asc_node,
        element.eccentricity,
        element.arg_of_pericenter,
        element.mean_anomaly,
        element.mean_motion,
        element.mean_motion_dot,
        element.mean_motion_ddot,
        element.bstar,
    )


def analyze_shared_orbital_solutions(
    elements: list[OrbitalElement],
) -> SharedSolutionAnalysis:
    groups: dict[
        OrbitalFingerprint,
        list[int],
    ] = defaultdict(list)

    for element in elements:
        groups[
            orbital_solution_fingerprint(element)
        ].append(
            element.orbital_object_id
        )

    shared_pairs: set[
        tuple[int, int]
    ] = set()

    shared_groups = 0
    shared_objects: set[int] = set()

    for object_ids in groups.values():
        unique_ids = sorted(
            set(object_ids)
        )

        if len(unique_ids) < 2:
            continue

        shared_groups += 1
        shared_objects.update(
            unique_ids
        )

        for first, second in combinations(
            unique_ids,
            2,
        ):
            shared_pairs.add(
                (first, second)
            )

    return SharedSolutionAnalysis(
        pairs=frozenset(
            shared_pairs
        ),
        groups=shared_groups,
        objects=len(shared_objects),
    )

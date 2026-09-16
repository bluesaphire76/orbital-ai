from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Iterable, Iterator

from sgp4.api import Satrec
from sgp4.earth_gravity import wgs72

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.models.orbital_element import OrbitalElement
from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.repositories.orbital_elements import (
    OrbitalElementRepository,
)
from backend.app.services.ephemeris_quality import (
    assess_ephemeris_quality,
)
from backend.app.services.ephemeris_selection import (
    select_screening_ephemerides,
)
from backend.app.services.orbital_fingerprint import (
    analyze_shared_orbital_solutions,
)
from orbital_engine.conjunction.episodes import (
    EncounterContinuityError,
    RelativeState,
    continuously_inside_threshold,
    merge_encounter_episodes,
)
from orbital_engine.conjunction.grid import (
    CandidateLimitExceeded,
    GridScreeningResult,
    screen_propagation_grid,
)
from orbital_engine.conjunction.models import (
    CandidatePair,
    ClosestApproach,
    StateVector,
)
from orbital_engine.conjunction.numerical_refinement import (
    refine_closest_approach_numerical,
)
from orbital_engine.propagation import (
    propagate_utc,
    satrec_from_omm,
)


EARTH_MU_KM3_S2 = 398600.4418

# Conservative safety multiplier for the inexpensive linear prefilter,
# also reused by the final-event continuity enclosure.
#
# The final conjunction solution always comes from
# numerical SGP4 refinement.
CURVATURE_SAFETY_FACTOR = 8.0


def _vector_magnitude(
    vector: tuple[
        float,
        float,
        float,
    ],
) -> float:
    x, y, z = vector

    return sqrt(
        x * x
        + y * y
        + z * z
    )


def _curvature_margin_km(
    candidate: CandidatePair,
    *,
    half_window_seconds: float,
) -> float:
    primary_radius = _vector_magnitude(
        candidate.primary.position_km
    )

    secondary_radius = _vector_magnitude(
        candidate.secondary.position_km
    )

    if (
        primary_radius <= 0.0
        or secondary_radius <= 0.0
    ):
        return float("inf")

    primary_acceleration = (
        EARTH_MU_KM3_S2
        / primary_radius**2
    )

    secondary_acceleration = (
        EARTH_MU_KM3_S2
        / secondary_radius**2
    )

    relative_acceleration_bound = (
        primary_acceleration
        + secondary_acceleration
    )

    nominal_curvature = (
        0.5
        * relative_acceleration_bound
        * half_window_seconds**2
    )

    return (
        CURVATURE_SAFETY_FACTOR
        * nominal_curvature
    )


def _linear_miss_distance_km(
    candidate: CandidatePair,
    *,
    half_window_seconds: float,
) -> float:
    """
    Cheap constant-relative-velocity closest-approach
    estimate.

    This function is intentionally minimal because it
    runs once for every coarse candidate.

    It does not produce an authoritative TCA. It exists
    only to reject obviously irrelevant candidates before
    the expensive numerical SGP4 refinement.
    """

    primary = candidate.primary
    secondary = candidate.secondary

    px, py, pz = (
        primary.position_km
    )

    sx, sy, sz = (
        secondary.position_km
    )

    pvx, pvy, pvz = (
        primary.velocity_km_s
    )

    svx, svy, svz = (
        secondary.velocity_km_s
    )

    rx = sx - px
    ry = sy - py
    rz = sz - pz

    vx = svx - pvx
    vy = svy - pvy
    vz = svz - pvz

    relative_speed_squared = (
        vx * vx
        + vy * vy
        + vz * vz
    )

    if relative_speed_squared == 0.0:
        delta_t_seconds = 0.0

    else:
        delta_t_seconds = -(
            rx * vx
            + ry * vy
            + rz * vz
        ) / relative_speed_squared

        delta_t_seconds = max(
            -half_window_seconds,
            min(
                half_window_seconds,
                delta_t_seconds,
            ),
        )

    closest_x = (
        rx
        + vx * delta_t_seconds
    )

    closest_y = (
        ry
        + vy * delta_t_seconds
    )

    closest_z = (
        rz
        + vz * delta_t_seconds
    )

    return sqrt(
        closest_x * closest_x
        + closest_y * closest_y
        + closest_z * closest_z
    )


@dataclass(frozen=True, slots=True)
class ConjunctionObjectLabel:
    orbital_object_id: int
    norad_cat_id: int
    object_name: str


@dataclass(frozen=True, slots=True)
class ConjunctionGridResult:
    start_time: datetime
    end_time: datetime

    objects: int
    samples: int

    propagation_attempts: int
    propagation_failures: int
    expired_skips: int

    shared_solution_groups: int
    shared_solution_objects: int
    suppressed_shared_pairs: int

    raw_candidates: int
    unique_candidates: int

    refinement_attempts: int
    refinement_failures: int

    # Exact orbital-element provenance used by this
    # screening run:
    #
    # (
    #     (orbital_object_id, orbital_element_id),
    #     ...
    # )
    #
    # Carrying this forward avoids querying canonical
    # ephemerides again during persistence.
    element_ids: tuple[
        tuple[int, int],
        ...,
    ]

    object_labels: tuple[
        ConjunctionObjectLabel,
        ...,
    ]

    refined_conjunctions: tuple[
        ClosestApproach,
        ...,
    ]

    # Summary only: candidate state vectors never escape a completed chunk.
    screening: GridScreeningResult

    chunk_count: int = 1
    chunk_seconds: int = 900
    duplicate_events_suppressed: int = 0
    max_chunk_raw_candidates: int = 0
    max_chunk_unique_candidates: int = 0
    max_chunk_refinement_attempts: int = 0

    # Diagnostic work on final-event pairs, separate from historical grid
    # counters. These counters are returned/printed, not new database columns.
    episode_checks: int = 0
    episode_propagation_attempts: int = 0


def _ensure_utc(
    when: datetime,
) -> datetime:
    if when.tzinfo is None:
        raise ValueError(
            "Grid start time must be timezone-aware"
        )

    return when.astimezone(
        timezone.utc
    )


def _build_sample_times(
    *,
    start_time: datetime,
    horizon_seconds: int,
    step_seconds: int,
) -> list[datetime]:
    if horizon_seconds <= 0:
        raise ValueError(
            "horizon_seconds must be greater than zero"
        )

    if step_seconds <= 0:
        raise ValueError(
            "step_seconds must be greater than zero"
        )

    if step_seconds > horizon_seconds:
        raise ValueError(
            "step_seconds cannot exceed horizon_seconds"
        )

    end_time = (
        start_time
        + timedelta(
            seconds=horizon_seconds
        )
    )

    times: list[datetime] = []
    current = start_time

    while current <= end_time:
        times.append(
            current
        )

        current += timedelta(
            seconds=step_seconds
        )

    if times[-1] < end_time:
        times.append(
            end_time
        )

    return times


def _load_object_labels(
    session: Session,
    *,
    object_ids: list[int],
) -> tuple[
    ConjunctionObjectLabel,
    ...,
]:
    if not object_ids:
        return ()

    objects = session.scalars(
        select(
            OrbitalObject
        )
        .where(
            OrbitalObject.id.in_(
                object_ids
            )
        )
        .order_by(
            OrbitalObject.id
        )
    )

    return tuple(
        ConjunctionObjectLabel(
            orbital_object_id=(
                orbital_object.id
            ),
            norad_cat_id=(
                orbital_object.norad_cat_id
            ),
            object_name=(
                orbital_object.object_name
            ),
        )
        for orbital_object in objects
    )


SatelliteMap = dict[int, tuple[OrbitalElement, Satrec]]
Snapshot = tuple[datetime, list[StateVector]]


def _build_sample_chunks(
    sample_times: list[datetime],
    *,
    step_seconds: int,
    chunk_seconds: int,
) -> list[slice]:
    """Slice the global grid; adjacent slices share exactly one timestamp.

    All full chunks contain chunk_seconds / step_seconds intervals. Only
    the final chunk can be shorter, including the existing partial end step.
    """
    if not isinstance(chunk_seconds, int) or chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be a positive integer")
    if step_seconds <= 0:
        raise ValueError("step_seconds must be greater than zero")
    if chunk_seconds < step_seconds:
        raise ValueError("chunk_seconds must be at least step_seconds")
    if chunk_seconds % step_seconds:
        raise ValueError("chunk_seconds must be a multiple of step_seconds")

    intervals = chunk_seconds // step_seconds
    return [
        slice(start, min(start + intervals + 1, len(sample_times)))
        for start in range(0, len(sample_times) - 1, intervals)
    ]


@dataclass(slots=True)
class _SnapshotStream:
    """Stream states, reusing only the last sample at a chunk boundary."""

    satellites: SatelliteMap
    settings: Settings
    preexpired_objects: int = 0
    propagation_attempts: int = 0
    propagation_failures: int = 0
    expired_skips: int = 0
    last_snapshot: Snapshot | None = None

    def iter_snapshots(self, sample_times: list[datetime]) -> Iterator[Snapshot]:
        for sample_time in sample_times:
            if self.last_snapshot is not None and self.last_snapshot[0] == sample_time:
                # Reuse successes, failures and quality decisions at this exact
                # timestamp. Propagation/expiry counters count global samples once.
                yield self.last_snapshot
                continue

            self.expired_skips += self.preexpired_objects
            states: list[StateVector] = []
            for element, satellite in self.satellites.values():
                quality = assess_ephemeris_quality(
                    epoch=element.epoch,
                    target_time=sample_time,
                    warning_hours=self.settings.ephemeris_warning_hours,
                    stale_hours=self.settings.ephemeris_stale_hours,
                    max_hours=self.settings.ephemeris_max_hours,
                )
                if not quality.propagation_allowed:
                    self.expired_skips += 1
                    continue

                self.propagation_attempts += 1
                try:
                    position, velocity = propagate_utc(satellite, sample_time)
                except Exception:
                    self.propagation_failures += 1
                    continue

                states.append(StateVector(
                    object_id=element.orbital_object_id,
                    when=sample_time,
                    position_km=position,
                    velocity_km_s=velocity,
                ))

            self.last_snapshot = sample_time, states
            yield self.last_snapshot


@dataclass(frozen=True, slots=True)
class _ChunkResult:
    screening: GridScreeningResult
    events: tuple[ClosestApproach, ...]
    refinement_attempts: int
    refinement_failures: int


def _refine_chunk_candidates(
    candidates: Iterable[CandidatePair],
    *,
    satellites: SatelliteMap,
    start_time: datetime,
    end_time: datetime,
    step_seconds: int,
    candidate_distance_km: float,
    use_linear_prefilter: bool,
) -> tuple[tuple[ClosestApproach, ...], int, int]:
    refined: list[
        ClosestApproach
    ] = []

    refinement_attempts = 0
    refinement_failures = 0

    half_window_seconds = (
        step_seconds / 2.0
    )

    for candidate in candidates:
        if use_linear_prefilter:
            linear_miss_distance_km = (
                _linear_miss_distance_km(
                    candidate,
                    half_window_seconds=(
                        half_window_seconds
                    ),
                )
            )

            curvature_margin_km = (
                _curvature_margin_km(
                    candidate,
                    half_window_seconds=(
                        half_window_seconds
                    ),
                )
            )

            prefilter_limit_km = (
                candidate_distance_km
                + curvature_margin_km
            )

            if (
                linear_miss_distance_km
                > prefilter_limit_km
            ):
                continue

        primary_entry = satellites.get(
            candidate.primary.object_id
        )

        secondary_entry = satellites.get(
            candidate.secondary.object_id
        )

        if (
            primary_entry is None
            or secondary_entry is None
        ):
            refinement_failures += 1
            continue

        _, primary_satellite = (
            primary_entry
        )

        _, secondary_satellite = (
            secondary_entry
        )

        candidate_time = (
            candidate.primary.when
        )

        # Preserve candidate time +/- one step, clamped only to the
        # GLOBAL run bounds. A boundary candidate can refine into either chunk.
        search_start = max(
            start_time,
            candidate_time
            - timedelta(
                seconds=step_seconds
            ),
        )

        search_end = min(
            end_time,
            candidate_time
            + timedelta(
                seconds=step_seconds
            ),
        )

        if search_end <= search_start:
            refinement_failures += 1
            continue

        def primary_state_at(
            when: datetime,
            satellite=primary_satellite,
        ):
            return propagate_utc(
                satellite,
                when,
            )

        def secondary_state_at(
            when: datetime,
            satellite=secondary_satellite,
        ):
            return propagate_utc(
                satellite,
                when,
            )

        refinement_attempts += 1

        try:
            closest = (
                refine_closest_approach_numerical(
                    candidate,
                    primary_state_at=(
                        primary_state_at
                    ),
                    secondary_state_at=(
                        secondary_state_at
                    ),
                    search_start=(
                        search_start
                    ),
                    search_end=(
                        search_end
                    ),
                    tolerance_seconds=0.01,
                )
            )

        except Exception:
            refinement_failures += 1
            continue

        if (
            closest.miss_distance_km
            <= candidate_distance_km
        ):
            refined.append(
                closest
            )

    return tuple(refined), refinement_attempts, refinement_failures


def _run_screening_chunk(
    snapshots: Iterable[Snapshot],
    *,
    satellites: SatelliteMap,
    start_time: datetime,
    end_time: datetime,
    step_seconds: int,
    candidate_distance_km: float,
    max_relative_speed_km_s: float,
    excluded_pairs: frozenset[tuple[int, int]],
    use_linear_prefilter: bool,
    max_unique_candidates: int,
) -> _ChunkResult:
    screening = screen_propagation_grid(
        snapshots,
        candidate_distance_km=candidate_distance_km,
        step_seconds=step_seconds,
        max_relative_speed_km_s=max_relative_speed_km_s,
        excluded_pairs=excluded_pairs,
        # Keep the validated lightweight prefilter; no per-candidate
        # linear ClosestApproach allocation in the engine.
        build_linear_conjunctions=False,
        max_unique_candidates=max_unique_candidates,
    )
    events, attempts, failures = _refine_chunk_candidates(
        screening.candidates,
        satellites=satellites,
        start_time=start_time,
        end_time=end_time,
        step_seconds=step_seconds,
        candidate_distance_km=candidate_distance_km,
        use_linear_prefilter=use_linear_prefilter,
    )
    # The candidate tuple and all states it owns are released when this
    # helper returns, BEFORE screening starts on the next chunk.
    return _ChunkResult(
        screening=replace(screening, candidates=()),
        events=events,
        refinement_attempts=attempts,
        refinement_failures=failures,
    )


@dataclass(slots=True)
class _EpisodeWork:
    checks: int = 0
    propagation_attempts: int = 0


def _merge_chunk_events(
    events: Iterable[ClosestApproach],
    *,
    satellites: SatelliteMap,
    sample_times: list[datetime],
    candidate_distance_km: float,
    work: _EpisodeWork,
) -> tuple[tuple[ClosestApproach, ...], int]:
    # Use the existing Earth-orbit curvature safety factor, evaluated at
    # Earth's surface to avoid underestimating acceleration between samples.
    # This is an explicit conservative Earth-orbit kinematic assumption for
    # the continuity enclosure, not a change to SGP4 or numerical refinement.
    acceleration_bound = (
        CURVATURE_SAFETY_FACTOR * 2 * wgs72.mu / wgs72.radiusearthkm**2
    )

    def continuous_between(first: ClosestApproach, last: ClosestApproach) -> bool:
        work.checks += 1
        pair = first.primary_object_id, first.secondary_object_id
        primary_satellite = satellites[pair[0]][1]
        secondary_satellite = satellites[pair[1]][1]

        def relative_state_at(when: datetime) -> RelativeState:
            work.propagation_attempts += 1
            primary_position, primary_velocity = propagate_utc(primary_satellite, when)
            work.propagation_attempts += 1
            secondary_position, secondary_velocity = propagate_utc(secondary_satellite, when)
            if min(_vector_magnitude(primary_position), _vector_magnitude(secondary_position)) < wgs72.radiusearthkm:
                raise EncounterContinuityError(
                    "Continuity acceleration enclosure requires Earth-orbit states above Earth's surface"
                )
            return RelativeState(
                position_km=tuple(s - p for p, s in zip(primary_position, secondary_position)),
                velocity_km_s=tuple(s - p for p, s in zip(primary_velocity, secondary_velocity)),
            )

        try:
            return continuously_inside_threshold(
                start=first.tca,
                end=last.tca,
                sample_times=sample_times,
                state_at=relative_state_at,
                threshold_km=candidate_distance_km,
                acceleration_bound_km_s2=acceleration_bound,
            )
        except EncounterContinuityError as exc:
            raise EncounterContinuityError(
                f"Encounter continuity for pair {pair[0]}/{pair[1]}, "
                f"{first.tca.isoformat()} -> {last.tca.isoformat()}: {exc}"
            ) from exc

    # The merger only visits pairs with multiple final events. Neighboring
    # TCAs are linked by threshold continuity, including when global refinement
    # puts a chunk's event on the other side of its nominal boundary.
    return merge_encounter_episodes(events, continuous_between=continuous_between)


def run_conjunction_grid(
    session: Session,
    *,
    start_time: datetime,
    horizon_seconds: int = 6 * 60 * 60,
    step_seconds: int = 60,
    candidate_distance_km: float = 10.0,
    max_relative_speed_km_s: float = 16.0,
    source: str = "celestrak",
    use_linear_prefilter: bool = True,
    chunk_seconds: int | None = None,
) -> ConjunctionGridResult:
    start_time = _ensure_utc(start_time)
    settings = get_settings()
    if chunk_seconds is None:
        chunk_seconds = settings.screening_chunk_seconds

    sample_times = _build_sample_times(
        start_time=start_time,
        horizon_seconds=horizon_seconds,
        step_seconds=step_seconds,
    )
    chunks = _build_sample_chunks(
        sample_times,
        step_seconds=step_seconds,
        chunk_seconds=chunk_seconds,
    )
    end_time = sample_times[-1]

    preexpired_objects = 0
    if source == "canonical":
        selection = select_screening_ephemerides(session, target_time=start_time)
        elements = list(selection.eligible_elements)
        preexpired_objects = selection.expired_total
    else:
        elements = OrbitalElementRepository(session).list_latest(source=source)

    if len(elements) > settings.screening_max_objects:
        raise RuntimeError(
            f"Screening object count {len(elements)} exceeds "
            f"ORBITAL_SCREENING_MAX_OBJECTS={settings.screening_max_objects}. "
            "Full-catalog screening exceeds the configured safety limit."
        )

    # Overlap snapshots are reused, so each object/global sample contributes
    # once to the grid workload estimate. Numerical refinement is separate.
    estimated_propagations = len(elements) * len(sample_times)
    if estimated_propagations > settings.screening_max_propagations:
        raise RuntimeError(
            f"Estimated propagation workload {estimated_propagations} exceeds "
            "ORBITAL_SCREENING_MAX_PROPAGATIONS="
            f"{settings.screening_max_propagations}. "
            "Reduce the screening horizon to fit the total-work budget."
        )

    shared_solutions = analyze_shared_orbital_solutions(elements)
    object_labels = _load_object_labels(
        session, object_ids=[element.orbital_object_id for element in elements],
    )
    element_ids = tuple(
        (element.orbital_object_id, element.id) for element in elements
    )
    satellites: SatelliteMap = {}
    for element in elements:
        try:
            satellite = satrec_from_omm(element.raw_omm)
        except Exception:
            continue
        satellites[element.orbital_object_id] = element, satellite

    stream = _SnapshotStream(satellites, settings, preexpired_objects)
    raw_candidates = unique_candidates = suppressed_shared_pairs = 0
    refinement_attempts = refinement_failures = 0
    max_raw = max_unique = max_refinements = 0
    events: list[ClosestApproach] = []

    for index, chunk_slice in enumerate(chunks, start=1):
        chunk_times = sample_times[chunk_slice]
        try:
            chunk = _run_screening_chunk(
                stream.iter_snapshots(chunk_times),
                satellites=satellites,
                start_time=start_time,
                end_time=end_time,
                step_seconds=step_seconds,
                candidate_distance_km=candidate_distance_km,
                max_relative_speed_km_s=max_relative_speed_km_s,
                excluded_pairs=shared_solutions.pairs,
                use_linear_prefilter=use_linear_prefilter,
                max_unique_candidates=settings.screening_max_chunk_unique_candidates,
            )
        except CandidateLimitExceeded as exc:
            raise RuntimeError(
                f"Chunk {index}/{len(chunks)}, "
                f"samples {chunk_slice.start}..{chunk_slice.stop - 1}, "
                f"{chunk_times[0].isoformat()} -> {chunk_times[-1].isoformat()}: {exc}"
            ) from exc

        raw_candidates += chunk.screening.raw_candidates
        unique_candidates += chunk.screening.unique_candidates
        suppressed_shared_pairs += chunk.screening.suppressed_shared_pairs
        refinement_attempts += chunk.refinement_attempts
        refinement_failures += chunk.refinement_failures
        max_raw = max(max_raw, chunk.screening.raw_candidates)
        max_unique = max(max_unique, chunk.screening.unique_candidates)
        max_refinements = max(max_refinements, chunk.refinement_attempts)
        events.extend(chunk.events)

    episode_work = _EpisodeWork()
    refined, duplicates = _merge_chunk_events(
        events,
        satellites=satellites,
        sample_times=sample_times,
        candidate_distance_km=candidate_distance_km,
        work=episode_work,
    )
    return ConjunctionGridResult(
        start_time=start_time,
        end_time=end_time,
        objects=len(elements),
        samples=len(sample_times),
        propagation_attempts=stream.propagation_attempts,
        propagation_failures=stream.propagation_failures,
        expired_skips=stream.expired_skips,
        shared_solution_groups=shared_solutions.groups,
        shared_solution_objects=shared_solutions.objects,
        suppressed_shared_pairs=suppressed_shared_pairs,
        raw_candidates=raw_candidates,
        unique_candidates=unique_candidates,
        refinement_attempts=refinement_attempts,
        refinement_failures=refinement_failures,
        element_ids=element_ids,
        object_labels=object_labels,
        refined_conjunctions=refined,
        screening=GridScreeningResult(
            samples=len(sample_times),
            raw_candidates=raw_candidates,
            suppressed_shared_pairs=suppressed_shared_pairs,
            unique_candidates=unique_candidates,
            candidates=(),
            conjunctions=(),
        ),
        chunk_count=len(chunks),
        chunk_seconds=chunk_seconds,
        duplicate_events_suppressed=duplicates,
        max_chunk_raw_candidates=max_raw,
        max_chunk_unique_candidates=max_unique,
        max_chunk_refinement_attempts=max_refinements,
        episode_checks=episode_work.checks,
        episode_propagation_attempts=episode_work.propagation_attempts,
    )

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import permutations
from math import cos, pi, sin
from types import SimpleNamespace
import weakref

import pytest

from backend.app.core.config import Settings
from backend.app.services import conjunction_grid as service
from orbital_engine.conjunction import grid as engine_grid
from orbital_engine.conjunction.models import CandidatePair, ClosestApproach
from orbital_engine.conjunction.episodes import (
    RelativeState, continuously_inside_threshold, merge_encounter_episodes,
)


WHEN = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _settings(**overrides):
    return replace(Settings(
        environment="test", log_level="INFO",
        postgres_host="localhost", postgres_port=5432,
        postgres_db="test", postgres_user="test", postgres_password="test-only",
        ephemeris_warning_hours=12, ephemeris_stale_hours=24, ephemeris_max_hours=72,
        screening_max_objects=40_000, screening_max_propagations=12_000_000,
    ), **overrides)


def _element(object_id, epoch=WHEN):
    return SimpleNamespace(
        id=object_id * 101, orbital_object_id=object_id, epoch=epoch,
        raw_omm={"object_id": object_id}, source="space-track",
        inclination=51.6, ra_of_asc_node=0, eccentricity=0,
        arg_of_pericenter=0, mean_anomaly=object_id, mean_motion=15,
        mean_motion_dot=0, mean_motion_ddot=0, bstar=0,
    )


@pytest.fixture
def synthetic_scene(monkeypatch):
    """Synthetic trajectories through the real tree, prefilter and minimizer."""
    scene = SimpleNamespace(
        settings=_settings(), elements=[_element(1), _element(2)],
        selection_calls=[], propagation_calls=[], expired_total=0,
        trajectory=lambda seconds: (75 - seconds, -1.0),
    )
    monkeypatch.setattr(service, "get_settings", lambda: scene.settings)

    def select(session, *, target_time):
        scene.selection_calls.append(target_time)
        return SimpleNamespace(
            eligible_elements=tuple(scene.elements), expired_total=scene.expired_total,
        )

    def propagate(satellite, when):
        scene.propagation_calls.append((satellite, when))
        if satellite == 1:
            return (7000.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        x, velocity = scene.trajectory((when - WHEN).total_seconds())
        return (7000.0 + x, 1.0, 0.0), (velocity, 0.0, 0.0)

    monkeypatch.setattr(service, "select_screening_ephemerides", select)
    monkeypatch.setattr(service, "_load_object_labels", lambda *a, **kw: ())
    monkeypatch.setattr(service, "satrec_from_omm", lambda omm: omm["object_id"])
    monkeypatch.setattr(service, "propagate_utc", propagate)
    return scene


def _run(**overrides):
    kwargs = dict(
        start_time=WHEN, horizon_seconds=120, step_seconds=60,
        chunk_seconds=60, candidate_distance_km=2.0, source="canonical",
    )
    kwargs.update(overrides)
    return service.run_conjunction_grid(None, **kwargs)


@pytest.mark.parametrize("horizon, expected", [
    (60, [(0, 1)]), (899, [(0, 15)]), (900, [(0, 15)]),
    (901, [(0, 15), (15, 16)]), (1800, [(0, 15), (15, 30)]),
    (3600, [(0, 15), (15, 30), (30, 45), (45, 60)]),
])
def test_global_sample_slices(horizon, expected):
    times = service._build_sample_times(
        start_time=WHEN, horizon_seconds=horizon, step_seconds=60,
    )
    slices = service._build_sample_chunks(times, step_seconds=60, chunk_seconds=900)
    assert [(s.start, s.stop - 1) for s in slices] == expected
    assert slices == service._build_sample_chunks(times, step_seconds=60, chunk_seconds=900)
    chunks = [times[s] for s in slices]
    assert chunks[0][0] == WHEN
    assert chunks[-1][-1] == WHEN + timedelta(seconds=horizon)
    reconstructed = chunks[0][:]
    for previous, current in zip(chunks, chunks[1:]):
        assert previous[-1] is current[0]
        assert set(previous) & set(current) == {current[0]}
        reconstructed.extend(current[1:])
    assert reconstructed == times


@pytest.mark.parametrize("chunk_seconds", [0, -1, 30, 901, 900.5])
def test_invalid_chunk_sizes(chunk_seconds):
    with pytest.raises(ValueError, match="chunk_seconds"):
        service._build_sample_chunks([WHEN, WHEN + timedelta(seconds=60)],
                                     step_seconds=60, chunk_seconds=chunk_seconds)


def _event(seconds=0, miss=1.0, pair=(1, 2)):
    return ClosestApproach(
        primary_object_id=pair[0], secondary_object_id=pair[1],
        tca=WHEN + timedelta(seconds=seconds), miss_distance_km=miss,
        relative_velocity_km_s=1, delta_t_seconds=0, method="numerical-propagation",
    )


def _merge_events(events, trajectory=lambda seconds: (0.5, 0.0)):
    times = [WHEN + timedelta(seconds=seconds) for seconds in range(0, 6001, 60)]

    def continuous(first, last):
        def state_at(when):
            distance, speed = trajectory((when - WHEN).total_seconds())
            return RelativeState((distance, 0.0, 0.0), (speed, 0.0, 0.0))
        return continuously_inside_threshold(
            start=first.tca, end=last.tca, sample_times=times,
            state_at=state_at, threshold_km=2, acceleration_bound_km_s2=0.157,
        )

    return merge_encounter_episodes(events, continuous_between=continuous)


@pytest.mark.parametrize("offset", [0, 0.5, 1.0, 120.0])
def test_continuous_events_merge_independently_of_time_gap(offset):
    better = _event(offset, miss=0.5)
    events, suppressed = _merge_events([_event(), better])
    assert events == (better,)
    assert suppressed == 1


def test_event_merge_preserves_threshold_exits_and_different_pairs():
    events = [_event(), _event(120), _event(5400), _event(pair=(1, 3))]
    # All reported TCAs are inside; intervening separations reach 3 km.
    trajectory = lambda t: (2 - cos(pi*t/60), pi/60*sin(pi*t/60))
    merged, suppressed = _merge_events(events, trajectory)
    assert set(merged) == set(events)
    assert suppressed == 0
    assert [e.tca for e in merged] == sorted(e.tca for e in events)


def test_event_merge_normalizes_pairs_and_breaks_ties_by_earlier_tca():
    earlier = _event(0.25)
    trajectory = lambda t: (1 + 2*sin(pi*t/20)**2, pi/10*sin(pi*t/10))
    for order in permutations([_event(0.75, pair=(2, 1)), earlier, _event(20)]):
        merged, suppressed = _merge_events(order, trajectory)
        assert merged == (earlier, _event(20))
        assert suppressed == 1


def test_episode_links_neighboring_tcas_independently_of_best_representative():
    events = [_event(0, miss=0.5), _event(120, miss=1), _event(240, miss=0.6)]
    for order in permutations(events):
        links = []
        def continuous(first, last):
            links.append((first.tca, last.tca))
            return True
        merged, suppressed = merge_encounter_episodes(order, continuous_between=continuous)
        assert merged == (events[0],)
        assert suppressed == 2
        assert links == [(events[0].tca, events[1].tca), (events[1].tca, events[2].tca)]


def test_continuous_pair_spanning_chunks_has_one_event(synthetic_scene):
    synthetic_scene.trajectory = lambda t: (1 + t/9000, 1/9000)
    chunked = _run(horizon_seconds=1800, chunk_seconds=900)
    reference = _run(horizon_seconds=1800, chunk_seconds=1800)
    assert len(chunked.refined_conjunctions) == 1
    assert chunked.refined_conjunctions == reference.refined_conjunctions
    assert chunked.duplicate_events_suppressed == 1
    assert chunked.episode_checks == 1
    assert chunked.episode_propagation_attempts > 0
    assert reference.episode_checks == reference.episode_propagation_attempts == 0
    assert chunked.propagation_attempts == reference.propagation_attempts == 62
    assert chunked.element_ids == ((1, 101), (2, 202))


def test_exit_between_grid_samples_preserves_distinct_events():
    # t=0,30,60 are all inside; exits peak at t=15,45, between those samples.
    trajectory = lambda t: (1.999 + .002*sin(pi*t/30)**2, .002*pi/30*sin(pi*t/15))
    events = [_event(0), _event(60)]
    merged, suppressed = _merge_events(events, trajectory)
    assert merged == tuple(events)
    assert suppressed == 0


def test_exit_and_reentry_even_below_one_second_preserves_events():
    trajectory = lambda t: (1.99999 + .00002*sin(pi*t/.5)**2,
                            .00002*pi/.5*sin(2*pi*t/.5))
    events = [_event(0), _event(.5)]
    merged, suppressed = _merge_events(events, trajectory)
    assert merged == tuple(events)
    assert suppressed == 0


@pytest.mark.parametrize("tca_seconds", [45, 60, 75])
def test_boundary_encounter_refines_across_chunk_bounds(synthetic_scene, monkeypatch, tca_seconds):
    synthetic_scene.trajectory = lambda seconds: (tca_seconds - seconds, -1.0)
    original_refine = service.refine_closest_approach_numerical
    searches = []

    def refine(candidate, **kwargs):
        result = original_refine(candidate, **kwargs)
        searches.append((candidate.primary.when, kwargs["search_start"], kwargs["search_end"], result))
        return result

    monkeypatch.setattr(service, "refine_closest_approach_numerical", refine)
    result = _run()
    assert result.chunk_count == 2
    assert len(searches) == 2
    for candidate_time, start, end, closest in searches:
        assert start == max(WHEN, candidate_time - timedelta(seconds=60))
        assert end == min(WHEN + timedelta(seconds=120), candidate_time + timedelta(seconds=60))
        assert abs((closest.tca - WHEN).total_seconds() - tca_seconds) < 0.01
    if tca_seconds > 60:
        assert searches[0][3].tca > WHEN + timedelta(seconds=60)
    elif tca_seconds < 60:
        assert searches[1][3].tca < WHEN + timedelta(seconds=60)
    assert len(result.refined_conjunctions) == 1
    assert result.refined_conjunctions[0].miss_distance_km == pytest.approx(1)
    assert result.duplicate_events_suppressed == 1
    assert result.propagation_attempts == 6
    assert result.propagation_failures == result.refinement_failures == 0
    assert result.raw_candidates == 4
    assert result.unique_candidates == result.refinement_attempts == 2
    assert result.max_chunk_raw_candidates == 2
    assert result.max_chunk_unique_candidates == result.max_chunk_refinement_attempts == 1
    assert result.screening.candidates == ()
    assert result.screening.samples == result.samples == 3
    assert synthetic_scene.selection_calls == [WHEN]
    assert result.element_ids == ((1, 101), (2, 202))


def test_separate_encounters_for_same_pair_survive(synthetic_scene):
    synthetic_scene.trajectory = lambda t: ((t - 30) * (t - 150) / 90, (2 * t - 180) / 90)
    result = _run(horizon_seconds=180)
    assert len(result.refined_conjunctions) == 2
    assert [(event.tca - WHEN).total_seconds() for event in result.refined_conjunctions] == pytest.approx([30, 150], abs=0.01)
    reference = _run(horizon_seconds=180, chunk_seconds=180)
    assert len(reference.refined_conjunctions) == 1
    assert any(abs((e.tca - reference.refined_conjunctions[0].tca).total_seconds()) <= 1
               for e in result.refined_conjunctions)


def test_one_chunk_preserves_counts_physics_and_default(synthetic_scene):
    default = _run(horizon_seconds=900, chunk_seconds=None)
    explicit = _run(horizon_seconds=900, chunk_seconds=900)
    larger = _run(horizon_seconds=900, chunk_seconds=1800)
    no_prefilter = _run(horizon_seconds=900, chunk_seconds=900, use_linear_prefilter=False)
    assert default == explicit == replace(larger, chunk_seconds=900) == no_prefilter
    assert default.chunk_count == 1
    assert default.samples == 16
    assert default.propagation_attempts == 32
    assert default.duplicate_events_suppressed == 0
    assert default.raw_candidates == default.max_chunk_raw_candidates == 10
    assert default.unique_candidates == default.refinement_attempts == 1
    assert len(default.refined_conjunctions) == 1


def test_configured_chunk_default_is_used(synthetic_scene):
    synthetic_scene.settings = replace(synthetic_scene.settings, screening_chunk_seconds=60)
    assert _run(chunk_seconds=None).chunk_count == 2


@pytest.mark.parametrize("failure", [False, True])
def test_overlap_reuses_quality_and_failure_decisions(synthetic_scene, monkeypatch, failure):
    elements = [_element(1), _element(2, WHEN - timedelta(hours=72) + timedelta(seconds=60))]
    stream = service._SnapshotStream(
        {e.orbital_object_id: (e, e.orbital_object_id) for e in elements},
        synthetic_scene.settings, preexpired_objects=3,
    )
    original = service.propagate_utc

    def propagate(satellite, when):
        if failure and satellite == 1 and when == WHEN + timedelta(seconds=60):
            synthetic_scene.propagation_calls.append((satellite, when))
            raise RuntimeError("synthetic propagation failure")
        return original(satellite, when)

    monkeypatch.setattr(service, "propagate_utc", propagate)
    times = [WHEN + timedelta(seconds=s) for s in (0, 60, 120)]
    first = list(stream.iter_snapshots(times[:2]))
    second = list(stream.iter_snapshots(times[1:]))
    assert first[-1] is second[0]
    assert first[-1][1] is second[0][1]
    assert len(second[-1][1]) == 1  # Object 2 expires after the boundary.
    assert stream.propagation_attempts == 5
    assert stream.propagation_failures == int(failure)
    assert stream.expired_skips == 10  # 3 preexpired * 3 samples + 1 new expiry.
    assert all(count == 1 for count in Counter(synthetic_scene.propagation_calls).values())


def test_candidates_are_released_before_next_chunk(synthetic_scene, monkeypatch):
    class TrackedCandidate(CandidatePair):
        pass

    references = []
    original_find = engine_grid.find_candidate_pairs
    original_chunk = service._run_screening_chunk
    chunk_calls = 0

    def find(*args, **kwargs):
        candidates = [TrackedCandidate(c.primary, c.secondary, c.screening_distance_km)
                      for c in original_find(*args, **kwargs)]
        references.extend(weakref.ref(candidate) for candidate in candidates)
        return candidates

    def chunk(*args, **kwargs):
        nonlocal chunk_calls
        assert all(reference() is None for reference in references)
        chunk_calls += 1
        return original_chunk(*args, **kwargs)

    monkeypatch.setattr(engine_grid, "find_candidate_pairs", find)
    monkeypatch.setattr(service, "_run_screening_chunk", chunk)
    result = _run(horizon_seconds=180)
    assert chunk_calls == 3
    assert references and all(reference() is None for reference in references)
    assert result.screening.candidates == ()


@pytest.mark.parametrize("field, limit, error", [
    ("screening_max_objects", 1, "ORBITAL_SCREENING_MAX_OBJECTS=1"),
    ("screening_max_propagations", 5, "ORBITAL_SCREENING_MAX_PROPAGATIONS=5"),
])
def test_work_guards_precede_propagation(synthetic_scene, field, limit, error):
    synthetic_scene.settings = replace(synthetic_scene.settings, **{field: limit})
    with pytest.raises(RuntimeError, match=error):
        _run()
    assert synthetic_scene.propagation_calls == []


def test_total_budget_counts_overlap_only_once(synthetic_scene):
    synthetic_scene.settings = replace(synthetic_scene.settings, screening_max_propagations=6)
    assert _run().propagation_attempts == 6


def test_candidate_guard_has_chunk_and_global_sample_bounds(synthetic_scene):
    synthetic_scene.elements.append(_element(3))
    synthetic_scene.settings = replace(synthetic_scene.settings, screening_max_chunk_unique_candidates=1)
    with pytest.raises(RuntimeError) as raised:
        _run()
    message = str(raised.value)
    assert "Chunk 1/2, samples 0..1" in message
    assert WHEN.isoformat() in message
    assert (WHEN + timedelta(seconds=60)).isoformat() in message
    assert "ORBITAL_SCREENING_MAX_CHUNK_UNIQUE_CANDIDATES=1" in message
    assert len(synthetic_scene.propagation_calls) == 3  # Fail during the first snapshot.


def test_invalid_chunk_override_fails_before_selection(synthetic_scene):
    with pytest.raises(ValueError, match="chunk_seconds"):
        _run(chunk_seconds=61)
    assert synthetic_scene.selection_calls == []


def test_empty_catalog_still_reports_chunks(synthetic_scene):
    synthetic_scene.elements.clear()
    result = _run()
    assert result.chunk_count == 2
    assert result.objects == result.propagation_attempts == result.unique_candidates == 0
    assert result.refined_conjunctions == ()


def test_screening_settings_defaults_and_overrides(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-only")
    for name in ("MAX_OBJECTS", "MAX_PROPAGATIONS", "CHUNK_SECONDS", "MAX_CHUNK_UNIQUE_CANDIDATES"):
        monkeypatch.delenv(f"ORBITAL_SCREENING_{name}", raising=False)
    settings = Settings.from_env()
    assert settings.screening_max_objects == 40_000
    assert settings.screening_max_propagations == 12_000_000
    assert settings.screening_chunk_seconds == 900
    assert settings.screening_max_chunk_unique_candidates == 4_000_000
    monkeypatch.setenv("ORBITAL_SCREENING_CHUNK_SECONDS", "1800")
    assert Settings.from_env().screening_chunk_seconds == 1800
    monkeypatch.setenv("ORBITAL_SCREENING_CHUNK_SECONDS", "0")
    with pytest.raises(ValueError, match="ORBITAL_SCREENING_CHUNK_SECONDS"):
        Settings.from_env()


@pytest.mark.parametrize("field", ["screening_max_objects", "screening_max_propagations",
                                   "screening_chunk_seconds", "screening_max_chunk_unique_candidates"])
def test_nonpositive_safety_limits_rejected(field):
    with pytest.raises(ValueError, match="must be greater than zero"):
        _settings(**{field: 0})


@pytest.fixture
def persistence_session():
    """Real SQL constraints/transactions; only PostgreSQL identity generation is emulated."""
    from itertools import count
    from sqlalchemy import BigInteger, Column, MetaData, Table, create_engine, event
    from sqlalchemy.orm import Session
    from backend.app.db.models.conjunction import ConjunctionEvent, ConjunctionRun

    engine = create_engine("sqlite://")
    metadata = MetaData()
    objects = Table("orbital_objects", metadata, Column("id", BigInteger, primary_key=True))
    elements = Table("orbital_elements", metadata, Column("id", BigInteger, primary_key=True))
    ConjunctionRun.__table__.to_metadata(metadata)
    ConjunctionEvent.__table__.to_metadata(metadata)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.execute(objects.insert(), [{"id": 1}, {"id": 2}])
        connection.execute(elements.insert(), [{"id": i} for i in (101, 202, 1001, 2002)])

    with Session(engine) as session:
        ids = count(1)

        @event.listens_for(session, "before_flush")
        def assign_sqlite_ids(session, context, instances):
            for item in session.new:
                if isinstance(item, (ConjunctionRun, ConjunctionEvent)) and item.id is None:
                    item.id = next(ids)

        yield session
    engine.dispose()


def _execute(session):
    from backend.app.services.conjunction_runs import execute_conjunction_screening
    return execute_conjunction_screening(
        session, start_time=WHEN, horizon_seconds=180, step_seconds=60,
        candidate_distance_km=2, source="canonical", chunk_seconds=60,
    )


def test_persist_multiple_encounters_with_exact_selected_elements(
    synthetic_scene, persistence_session, monkeypatch,
):
    from sqlalchemy import select
    from backend.app.db.models.conjunction import ConjunctionEvent, ConjunctionRun
    from backend.app.db.repositories.orbital_elements import OrbitalElementRepository
    from backend.app.api.routes.conjunctions import get_latest_run

    synthetic_scene.trajectory = lambda t: ((t - 30) * (t - 150) / 90, (2 * t - 180) / 90)

    def unexpected_query(*args, **kwargs):
        pytest.fail("Persistence must not select orbital elements a second time")

    monkeypatch.setattr(OrbitalElementRepository, "list_canonical_latest", unexpected_query)
    monkeypatch.setattr(OrbitalElementRepository, "list_latest", unexpected_query)
    execution = _execute(persistence_session)
    persistence_session.expire_all()
    rows = persistence_session.scalars(select(ConjunctionEvent).order_by(ConjunctionEvent.tca)).all()
    assert len(rows) == 2
    assert rows[0].tca != rows[1].tca
    for row in rows:
        assert (row.primary_object_id, row.secondary_object_id) == (1, 2)
        assert (row.primary_element_id, row.secondary_element_id) == (101, 202)
        assert row.run_id == execution.run_id
    assert synthetic_scene.selection_calls == [WHEN]
    run = persistence_session.get(ConjunctionRun, execution.run_id)
    assert run.event_count == 2
    assert run.chunk_count == 3
    assert run.chunk_seconds == 60
    assert run.duplicate_events_suppressed == 1
    assert run.unique_candidates == 3
    assert run.max_chunk_unique_candidates == run.max_chunk_refinement_attempts == 1
    assert run.max_chunk_raw_candidates == 2
    response = get_latest_run(session=persistence_session)
    assert response.chunk_count == 3
    assert response.duplicate_events_suppressed == 1
    assert response.max_chunk_refinement_attempts == 1


def test_persistence_still_rejects_exact_pair_and_tca_duplicates(synthetic_scene, persistence_session):
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from backend.app.db.models.conjunction import ConjunctionEvent

    _execute(persistence_session)
    row = persistence_session.scalars(select(ConjunctionEvent)).first()
    duplicate = ConjunctionEvent(**{
        column.name: getattr(row, column.name)
        for column in ConjunctionEvent.__table__.columns
        if column.name not in {"id", "created_at"}
    })
    persistence_session.add(duplicate)
    with pytest.raises(IntegrityError):
        persistence_session.flush()
    persistence_session.rollback()


def test_missing_provenance_rolls_back_the_whole_run(synthetic_scene, persistence_session, monkeypatch):
    from sqlalchemy import func, select
    from backend.app.db.models.conjunction import ConjunctionEvent, ConjunctionRun
    from backend.app.services import conjunction_runs

    result = _run(horizon_seconds=180)
    monkeypatch.setattr(conjunction_runs, "run_conjunction_grid",
                        lambda *a, **kw: replace(result, element_ids=((1, 101),)))
    with pytest.raises(RuntimeError, match="Missing orbital element provenance"):
        _execute(persistence_session)
    assert persistence_session.scalar(select(func.count()).select_from(ConjunctionRun)) == 0
    assert persistence_session.scalar(select(func.count()).select_from(ConjunctionEvent)) == 0


def test_worker_summary_reports_chunk_metrics(synthetic_scene, monkeypatch, capsys):
    from contextlib import nullcontext
    from workers.conjunction import run_screening as worker

    result = _run()
    calls = []

    def execute(session, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(result=result, run_id=42, duration_ms=123.0)

    monkeypatch.setattr("sys.argv", ["screening", "--hours", "0.5", "--chunk-seconds", "60",
                                    "--start-time", WHEN.isoformat(), "--summary-only"])
    monkeypatch.setattr(worker, "get_session_factory", lambda: lambda: nullcontext(None))
    monkeypatch.setattr(worker, "execute_conjunction_screening", execute)
    worker.main()
    output = capsys.readouterr().out
    for label in ("Run ID: 42", "Source: canonical", "Window:", "Objects:", "Samples:",
                  "Chunk count: 2", "Chunk seconds: 60", "Propagation attempts:",
                  "Propagation failures:", "Raw candidates:", "Chunk-unique candidate evaluations:",
                  "Refinement attempts:", "Refinement failures:", "Duplicate events suppressed: 1",
                  "Conjunction events: 1", "Duration:", "Max chunk unique candidates:",
                  "Episode continuity checks:", "Episode propagation attempts:"):
        assert label in output
    assert "Primary:" not in output
    assert calls[0]["start_time"] == WHEN
    assert calls[0]["chunk_seconds"] == 60
    assert calls[0]["source"] == "canonical"


def test_worker_rejects_naive_reference_time():
    import argparse
    from workers.conjunction.run_screening import _parse_start_time
    with pytest.raises(argparse.ArgumentTypeError, match="timezone"):
        _parse_start_time("2026-09-15T00:00:00")


def test_engine_candidate_guard_rejects_invalid_limit():
    with pytest.raises(ValueError, match="max_unique_candidates"):
        engine_grid.screen_propagation_grid([], candidate_distance_km=10,
                                            step_seconds=60, max_unique_candidates=0)


def test_persist_sustained_episode_with_exact_provenance(synthetic_scene, persistence_session):
    from sqlalchemy import select
    from backend.app.db.models.conjunction import ConjunctionEvent, ConjunctionRun

    synthetic_scene.trajectory = lambda t: (1 + t/9000, 1/9000)
    execution = _execute(persistence_session)
    persistence_session.expire_all()
    rows = persistence_session.scalars(select(ConjunctionEvent)).all()
    assert len(rows) == 1
    assert (rows[0].primary_element_id, rows[0].secondary_element_id) == (101, 202)
    assert rows[0].run_id == execution.run_id
    assert synthetic_scene.selection_calls == [WHEN]
    run = persistence_session.get(ConjunctionRun, execution.run_id)
    assert run.chunk_count == 3
    assert run.event_count == 1
    assert run.duplicate_events_suppressed == 2


def test_unresolved_episode_aborts_before_any_persistence(synthetic_scene, persistence_session, monkeypatch):
    from sqlalchemy import func, select
    from backend.app.db.models.conjunction import ConjunctionEvent, ConjunctionRun
    from orbital_engine.conjunction.episodes import EncounterContinuityError

    synthetic_scene.trajectory = lambda t: (1 + t/9000, 1/9000)

    def unresolved(**kwargs):
        raise EncounterContinuityError("unresolved synthetic threshold grazing")

    monkeypatch.setattr(service, "continuously_inside_threshold", unresolved)
    with pytest.raises(EncounterContinuityError, match="Encounter continuity for pair 1/2"):
        _execute(persistence_session)
    assert persistence_session.scalar(select(func.count()).select_from(ConjunctionRun)) == 0
    assert persistence_session.scalar(select(func.count()).select_from(ConjunctionEvent)) == 0

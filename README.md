# OrbitalAI

Local-first orbital intelligence, visualization and conjunction assessment platform.

OrbitalAI is designed as a sovereign, deterministic orbital operations platform for ingesting public orbital data, maintaining a local catalogue, propagating trajectories, screening conjunctions and supporting operator analysis through an interactive 3D mission-control workspace.

## Project status

Current development baseline: **v0.4**

The v0.4 work introduces the Orbital Operations Workspace, including:

- scalable 3D Earth visualization with CesiumJS;
- canonical orbital catalogue rendering;
- object search and selection;
- targeted object playback;
- conjunction analysis and exact-event replay;
- semantic object classification and coloring;
- collapsible object legend;
- high-resolution Earth imagery and terrain;
- solar day/night illumination;
- local NASA Black Marble night-light rendering.
- automated SATCAT, CelesTrak and Space-Track synchronization;
- catalog synchronization status, freshness and observability.

The previous stable release is **v0.3.0**.

The current v0.5 development work also contains an optional local AI
foundation and a fixed-input Conjunction Analyst Brief backend. AI remains
disabled by default and does not change the v0.4 deterministic runtime.

## Core principles

### Deterministic orbital mechanics

Orbital propagation and conjunction calculations are deterministic and authoritative.

The browser and AI layer do not calculate authoritative:

- orbital trajectories;
- time of closest approach (TCA);
- miss distance;
- relative velocity;
- collision probability.

Authoritative orbital mechanics remain in the backend.

### AI is assistive, not authoritative

AI is intended for:

- prioritisation;
- anomaly detection;
- trend analysis;
- explanation;
- decision support.

AI must not replace deterministic propagation, screening or collision-risk calculations.

The v0.5A foundation adds a bounded backend gateway for a separately managed
NVIDIA CUDA llama.cpp runtime. OrbitalAI does not support CPU inference,
partial model offload, or automatic CPU fallback. It exposes capability and
health endpoints plus a brief endpoint grounded in one persisted event; there
is no public free-form prompt endpoint.
Models and runtime images are not included or downloaded automatically. See
[v0.5 Local AI Foundation](docs/architecture/v0.5-local-ai-foundation.md) and
[v0.5B.1 Conjunction Analyst Brief](docs/architecture/v0.5b1-conjunction-analyst-brief.md).

### Local-first architecture

OrbitalAI is designed to keep the operational catalogue, propagation pipeline, conjunction analysis and future AI inference under local control.

External services are used as orbital-data sources and, where configured, for high-resolution geospatial assets.

## Architecture

```text
                 +------------------+
                 |     SATCAT       |
                 | metadata / type  |
                 +---------+--------+
                           |
                 +---------v--------+
                 |   CelesTrak GP   |
                 | public fallback  |
                 +---------+--------+
                           |
                 +---------v--------+
                 |   Space-Track    |
                 | primary GP data  |
                 +---------+--------+
                           |
                           v
                 +------------------+
                 |    PostgreSQL    |
                 | local catalogue  |
                 +---------+--------+
                           |
                           v
              +--------------------------+
              | Canonical ephemeris      |
              | selection + freshness    |
              +------------+-------------+
                           |
              +------------+-------------+
              |                          |
              v                          v
     +------------------+       +----------------------+
     | SGP4 propagation |       | Conjunction screening|
     +--------+---------+       +----------+-----------+
              |                            |
              +-------------+--------------+
                            |
                            v
                 +----------------------+
                 | FastAPI backend      |
                 | deterministic APIs   |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | Next.js + CesiumJS   |
                 | Operations Workspace |
                 +----------------------+
```

## Main capabilities

### Orbital catalogue

- local PostgreSQL catalogue;
- SATCAT metadata and classification;
- CelesTrak GP ingestion;
- Space-Track GP ingestion;
- historical orbital elements;
- canonical ephemeris selection;
- freshness and stale-element controls.

### Automated Catalog & Ephemeris Synchronization

The v0.4F.1 capability, implemented on the current feature branch, adds:

- the `catalog-sync` scheduler service;
- canonical SATCAT → CelesTrak `ACTIVE` → Space-Track ordering;
- independent 12-hour, 2-hour and 1-hour default cadences;
- per-source retry/backoff and a shared filesystem lock;
- `GET /catalog/sync-status` with last-success freshness;
- Prometheus metrics, Grafana panels and the Catalog Synchronization health UI.

Cadence, retry and provider settings use the `ORBITAL_CATALOG_SYNC_*`
variables in `.env.example`. Operational details are documented in
[v0.4F.1 — Automated Catalog & Ephemeris Synchronization](docs/architecture/v0.4f1-automated-catalog-ephemeris-synchronization.md).

### Propagation

- deterministic SGP4 propagation;
- backend-generated state vectors;
- Earth-fixed visualization coordinates;
- targeted playback for selected objects;
- no browser-side authoritative propagation.

### Conjunction screening

- scalable deterministic screening;
- cKDTree-based candidate detection;
- chunked screening windows;
- numerical refinement;
- duplicate-event suppression;
- exact event replay using the original orbital-element IDs.

The v0.4F.2 development work adds a dedicated `conjunction-screening`
Compose scheduler. It evaluates the latest successful canonical run in
PostgreSQL every 60 seconds, uses a four-hour cadence, and retains the
validated six-hour horizon and 60-second grid. Manual runs participate in the
same cadence and share a nonblocking filesystem lock with the scheduler.
Failures use persisted exponential retry state without replacing the database
as the source of successful-run history. See
[v0.4F.2 — Automated Conjunction Screening](docs/architecture/v0.4f2-automated-conjunction-screening.md).

Probability of collision is not currently calculated because covariance data is not yet part of the authoritative pipeline.

### Orbital Operations Workspace

The v0.4 workspace provides:

- interactive 3D Earth;
- large-scale object rendering;
- catalogue search;
- active-object context;
- multi-object selection;
- targeted playback;
- conjunction queue;
- conjunction ANALYZE workflow;
- exact TCA replay;
- pair framing and conjunction visualization.

The globe remains authoritative for interactive selection state to avoid React/Cesium state races.

### Earth visualization

High-resolution mode uses Cesium imagery and terrain.

OrbitalAI also provides:

- real solar illumination;
- day/night terminator;
- atmosphere lighting;
- local NASA Black Marble night-light texture;
- unlit emissive city-light rendering on the night hemisphere.

The experimental NASA Black Marble 500 m tiled/LOD implementation was rejected after regression testing. The stable local 3 km texture remains the current implementation.

## Orbital object semantics

Current visualization colors:

- `PAYLOAD` — cyan;
- `DEBRIS` — orange;
- `ROCKET_BODY` — yellow;
- `UNKNOWN / OTHER` — neutral white.

Object classification comes from catalogue metadata rather than ephemeris freshness.

## Ephemeris policy

Current freshness thresholds:

- warning: **12 hours**;
- stale: **24 hours**;
- maximum accepted age: **72 hours**.

Canonical source selection is shared by visualization and conjunction analysis so the globe and deterministic screening operate on the same data policy.

## Technology stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- SGP4 / Skyfield-based orbital processing
- SciPy / cKDTree conjunction screening

### Frontend

- Next.js 16
- React 19
- TypeScript
- CesiumJS
- Tailwind CSS

### Observability

- Prometheus
- Grafana
- Alertmanager
- Loki
- Grafana Alloy

### Deployment

- Docker Compose
- local-first Linux / WSL development environment

## Data sources

OrbitalAI currently integrates:

### SATCAT

Used for:

- object metadata;
- object type;
- launch information;
- operator / owner metadata;
- decay state;
- orbital catalogue classification.

### CelesTrak

Used as:

- public GP source;
- fallback orbital-element source;
- public catalogue bootstrap source.

### Space-Track

Used as:

- primary current GP source;
- preferred source in canonical ephemeris selection when eligible.

## Repository structure

```text
backend/          FastAPI application, services and persistence
frontend/         Next.js / CesiumJS Orbital Operations Workspace
ingestion/        external orbital-data providers
orbital_engine/   deterministic orbital and conjunction algorithms
workers/          ingestion, propagation and screening workers
scripts/          operational and maintenance commands
observability/    Prometheus, Grafana, Alertmanager, Loki and Alloy
deploy/           Docker Compose deployment
migrations/       Alembic database migrations
tests/            backend and observability tests
docs/             architecture and design documentation
data/             local runtime and cached orbital data
```

## Development validation

Backend tests:

```bash
pytest -q
```

Frontend type checking:

```bash
cd frontend
npx tsc --noEmit
```

Frontend lint:

```bash
npm run lint
```

Frontend production build:

```bash
npm run build
```

## Current v0.4F.1 development status

**Automated Catalog & Ephemeris Synchronization** is implemented on the
`feature/v0.4.0-automated-catalog-sync` branch. Its scope includes:

- automated SATCAT synchronization;
- automated CelesTrak synchronization;
- automated Space-Track synchronization;
- provider-specific schedules;
- synchronization locking;
- persistent last-run / last-success state;
- retry and backoff;
- Prometheus synchronization metrics;
- API synchronization-status endpoint;
- freshness visibility in the operations UI.

Default cadences:

- Space-Track: approximately every **1 hour**;
- CelesTrak: approximately every **2 hours**;
- SATCAT: approximately every **12 hours**.

The scheduler runs as the Compose `catalog-sync` service. Operational state is
available from `GET /catalog/sync-status`; Prometheus and the **Orbital
Operations Overview** dashboard expose bounded synchronization telemetry.

## Documentation

Architecture documentation is maintained under:

```text
docs/architecture/
```

The v0.4 Orbital Operations Workspace is documented in:

```text
docs/architecture/v0.4-orbital-operations-workspace.md
```

Automated catalog and ephemeris synchronization is documented in:

```text
docs/architecture/v0.4f1-automated-catalog-ephemeris-synchronization.md
```

Automated conjunction screening is documented in:

```text
docs/architecture/v0.4f2-automated-conjunction-screening.md
```

The optional local AI gateway foundation is documented in:

```text
docs/architecture/v0.5-local-ai-foundation.md
```

The fixed-input Conjunction Analyst Brief backend is documented in:

```text
docs/architecture/v0.5b1-conjunction-analyst-brief.md
```

## Project direction

OrbitalAI is evolving toward a sovereign orbital operations platform combining:

- deterministic orbital mechanics;
- scalable conjunction analysis;
- operator-focused 3D visualization;
- local observability;
- controlled local AI assistance.

The design principle remains simple:

> deterministic systems calculate the orbit; AI helps the human understand and prioritise what matters.

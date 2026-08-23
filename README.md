# School AI

School AI is a public-demo school activity and timetable management system built
with synthetic data.

The current implementation provides:

- SQLAlchemy 2.x models for teachers, student groups, rooms, activities, and
  teacher/room availability
- Pydantic schemas for validating and serializing those entities
- PostgreSQL configuration through `DATABASE_URL`
- A deterministic, database-independent OR-Tools CP-SAT scheduling engine with
  hard constraints for availability, resource conflicts, required sessions, and
  room suitability
- Application services and focused repositories that translate persisted school
  data into solver DTOs and persist successful results as versioned schedules
- pytest coverage using an in-memory SQLite database

The FastAPI application exposes read-only school data and the complete schedule
draft/version/publication workflow. AI and MCP integrations are planned but are
not yet implemented.

## Schedule lifecycle

A `Schedule` is the stable identity of a timetable. Every successful CP-SAT run
creates a new `ScheduleVersion` in `DRAFT` status and stores its assignments as
`ScheduledLesson` rows. Existing versions are not overwritten. Solver outcomes
that are `INFEASIBLE`, `UNKNOWN`, or contain no assignments do not create a
version or fabricated lessons; their diagnostic metadata is returned by the
application service.

Publishing is a separate explicit service operation. Publishing a draft marks
it `PUBLISHED` and marks the prior published version `SUPERSEDED`, ensuring at
most one current publication per schedule. Further changes require generating a
new draft rather than modifying a published lesson snapshot in place.

The project does not yet use a migration framework. Tests and current database
initialization use SQLAlchemy's `Base.metadata.create_all()`; production schema
migrations remain a future infrastructure milestone.

## Run the API locally

Install the project and development dependencies in a Python 3.12 virtual
environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Configure a PostgreSQL database whose tables have been initialized from the
current SQLAlchemy metadata, then start the ASGI application:

```bash
export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/school_ai'
.venv/bin/uvicorn school_ai.api.app:app --reload
```

Useful local URLs:

- Health check: `http://127.0.0.1:8000/health`
- Interactive API documentation: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Environment configuration:

- `DATABASE_URL`: PostgreSQL connection URL. Defaults to the local development
  database shown above.
- `APP_NAME` and `APP_VERSION`: OpenAPI application metadata.
- `APP_ENV`: environment label returned by the health endpoint.
- `ALLOWED_CORS_ORIGINS`: comma-separated origins. Localhost ports 3000 and
  5173 are allowed by default for development; production origins must be set
  explicitly.

A basic scheduling workflow is:

1. Read teachers, rooms, groups, activities, and availability.
2. `POST /schedules` to create a logical timetable.
3. `POST /schedules/{id}/drafts` with candidate time slots.
4. Inspect or compare versions under `/schedules/{id}/versions` and
   `/schedules/{id}/compare`.
5. Explicitly publish a draft with
   `POST /schedules/{id}/versions/{version_id}/publish`.

The API does not automatically create or migrate production tables. A migration
system and deployment workflow remain separate future milestones.

## Run the public demo UI locally

The demo frontend is a separate React, TypeScript, and Vite application under
`frontend/`. It communicates only with FastAPI and never accesses the database
or scheduler directly.

Seed an empty configured database with deterministic synthetic data and run the
backend:

```bash
export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/school_ai'
.venv/bin/python -m school_ai.demo_seed
.venv/bin/uvicorn school_ai.api.app:app --reload
```

In a second terminal, install frontend dependencies and start Vite:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

`VITE_API_BASE_URL` controls the backend URL and defaults to
`http://127.0.0.1:8000`. Do not place secrets in Vite environment variables;
they are compiled into browser assets. The default backend CORS settings permit
the local Vite origin at `http://localhost:5173`.

Open `http://localhost:5173` and follow the demo workflow:

1. Review synthetic teachers, rooms, groups, activities, and availability.
2. Generate a CP-SAT-backed draft from the Overview screen.
3. Inspect and filter the weekly timetable by group, teacher, or room.
4. Compare stored versions using backend-provided change classifications.
5. Explicitly publish a reviewed draft.

The UI remembers the logical demo schedule ID in browser local storage because
the API intentionally does not expose a global schedule-list endpoint yet.

Frontend verification commands:

```bash
cd frontend
npm test
npm run build
```

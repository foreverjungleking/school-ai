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

The FastAPI application exposes read-only school data, the complete schedule
draft/version/publication workflow, and a first controlled AI harness over an
approved MCP tool surface. The React UI does not include chat yet.

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

Database schema changes are managed with Alembic. Apply the current schema with
`alembic upgrade head`; application startup and demo seeding never drop tables
or silently rebuild the production database.

## Run the API locally

Install the project and development dependencies in a Python 3.12 virtual
environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Configure PostgreSQL, apply migrations, then start the ASGI application:

```bash
export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/school_ai'
.venv/bin/alembic upgrade head
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
- `MAX_SOLVE_SECONDS`: application-enforced upper bound for each CP-SAT request;
  defaults to 15 seconds.

A basic scheduling workflow is:

1. Read teachers, rooms, groups, activities, and availability.
2. `POST /schedules` to create a logical timetable.
3. `POST /schedules/{id}/drafts` with candidate time slots.
4. Inspect or compare versions under `/schedules/{id}/versions` and
   `/schedules/{id}/compare`.
5. Explicitly publish a draft with
   `POST /schedules/{id}/versions/{version_id}/publish`.

The API does not automatically create or migrate tables during startup.

## Run the public demo UI locally

The demo frontend is a separate React, TypeScript, and Vite application under
`frontend/`. It communicates only with FastAPI and never accesses the database
or scheduler directly.

Seed an empty configured database with deterministic synthetic data and run the
backend:

```bash
export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/school_ai'
.venv/bin/alembic upgrade head
.venv/bin/python -m school_ai.demo_seed
.venv/bin/uvicorn school_ai.api.app:app --reload
```

In an installed production environment the supported seed command is simply
`python -m school_ai.demo_seed`; no manual `PYTHONPATH` is required. Apply
migrations first. A draft request made before teachers, rooms, student groups,
and activities exist returns the structured `SCHEDULING_DATA_INCOMPLETE` error
instead of a generic validation failure.

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

## Railway deployment

The repository includes Railway configuration for a root FastAPI service and a
`frontend/` static service. PostgreSQL migrations, deterministic one-time demo
seeding, environment variables, custom-domain setup, and the production smoke
test are documented in [docs/deployment-railway.md](docs/deployment-railway.md).

## AI harness and MCP

`POST /ai/chat` invokes a provider-neutral harness. The model can select only
these MCP tools:

- `list_teachers`, `list_rooms`, `list_student_groups`, `list_activities`
- `get_schedule`, `get_schedule_version`, `get_published_schedule`
- `compare_schedule_versions`
- `create_schedule_draft`

The MCP adapter delegates to existing application services. It contains no
SQLAlchemy/session queries and constructs no CP-SAT model. There is deliberately
no publish tool: users must review and publish drafts through the existing
API/UI. `INFEASIBLE` and `UNKNOWN` solver outcomes are reported as failures and
never converted into a timetable.

Select a provider through environment variables. For local Ollama:

```bash
export AI_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=<installed-tool-capable-model>
```

For OpenAI's Responses API:

```bash
export AI_PROVIDER=openai
export OPENAI_API_KEY=<secret>
export OPENAI_MODEL=<tool-capable-model>
```

No OpenAI key is needed for Ollama or tests. Example request:

```bash
curl -X POST http://127.0.0.1:8000/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Show me the published schedule for schedule 1"}'
```

This first milestone performs at most one approved tool call per chat request
and uses an in-process MCP client boundary; the same tools can be registered on
the official MCP Python SDK server for a future external transport. Draft
generation currently requires the model to provide a schedule ID and explicit
candidate time slots. There is no UI chat, conversation memory, authentication,
streaming, RAG, autonomous publication, or multi-agent orchestration yet.

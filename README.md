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
draft/version/publication workflow, and a controlled AI harness over an
approved MCP tool surface. The React demo includes an AI Assistant page that
uses that harness without bypassing the normal schedule review workflow.

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
3. `POST /schedules/{id}/drafts`; omit `time_slots` to use the standard demo
   grid (Monday-Friday, hourly from 08:00 through 16:00), or supply custom
   candidate slots explicitly.
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
- `get_current_demo_schedule`, `get_schedule`, `get_schedule_version`,
  `get_published_schedule`
- `compare_schedule_versions`
- `create_schedule_draft`

The MCP adapter delegates to existing application services. It contains no
SQLAlchemy/session queries and constructs no CP-SAT model. There is deliberately
no publish tool: users must review and publish drafts through the existing
API/UI. `INFEASIBLE` and `UNKNOWN` solver outcomes are reported as failures and
never converted into a timetable.

The frontend AI Assistant sends typed requests to `POST /ai/chat` through the
same FastAPI base URL as the rest of the UI. It shows approved tool activity,
provider errors, and links a successfully generated draft to the existing
Versions review screen. It does not call Ollama or OpenAI from the browser and
does not add a publish capability. Suggested prompts omit schedule IDs so the
backend can resolve the current demo schedule through application services.

Select a provider through environment variables. The application does not
construct a provider during startup, so the deterministic API/UI remains
available when AI variables are absent. For deterministic, network-free local
smoke testing:

```bash
export AI_PROVIDER=fake
```

`FakeProvider` is scripted directly in automated tests to simulate tool calls;
the environment-selected instance returns a fixed informational response and
uses no credentials.

For a real local Ollama model, install Ollama separately and pull a model with
tool support (the application never downloads one automatically), then run:

```bash
ollama serve
ollama pull qwen2.5:3b
export AI_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=qwen2.5:3b
export DATABASE_URL=<your-local-database-url>
uvicorn school_ai.api.app:app --host 127.0.0.1 --port 8000
```

Run the frontend normally with `VITE_API_BASE_URL` pointing to FastAPI. The
request path remains Browser → FastAPI → Ollama; never configure the browser to
contact port 11434 directly.

Before the smoke test, run `alembic upgrade head` and
`python -m school_ai.demo_seed` against that `DATABASE_URL`. Create a logical
schedule with `POST /schedules` if the database has none. The published-read
case naturally requires a version previously published through the normal
REST/UI workflow; the AI is intentionally unable to publish it.

In another terminal, run the opt-in end-to-end smoke test (it is deliberately
not part of pytest):

```bash
SCHOOL_AI_API_URL=http://127.0.0.1:8000 \
  python scripts/ollama_smoke.py
```

The four prompts should respectively produce no required factual tool, then
`list_teachers`, `get_published_schedule`, and `create_schedule_draft` (the
model may first call `get_current_demo_schedule`). For additional manual chat
coverage:

```bash
curl -X POST http://127.0.0.1:8000/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Compare the newest draft with the published schedule."}'
```

The newest logical schedule is the single-school demo's “current” schedule.
The scheduling service—not the model—resolves it and constructs the standard
candidate slots. Custom slots remain available through the deterministic REST
API.

For OpenAI's Responses API:

```bash
export AI_PROVIDER=openai
export OPENAI_API_KEY=<secret>
export OPENAI_MODEL=<tool-capable-model>
```

`OPENAI_API_KEY` is read only when `AI_PROVIDER=openai`; selecting OpenAI
without it returns `AI_PROVIDER_NOT_CONFIGURED` from `/ai/chat` and does not
prevent FastAPI startup. No OpenAI key is needed for FakeProvider, Ollama, or
tests. Example request:

```bash
curl -X POST http://127.0.0.1:8000/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Show me the published schedule for schedule 1"}'
```

The harness performs at most four sequential approved tool calls per
chat request and uses an in-process MCP client boundary; the same tools can be
registered on the official MCP Python SDK server for a future external
transport. Each requested name and its arguments are validated before
execution. Draft
generation accepts an optional schedule ID and always obtains candidate slots
from the scheduling service. Ollama uses native tools first and falls back to a
strict Pydantic-validated JSON response schema; malformed JSON fails safely.
The UI limits message length and disables duplicate submission while a request
is running. These are usability controls, not security controls. There is no
user authentication, per-user session ownership, persistent conversation
memory, server-side AI rate limiting, streaming, RAG, autonomous publication,
or multi-agent orchestration yet. Server-side rate limiting and session
isolation are required before broad public AI exposure.

# Architecture

## Core Application

```text
Browser/UI ---> FastAPI --------------------+
                                             |
User ---> AI Harness                         +--> Application Services
           +-- LLM Provider                  |          /       \
           +-- MCP Client                    |         v         v
                 |                           |   Repositories   CP-SAT
                 v                           |         |
           School MCP Server ----------------+         v
                                                   PostgreSQL
```

Application services own orchestration and transaction boundaries. Repositories
contain SQLAlchemy queries and persistence operations but no scheduling logic.
The scheduler interface accepts and returns in-memory DTOs and contains no
database logic. PostgreSQL is the source of truth for application state, while
the OR-Tools CP-SAT scheduler is the authoritative scheduling engine. Future
API, MCP, and UI adapters must call application services rather than database or
solver internals. FastAPI and MCP are parallel adapters over the same service
capabilities.

FastAPI is a presentation adapter. Routes validate public request schemas, call
application services, and translate service outcomes to HTTP responses; they do
not query SQLAlchemy or construct CP-SAT models directly. Read-only school-data
queries also pass through a dedicated application service. Database sessions
are request-scoped dependencies, while schedule generation and publication
transactions remain owned by the scheduling application service. MCP tools use
these same services in parallel with FastAPI.

The demo UI is a separately built React/TypeScript application. Its typed API
client is the only browser-side capability boundary: components do not query
PostgreSQL, construct solver models, or reproduce schedule lifecycle and version
comparison rules. FastAPI remains responsible for public validation and HTTP
mapping, while application services remain responsible for scheduling,
persistence transactions, publication, and comparison.

The AI Assistant is a dedicated, non-dominant UI screen. It calls only the
typed FastAPI `POST /ai/chat` client and displays the returned assistant text
and approved tool-execution summary. A successful draft response triggers a
fresh read of the affected schedule/version state and links to the existing
Versions screen; publication is never offered through chat. Provider failure
is isolated to the assistant screen, so deterministic scheduling remains
usable. Browser code never connects directly to an LLM provider or receives
provider credentials.

The browser prepares a standard weekday/hour candidate-slot template for the
existing draft-generation endpoint. CP-SAT remains authoritative about whether
those inputs produce a valid timetable. `INFEASIBLE` and `UNKNOWN` responses are
shown as failures and never rendered as timetable data.

API configuration is loaded from environment variables. The application factory
owns the configured database engine/session factory and closes the engine during
ASGI shutdown. CORS uses an explicit configurable origin list, with only common
localhost development origins enabled by default.

In production, Railway runs the built React assets and FastAPI as separate
services. Browser traffic reaches the backend over its public HTTPS origin;
only FastAPI connects to PostgreSQL over Railway private networking. Alembic is
the production schema authority and runs before a backend deployment starts.
Neither API startup nor demo seeding creates, drops, or resets schema objects.

## AI and MCP Integration

```text
AI Harness
  |
  +------ LLM Provider
  |         +-- Ollama
  |         +-- OpenAI
  |         +-- vLLM
  |
  +------ MCP Client
            |
            +-- School MCP Server
                  |
                  +-- Application Services
                        /          \
                       v            v
                 Repositories    CP-SAT
```

The AI harness accesses Ollama or OpenAI through a small provider interface and
uses a replaceable MCP client. The first client runs in-process, while the same
approved tool functions can be registered with the official MCP SDK server.
This keeps protocol transport separate from application capabilities.

The MCP adapter delegates to `SchoolDataService`, `SchedulingService`, and
`PolicyService`;
it has no SQLAlchemy session, SQL, repository, or CP-SAT construction logic.
Eleven read tools expose school/schedule data, current-demo schedule discovery,
and comparison. The sole write tool asks the scheduling service to create a
CP-SAT-backed `DRAFT`. The service resolves an omitted schedule ID to the newest
logical demo schedule and owns the standard candidate time-slot grid. No publish
tool is registered. A user must publish separately through the existing REST/UI
flow.

The harness executes a bounded loop of at most four allow-listed tool calls,
validates every tool name and argument payload, and asks the provider to
summarize structured results. A deterministic FakeProvider supports tests with
no network or credentials; Ollama is the local real-model option, while the
OpenAI adapter is configured only when explicitly selected. Solver `INFEASIBLE`
or `UNKNOWN` outcomes bypass model summarization and produce a deterministic
no-draft response, preventing fabricated success. Arbitrary tool names,
additional tool calls, SQL access, direct lesson edits, constraint changes, and
autonomous publishing are rejected by construction. RAG retrieves versioned
unstructured policy excerpts from PostgreSQL; structured
school and timetable facts remain service-backed tool reads.

Ollama attempts its native function-call format first. When a model returns no
native call, the adapter makes a schema-constrained fallback request using the
same provider-neutral `ProviderTurn` JSON contract, temperature zero, strict
Pydantic validation, and no dynamic code execution. Only tools relevant to the
current request are sent when they can be identified cheaply. Full lesson lists
remain in the structured API result but use counts and bounded previews in the
model context. Filtered lesson pages are available through `get_schedule_lessons`.

Chat requests optionally belong to token-owned conversations. PostgreSQL stores
original exchanges and bounded provider-generated summaries; the browser
restores history using a private token, whose hash is stored server-side.
Atomic leases and revision checks serialize turns across processes. Summary
and history data are untrusted context. Conversations do not provide account
authentication or ownership of the shared demo timetable. Public server-side
rate limiting and schedule isolation remain separate requirements.

## Source Layout

- `src/school_ai/database/` contains persistence-related components.
- `src/school_ai/services/` contains application services.
- `src/school_ai/solver/` contains scheduling and optimization components.
- `src/school_ai/ai/` contains provider-neutral harness orchestration.
- `src/school_ai/mcp/` contains the approved service adapter and MCP client/server boundaries.

## Scheduling Engine

The solver accepts validated, in-memory DTOs and has no dependency on database
sessions or web frameworks. Candidate assignments are represented by optional
fixed CP-SAT intervals. Each activity selects its required number of candidates, and
teacher, student-group, and room calendars each use hard `NoOverlap`
constraints. Availability and room suitability are enforced when candidates
are created; constraints are never relaxed to obtain a result.

Teacher and room availability use these explicit semantics:

- No availability records means the resource is unrestricted.
- One or more `available=True` records form a global whitelist. A session must
  fit completely inside a whitelist window, including matching its weekday.
- `available=False` records are blackout periods. Any overlap with a blackout
  rejects the session, even when an available window also covers it.

Time slots are same-day candidate windows: their end must be later than their
start, and an activity must fit completely within the selected slot. Activities
may start or end exactly on slot and availability boundaries. Resource conflict
constraints operate on the activity's actual interval, so differently
identified or partially overlapping slots still conflict.

Scheduling problems must contain at least one teacher, student group, room,
activity, and time slot. Identifiers must be unique within each collection, and
activities must reference a teacher and student group in the problem. These
requirements align the solver boundary with the existing domain model.

## Schedule Persistence

`Schedule` provides a logical timetable identity. Each valid solver result is
stored as a new `ScheduleVersion` with a monotonically increasing version number
and a complete set of `ScheduledLesson` assignment snapshots. Candidate time
slots are supplied to the application service; teachers, groups, rooms,
activities, and availability are loaded through the scheduling-data repository
and translated into `SchedulingProblem` DTOs before CP-SAT is invoked.

New solver results are always `DRAFT`. Publication is an explicit application
service transition, never an in-place edit of a published lesson snapshot. When
a new draft is published, the previous `PUBLISHED` version becomes
`SUPERSEDED`. Service logic and a database partial unique index enforce at most
one currently published version per schedule. `INFEASIBLE`, `UNKNOWN`, and
assignment-free outcomes return solver diagnostics without persisting a version
or lessons.

The schedule repository provides focused schedule/version queries and writes;
it does not implement constraints or call CP-SAT. Version comparison is
application logic keyed by `(activity_id, session_index)` and reports unchanged,
added, removed, and changed assignments for future presentation layers.

Alembic migrations represent the complete persistence schema and are applied
with `alembic upgrade head`. The initial migration is safe for an empty
production database and later revisions must evolve it without deleting user
data during normal deployment.

The explicit, idempotent `school_ai.demo_seed` utility adds deterministic
synthetic school resources only after migrations have been applied. It is an
infrastructure/demo helper outside the solver and service business logic,
preserves a fully seeded database, and refuses partially populated datasets.

## Weekly distribution objective

The solver now optimizes soft preferences after enforcing all resource,
availability, room suitability, and weekly session-count constraints. Its
objective sums each group's maximum-minus-minimum daily teaching minutes over
candidate weekdays, plus each activity's repeated daily sessions beyond the
first multiplied by that activity's duration. Both components have equal weight
in minutes. A score of zero means equal daily loads and no repeated subject
within a day; it is not a measure of every aspect of school timetable quality.
Restricted availability can legitimately require a positive score. `FEASIBLE`
means the time limit allowed a valid solution without proving optimality.

There is one optional interval per activity/slot/room candidate, and exactly
`sessions_per_week` candidates are selected per activity. Interchangeable
session numbers are assigned chronologically after solving, avoiding equivalent
permutations in the search. This preserves the hard no-overlap rules and makes
larger weekly demo problems practical with a single search worker. Comparisons
with older versions may reflect the old solver's arbitrary session numbering.

The expanded synthetic seed models 25 lessons per class per week and protects
lunch through structured teacher/room availability. The explicit `--expand`
operation updates known demo master data while preserving stored lesson
snapshots; it does not publish or rewrite a timetable version.

## Conversation context and policy retrieval

`ConversationService` owns short PostgreSQL transactions for access checks,
turn leases, history, and summary commits. `ConversationRepository` implements
persistence only. `AIHarness` builds bounded context and calls the same provider
abstraction for replies; compression also uses that abstraction, with no tools
available during summarization. Provider outages preserve valid memory.

`PolicyService` ingests local synthetic Markdown, chunks it by section, retains
content versions, and ranks matching excerpts. `PolicyRepository` queries only
current versions, using PostgreSQL full-text candidate retrieval (SQLite lexical
fallback for tests). `search_school_policies` is a thin MCP adapter. The UI
renders sources from tool metadata rather than trusting model-generated links.

`get_schedule_lessons` delegates filtering and pagination to the scheduling
service, allowing precise assignment reads without including full timetable
snapshots in every prompt. The LLM cannot change constraints or publish through
these tools. See [AI context and RAG](ai-context-plan.md) for protocol, budget,
retention, concurrency, and failure semantics.

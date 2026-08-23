# Architecture

## Core Application

```text
User
  |
  v
FastAPI / UI
  |
  v
Application Services
  |
  +------ PostgreSQL
  |
  +------ CP-SAT Scheduler
```

Application services coordinate the system. PostgreSQL is the source of truth for application state, while the OR-Tools CP-SAT scheduler is the authoritative scheduling engine.

## Planned AI Integration

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
                  +-- CP-SAT
                  +-- RAG
```

The AI harness will access language models through a provider abstraction. Ollama is the initial provider; OpenAI and OpenAI-compatible local servers such as vLLM may be added later.

The School MCP Server will expose application capabilities to AI agents. Its adapters will delegate to application services and contain no core business logic. RAG will be limited to unstructured policies and documents. The LLM may assist users and propose inputs, but it will never generate the final timetable; final schedules remain the responsibility of CP-SAT.

## Source Layout

- `src/school_ai/database/` contains persistence-related components.
- `src/school_ai/services/` contains application services.
- `src/school_ai/solver/` contains scheduling and optimization components.

## Scheduling Engine

The solver accepts validated, in-memory DTOs and has no dependency on database
sessions or web frameworks. Candidate assignments are represented by optional
fixed CP-SAT intervals. Required sessions select exactly one candidate, and
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

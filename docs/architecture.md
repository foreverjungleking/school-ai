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

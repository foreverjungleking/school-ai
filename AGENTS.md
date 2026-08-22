# Repository Guidelines

## Project Goal

Build a public-demo AI-assisted school activity and timetable management system using synthetic data.

## Architecture Rules

1. OR-Tools CP-SAT is the authoritative scheduling engine.
2. The LLM must never directly generate the final timetable.
3. PostgreSQL is the source of truth for application state.
4. RAG is used only for unstructured policies and documents.
5. MCP exposes application capabilities to AI agents.
6. MCP adapters must contain no core business logic.
7. All LLM access must go through a provider abstraction.
8. The initial LLM provider will be Ollama.
9. Future providers may include OpenAI and OpenAI-compatible local servers such as vLLM.
10. Schedule changes must create a draft version before publication.
11. Use synthetic or public demo data only.
12. Add automated tests for scheduling constraints.
13. Do not introduce LangChain, LangGraph, multi-agent frameworks, or other large AI frameworks unless explicitly requested.

## Technology

- Python 3.12
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- OR-Tools CP-SAT
- pytest
- MCP Python SDK (later)
- Ollama (initially)

## Repository Layout

- Keep application code under `src/school_ai/`.
- Keep automated tests under `tests/`.
- Keep demonstration data under `demo_data/`.
- Document architectural decisions in `docs/architecture.md`.

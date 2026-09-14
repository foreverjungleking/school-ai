# Policy RAG and compressed conversation memory

Implemented alongside the expanded weekly scheduling demo. PostgreSQL stores
conversation history, summaries, and versioned policy chunks. The LLM provider
interface and service-backed MCP boundary remain unchanged in responsibility.

## Conversation lifecycle

`POST /ai/conversations` returns an opaque `id` and a random `access_token` once.
Only the SHA-256 token hash is stored in PostgreSQL. The assistant stores the
credential in browser local storage and sends it in `X-Conversation-Token`.
A conversation ID alone grants no access. Credentials are not supplied to the
LLM or exposed by MCP. Responses containing history/credentials are marked
`Cache-Control: no-store`.

- `POST /ai/chat` accepts `message` and optional `conversation_id`. With an ID,
  the token header is required; without one, the original stateless behavior
  remains supported.
- `GET /ai/conversations/{id}` restores the latest 50 complete exchanges and
  indicates whether earlier exchanges exist.
- `POST /ai/conversations/{id}/reset` deletes all exchanges and the summary for
  that conversation. The UI exposes this as **Clear conversation**.

Original exchanges are retained until explicitly cleared; compression does not
delete them. Losing the browser credential loses access to that history. There
is no cross-device account recovery or automatic retention cleanup yet.
Conversation ownership protects chat history, not the existing shared demo
school data or schedule/publication endpoints. Server-side public rate limits
and school/schedule ownership remain separate deployment work.

Each turn claims an atomic database lease. Competing requests and resets return
409 while a turn is active. A ten-minute lease permits recovery after a process
crash; heartbeats precede model/tool actions, and completion checks both lease
and revision. The model loop has a five-minute deadline, with a separate
30-second compression deadline. No conversation transaction remains open across
LLM calls. MCP service sessions are also released after each tool action.
Provider failure before any tool action leaves no fabricated completed turn.
A successful tool action followed by a provider-response failure is returned
with a deterministic fallback and its actual tool metadata. A process crash or
overall timeout after a committed draft can still leave that draft in Versions;
check Versions before retrying a timed-out write.

## Context and compression

The harness assembles invariant system instructions, a clearly labeled untrusted
summary, recent exchanges, the current question, and bounded live tool results.
Historical schedule/version IDs help resolve references; publication and other
mutable facts must be refreshed through read tools. Follow-ups retain the read
tool surface rather than relying on keywords from only the latest message.

Defaults, configurable on the backend:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AI_CONTEXT_MAX_BYTES` | `48000` | Bound the provider-neutral message/tool-schema envelope |
| `AI_SUMMARY_MAX_BYTES` | `4000` | Maximum validated summary UTF-8 bytes |
| `AI_RECENT_TURNS` | `3` | Recent complete exchanges retained before byte-budget pruning |

The byte budget is not an exact model-token count. The harness reserves 6,000
bytes for protocol/response headroom; provider-specific framing and actual
output token limits are still provider concerns. Original history is not sent
in full. If necessary, older context is omitted to retain the system prompt,
current question and latest tool result; an oversized mandatory envelope is
rejected instead of silently truncating the current question.

Once history exceeds the recent-turn window, the same `LLMProvider` compresses
older complete turns into concise text, wrapped in a validated JSON memory
record (`summary`, `references`). This avoids requiring small local models to
generate nested JSON; structured JSON summaries are accepted too. The summary
and source sequence cursor commit atomically with the completed reply. Empty, invalid structured,
oversized, tool-requesting, or timed-out compression preserves the previous
summary and cursor. The reply can retain older raw exchanges within the byte
budget as well as recent context and reports
`compression_failed`; original messages remain intact. A compression batch is
bounded, so a large backlog may require more than one subsequent turn to catch
up. Summaries remain fallible derived context, never authoritative schedule
state or permission to act.

`get_schedule_lessons` provides filtered, chronological pages of up to 20 actual
lessons, with `matched_count` and `next_offset`. Filters include weekday, group,
teacher and room. An omitted version selects the current publication; an
explicit version reads that snapshot. General version responses still use small
previews, but this focused tool keeps its page of assignments in model context.

## Policy retrieval and citations

The explicit ingestion command reads synthetic Markdown files from
`demo_data/policies/`:

```bash
PYTHONPATH=src python -m school_ai.policy_seed demo_data/policies
```

Each source filename has a current SHA-256 content version. Chunks preserve
title, section, version and source filename, with at most 1,200 UTF-8 bytes of
body text each. Re-ingestion is idempotent. Replaced versions stop appearing in
current searches, while old chunks remain available as evidence for stored
citation snapshots. Ingestion is transactional per document and accepts local
Markdown files of at most 200,000 bytes; it does not fetch URLs.

The thin `search_school_policies` MCP adapter calls `PolicyService`. PostgreSQL
full-text search produces lexical candidates; SQLite provides a deterministic
lexical fallback for unit tests. Matching terms rank a bounded candidate set,
and the tool returns at most four excerpts. This is lexical RAG, not embedding
or semantic similarity search. No external vector database or model download
is required. It works best with the English synthetic documents provided.

Explicit policy/rule/lunch questions trigger retrieval before generation.
Other questions can use the search tool through normal model selection. Empty
retrieval yields a deterministic no-source response. Returned citations include
source, title, section, content version, excerpt and an ID such as
`policy:1:012345abcdef:2`. The system prompt requests inline citations. Only
IDs retrieved in the current turn are accepted as policy references; unknown
`[policy:...]` references are replaced with `[unverified source]`. The UI shows
expandable **Policy sources consulted** with the exact returned excerpts and
versions, independently of whether the model cited each one correctly.

Policy text and summaries are untrusted data. They cannot register tools,
execute SQL, change solver constraints, or publish a timetable. Each tool call
must be in the current request's offered tool set; draft generation is omitted
unless the current message contains an explicit creation verb. This English
verb filter is a conservative routing guard, not a general natural-language
intent verifier. Document instructions alone cannot add draft generation to a
policy-only request. Natural-language policy changes still require a separate
validated structured implementation before they can affect CP-SAT.

## Validation and local smoke test

`tests/test_ai_context.py` covers conversation access, restart persistence,
concurrent claims, expired workers, compression fallback, source versioning,
no-match responses, malicious document instructions, filtered lesson reads,
and non-destructive migration upgrades. It runs on SQLite by default and also
on PostgreSQL when `TEST_POSTGRES_URL` is supplied. PostgreSQL tests create and
drop unique temporary schemas; the account must be permitted to create schemas.
Never point this test setting at production.

```bash
.venv/bin/pytest
TEST_POSTGRES_URL='postgresql+psycopg://user:password@localhost/test_db' \
  .venv/bin/pytest tests/test_ai_context.py
cd frontend
npm test
npm run build
```

For an installed local Ollama model, the opt-in smoke script uses disposable
SQLite data and exercises a real policy answer and compressed memory recall:

```bash
OLLAMA_MODEL=qwen2.5:3b PYTHONPATH=src \
  .venv/bin/python scripts/ai_context_smoke.py
```

It uses `OLLAMA_BASE_URL` (default `http://localhost:11434`), never downloads a
model, and does not modify the application's database.

# API Contract: Tutor Agent

**Feature**: `012-tutor-agent` | **Date**: 2026-08-23

Adds a new `backend` REST surface for opening/using a Tutoring Session,
and a new internal A2A contract between the `backend` and the new
`tutor-agent/` service. `backend` is the sole orchestrator
(research.md §2) -- `tutor-agent/` exposes exactly one A2A method and
holds no state of its own.

## `POST /api/tutor/sessions` (NEW)

Opens a Tutoring Session for a learner -- **get-or-create** (FR-014).
Auth: `current_guardian` (guardian-mediated, targeting one of that
guardian's own real learners -- same ownership check pattern as
Milestone 8's assigned-quiz attempt start) or the demo-learner path
(matching every other demo-learner-exclusive endpoint).

**Request**:
```json
{ "learner_id": "...", "subject_id": "biology" }
```

**Response** `201` -- a new session was created (no existing active
session for this `learner_id`/`subject_id` pair):
```json
{ "session_id": "...", "subject_id": "biology", "status": "active" }
```

**Response** `200` -- an active session for this `learner_id`/
`subject_id` pair already existed; that same session is returned
rather than creating a duplicate (FR-014, enforced by the partial
unique index in data-model.md -- this branch also covers the race
where a concurrent second request loses the DB-level uniqueness
check).

**Response** `403` -- learner not owned by the calling guardian (FR-001,
same ownership-check shape as `quiz_assignments`' guardian check).

## `POST /api/tutor/sessions/{session_id}/messages` (NEW, streaming)

Submits a learner's question and streams the Tutor Agent's answer back
token-by-token (FR-005). A `Response`/`StreamingResponse` endpoint, not
a single JSON body -- the frontend reads it via the browser's streaming
`fetch`, matching `tech-stack.md`'s locked streaming choice.

**Request**:
```json
{ "question": "why does photosynthesis need light?" }
```

**Server steps before the first byte is streamed** (all synchronous,
counted in SC-001's first-token budget):
1. Reject if this session already has an in-flight exchange
   (`answer_text IS NULL`) -- FR-015, cheapest check, done first.
2. Rate-limit check (FR-013) -- a DB query counting this learner's
   `tutor_exchanges` in the trailing 10-minute window
   (research.md §8/data-model.md), same shape as spec 007's
   `check_rate_limit`.
3. Length cap + moderation check on `question` (reuse of the existing
   backend-owned guardrail pattern, per `tech-stack.md`'s Principle IV
   table).
4. `pgvector` similarity search over `content_passage_embeddings`
   scoped to the session's `subject_id` (research.md §2, §5).
5. If the question needs the learner's own performance context
   (FR-006) -- an in-process call to the existing Recommendation/
   Sequencing services, no network hop.
6. Bundle question + retrieved passages + any delegation context into
   the A2A request below and open the stream from `tutor-agent/`.

**Streamed response** (`text/event-stream`, one `data:` line per
token/chunk from the Tutor Agent's own A2A stream, proxied through
unmodified):
```text
data: {"delta": "Light"}
data: {"delta": " provides"}
data: {"delta": " the energy..."}
data: {"done": true}
```

**Response** `409` -- **still answering** (FR-015, checked first, before
rate limit/length/moderation/retrieval):
```json
{ "error": "still_answering", "exchange_id": "..." }
```

**Response** `429` -- **rate limited** (FR-013, same shape as spec
007's `rate_limited`):
```json
{ "error": "rate_limited", "retry_after_seconds": 137 }
```

**Response** `422` -- **question too long / moderation rejected**
(same two-state shape as spec 007's `answer_too_long`/
`moderation_rejected`, checked before any retrieval or A2A call):
```json
{ "error": "question_too_long", "max_length": 2000 }
```
```json
{ "error": "moderation_rejected" }
```

**Response** `503` -- **tutor unavailable** (Tutor Agent A2A call
failed after retry, mirroring `grading_unavailable`'s shape):
```json
{ "error": "tutor_unavailable" }
```

**Error-state ordering**: in-flight check first (cheapest, one query
against a row already implied by the session), then rate limit (one DB
query), then length/moderation (no DB query, one LLM call), then
retrieval/delegation, then the A2A call itself -- mirrors spec 007's
own ordering rationale (cheapest, most-likely-to-reject checks first).

**After the stream completes** (server-side, not learner-visible): the
backend writes the `TutorExchange` row (`answer_text`, `grounded`,
`retrieved_passage_ids`, `delegation_context`) and the
`tutor_exchange_completed` `AssessmentEvent` (data-model.md), and
flushes the Langfuse span (FR-008, `tech-stack.md`'s serverless
flush-before-return requirement).

## `GET /api/tutor/exchanges/{exchange_id}` (NEW)

User Story 3's inspection endpoint. Auth: the owning guardian, the
learner's enrolled-classroom instructor (same enrollment-scoped access
`content_review` already uses), or the demo-instructor session.

**Response** `200`:
```json
{
  "exchange_id": "...",
  "question_text": "why does photosynthesis need light?",
  "answer_text": "Light provides the energy...",
  "grounded": true,
  "retrieved_passages": [
    {
      "passage_id": "...",
      "topic_id": "photosynthesis",
      "field": "skill_summary",
      "text": "..."
    }
  ],
  "delegation_context": { "weak_areas": ["..."] }
}
```

## Internal contract: backend -> Tutor Agent (A2A)

Per Constitution Principle VI, `tutor-agent/` is a network-reachable
A2A service and MUST authenticate every inbound request before its own
guardrails or the backend's can be assumed to apply. Every request
carries a shared secret in `X-Tutor-Agent-Secret`, checked by
`tutor-agent/src/agent.py`'s ASGI middleware before A2A routing --
same shape as `grading-agent`'s `X-Grading-Agent-Secret`
(`tech-stack.md`'s A2A inbound authentication row), with its own
distinct secret (`TUTOR_AGENT_SHARED_SECRET` /
`TUTOR_AGENT_SHARED_SECRET_NEXT` for rotation).

**Leaked-secret compensating control**: `tutor-agent/` re-checks a
total request-length cap and re-runs content moderation on the raw
question text itself, in addition to shared-secret auth -- same
compensating-control shape `tech-stack.md` already locks for Grading
Agent.

**Request** (A2A `message/stream`, JSON content):
```json
{
  "question": "why does photosynthesis need light?",
  "subject_id": "biology",
  "retrieved_passages": [
    { "passage_id": "...", "topic_id": "photosynthesis", "field": "skill_summary", "text": "..." }
  ],
  "delegation_context": { "weak_areas": ["cell-transport"] }
}
```

**Streamed response** (A2A `message/stream` chunks): incremental text
deltas, terminated by a final chunk indicating completion and which
`retrieved_passages` (by `passage_id`) the answer actually grounded in
-- this is what the backend persists as `TutorExchange.grounded`/
`retrieved_passage_ids` is filtered down to (a passage can be *offered*
without being *used*; only used ones count for SC-002).

**Tracing**: the outbound A2A call is wrapped in the existing
Langfuse/OpenInference ADK instrumentation, spans flushed before the
backend's own streaming response completes (FR-008).

**Deployment**: `tutor-agent/` is built via ADK's `to_a2a()`, deriving
`host`/`protocol`/`port=443` from Vercel's `VERCEL_BRANCH_URL`/
`VERCEL_URL` exactly as `grading-agent/src/agent.py`'s
`_to_a2a_kwargs` already does (research.md §7) -- not left at
`to_a2a()`'s `localhost:8000` default.

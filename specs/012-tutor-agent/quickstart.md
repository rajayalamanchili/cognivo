# Quickstart: Tutor Agent

**Feature**: `012-tutor-agent` | **Date**: 2026-08-23

Validates the full ask -> retrieval-grounded, streamed answer ->
inspectable-delegation round trip against the already-deployed
Milestones 1-8 backend plus this feature's new tables, routes, and
standalone `tutor-agent/` A2A service. See `data-model.md` for entity
detail and `contracts/api.md` for exact request/response shapes.

## Prerequisites

- Same as `specs/011-instructor-assigned-quizzes/quickstart.md`, plus:
  - This feature's migration applied (`alembic upgrade head` -- adds
    the `pgvector` extension, `content_passage_embeddings`,
    `tutoring_sessions`, `tutor_exchanges`, and the
    `tutor_exchange_completed` event type).
  - Content-artifact embeddings generated for at least one subject
    (re-run `scripts/load_content_artifact.py` for `biology` or
    `algebra-1` after this feature's loader extension ships --
    research.md §5/data-model.md).
  - `tutor-agent/` running locally (`uv run uvicorn src.agent:app
    --port 8002`, matching `grading-agent/`'s own quickstart pattern)
    or deployed, with `TUTOR_AGENT_URL`/`TUTOR_AGENT_SHARED_SECRET` set
    on the backend to match.
  - `VOYAGE_API_KEY` set (research.md §1).

## Validation scenario 1: grounded, streamed answer to a subject question

As a guardian with an enrolled real learner (or via the demo-learner
path), `POST /api/tutor/sessions` with that learner's `learner_id` and
`subject_id: "biology"` -> `201`. `POST /api/tutor/sessions/{session_id}
/messages` with `{"question": "why does photosynthesis need light?"}`.
Confirm the response arrives as multiple `data:` chunks (not one
buffered payload) and that `GET /api/tutor/exchanges/{exchange_id}`
afterward shows `grounded: true` with at least one
`retrieved_passages` entry whose `topic_id` matches the biology content
artifact's photosynthesis topic.

## Validation scenario 2: honest non-grounded answer

Ask a question with no plausible match in any loaded content artifact
(e.g. "what's the capital of France?"). Confirm the streamed answer
itself says it isn't grounded in this platform's material, and
`GET /api/tutor/exchanges/{exchange_id}` shows `grounded: false` with
`retrieved_passages: []` -- not a partial/low-confidence match silently
presented as sourced (FR-004).

## Validation scenario 3: answer reflects the learner's real mastery state

Using a learner with a known "struggling" topic (seed one via the
existing placement/quiz flow if needed), ask "what should I work on?"
Confirm the answer names that actual topic, and
`GET /api/tutor/exchanges/{exchange_id}`'s `delegation_context` shows
the same topic came from the Recommendation Agent's real output, not
free-form generation (FR-006). Repeat with a brand-new learner with no
answer history -- confirm the answer honestly says there's not enough
data yet rather than inventing a weak area (spec.md US2 scenario 2).

## Validation scenario 4: inspecting a past exchange (User Story 3)

As the learner's enrolled-classroom instructor (not the guardian who
asked), `GET /api/tutor/exchanges/{exchange_id}` for an exchange from
scenario 1 or 3. Confirm the full retrieved-passage list and
delegation context are visible without needing to ask the Tutor Agent
itself -- this is the same data an engineer would use to answer "why
did the Tutor say that" after the fact (FR-007/SC-003).

## Validation scenario 5: A2A auth and guardrails hold under a leaked/missing secret

Call `tutor-agent/`'s A2A endpoint directly (bypassing the backend)
with no `X-Tutor-Agent-Secret` header -> confirm rejection before any
model call. With a valid secret but an over-length or moderation-
flagged `question` in the request body -> confirm `tutor-agent/`'s own
compensating guardrail rejects it independently of the backend's own
pre-check (`tech-stack.md`'s leaked-secret compensating-control row;
contracts/api.md's internal contract).

## Validation scenario 6: session reuse, in-flight rejection, and rate limiting

`POST /api/tutor/sessions` twice in a row for the same `learner_id`/
`subject_id` -> confirm the second call returns `200` with the *same*
`session_id` as the first's `201` (FR-014). While a message is still
streaming, `POST` a second message to the same session -> confirm
`409 still_answering` (FR-015). Submit questions past the rate-limit
threshold within the trailing window -> confirm `429 rate_limited`
with a `retry_after_seconds` that shrinks on a later retry, same shape
as spec 007's existing rate-limit behavior (FR-013).

## Validation scenario 7: regression -- Milestones 1-8 unaffected

Run the full backend suite (`uv run pytest`) against a real, freshly
migrated dev database. Confirm nothing outside this feature's own new
files changed behavior (SC-005) -- in particular, `GET /api/
recommendation/{learner_id}` and the Sequencing Agent's existing
next-question selection are untouched; the Tutor Agent only *reads*
their output.

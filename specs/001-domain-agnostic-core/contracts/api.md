# API Contract: Domain-Agnostic Core

**Feature**: `001-domain-agnostic-core` | **Date**: 2026-08-15

FastAPI backend, deployed as a Vercel Python Function
(`tech-stack.md`). All endpoints are stateless per-request -- no session
state assumed to survive between calls beyond what's persisted to
Postgres (FR-013). All request/response bodies are JSON.

## `POST /api/subjects/{subject_id}/placement/start`

Starts a new placement session for the demo learner on a subject.

**Path params**: `subject_id` (`algebra-1` | `biology`)

**Response** `200`:
```json
{
  "placement_session_id": "uuid",
  "questions": [
    {
      "question_id": "uuid",
      "topic_id": "string",
      "question_type": "multiple_choice | numeric",
      "stem": "string",
      "options": ["string", "..."]
    }
  ]
}
```
One question per entry-level topic (FR-003) -- `answer_key` is never
included in this response.

**Errors**: `404` if `subject_id` unknown or not `validated_at` (FR-002).

---

## `POST /api/placement/{placement_session_id}/submit`

Submits all placement answers at once and triggers the initial mastery
computation.

**Request**:
```json
{
  "answers": [
    { "question_id": "uuid", "response": "string | number" }
  ]
}
```

**Response** `200`:
```json
{
  "mastery_state": [
    {
      "topic_id": "string",
      "status": "unknown | scored",
      "p_mastery": 0.0,
      "band": "struggling | developing | mastered"
    }
  ]
}
```
Topics not covered by placement appear with `"status": "unknown"` and no
`p_mastery`/`band` (FR-005) -- never a default numeric value. This
response is deterministic given identical `answers` (SC-001).

**Errors**: `409` if already submitted for this session; `422` if an
`answers` entry doesn't match a question type's expected response shape.

---

## `GET /api/learners/{learner_id}/next-question?subject_id={subject_id}`

Requests the next dynamically generated question, per the Sequencing
Agent's topic selection (FR-006) and the Assessment-Generation Agent's
generation (FR-007).

**Response** `200`:
```json
{
  "question_id": "uuid",
  "topic_id": "string",
  "difficulty": "easy | medium | hard",
  "question_type": "multiple_choice | numeric",
  "stem": "string",
  "options": ["string", "..."]
}
```
`answer_key` is never included. The selected `topic_id` is guaranteed
`struggling` or `developing` band with satisfied prerequisites (FR-006).

**Errors**: `404` if the learner has no placement data yet for
`subject_id` (must complete placement first); `409` (rare) if no
eligible topic exists (all topics `mastered` or prerequisite-blocked) --
the Independent Test in spec.md US2 assumes an eligible topic exists.

---

## `POST /api/questions/{question_id}/answer`

Submits an answer to a previously generated question and triggers the
mastery-model update.

**Request**:
```json
{ "response": "string | number" }
```

**Response** `200`:
```json
{
  "correct": true,
  "topic_id": "string",
  "prior_p_mastery": 0.0,
  "posterior_p_mastery": 0.0,
  "band": "struggling | developing | mastered"
}
```
Grading is a deterministic comparison against `answer_key` -- no LLM
judgment call (FR-009). This call also writes the `answer_submitted` and
`mastery_updated` `AssessmentEvent` rows (FR-010).

**Errors**: `404` unknown `question_id`; `409` if already answered.

---

## `POST /api/questions/{question_id}/flag`

Flags a question's answer key as incorrect (FR-011).

**Request**:
```json
{ "flagged_by": "learner_id or instructor_id", "reason": "string" }
```

**Response** `200`:
```json
{ "question_id": "uuid", "validation_status": "flagged" }
```
A flagged question is excluded from all future `next-question` selection
(FR-011) until manually re-reviewed (review workflow itself is out of
scope for Milestone 1 -- see roadmap.md Milestone 7).

---

## `GET /api/learners/{learner_id}/mastery-state?subject_id={subject_id}`

Returns the learner's current full mastery state for a subject --
backs the "why was I placed here" / mastery-view UI (Constitution
Principle V).

**Response** `200`:
```json
{
  "topics": [
    {
      "topic_id": "string",
      "status": "unknown | scored",
      "p_mastery": 0.0,
      "band": "struggling | developing | mastered",
      "last_updated_at": "iso8601"
    }
  ]
}
```

---

## Cross-cutting

- Every endpoint above that triggers a Diagnostic, Sequencing, or
  Assessment-Generation agent invocation emits a Langfuse trace, flushed
  before the response returns (FR-014).
- Every endpoint's agent-driven decision (topic selection, mastery
  update, question generation) writes a corresponding `AssessmentEvent`
  row (FR-010) -- see `data-model.md`.
- All `learner_id` values in Milestone 1 resolve to a `DemoLearnerProfile`
  row with `is_demo = true` (Constitution Principle VIII); there is no
  real-account creation path yet.

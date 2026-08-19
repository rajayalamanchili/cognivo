# API Contract: Free-Text Grading via a Real A2A Service

**Feature**: `007-grading-agent` | **Date**: 2026-08-19

Extends `specs/001-domain-agnostic-core/contracts/api.md`'s FastAPI
backend. `GET /api/learners/{learner_id}/next-question` is unchanged in
shape -- it may now return `question_type: "free_text"` with
`options: null`, exactly like it already does for `numeric`, whenever
the selected topic's content artifact lists `free_text` first in
`preferred_question_types` (research.md §10). This contract covers only
what actually changes: `POST /api/questions/{id}/answer`'s free-text
branch, and the new internal A2A contract between the backend and the
Grading Agent.

## `POST /api/questions/{question_id}/answer` (EXTENDED)

Now `async def` (was sync) -- the free-text branch awaits the A2A call
to the Grading Agent. The MC/numeric branch is byte-for-byte unchanged
in behavior.

**Request** (unchanged shape; `response` may now be a string):
```json
{ "response": "The independent variable is x, the dependent variable is y." }
```

**Response** `200` (free-text, graded normally):
```json
{
  "correct": true,
  "topic_id": "linear-equations",
  "prior_p_mastery": 0.42,
  "posterior_p_mastery": 0.58,
  "band": "developing",
  "graduated_score": 0.82,
  "criteria_met": ["Correctly identifies the independent variable"],
  "criteria_missed": [],
  "grading_logic_version": "v1"
}
```

`graduated_score`, `criteria_met`, `criteria_missed`,
`grading_logic_version` are `null` for MC/numeric responses (existing
behavior, fields simply absent from what the mastery pipeline reads) --
present only for `free_text` (FR-005, FR-007, SC-004).

**Response** `422` -- **answer too long** (FR-015, checked before
moderation or grading):
```json
{ "error": "answer_too_long", "max_length": 2000 }
```

**Response** `429` -- **rate limited** (FR-016, checked before
moderation or grading):
```json
{ "error": "rate_limited", "retry_after_seconds": 137 }
```

**Response** `422` -- **moderation rejected** (FR-012, checked before
grading):
```json
{ "error": "moderation_rejected" }
```
Deliberately does not echo back *why* the moderation check flagged the
text (avoids teaching a learner how to phrase around the filter) --
the reason is still logged server-side (data-model.md).

**Response** `503` -- **grading unavailable** (FR-010, after retries
exhausted; also FR-014's fallback if the Grading Agent's response
repeatedly fails rubric-shape validation):
```json
{ "error": "grading_unavailable" }
```

**Error-state ordering**: too-long is checked first (cheapest, no DB
query needed beyond the request body itself), then rate limit (one DB
count query), then moderation (one LLM call), then grading (the A2A
call). Each is a distinct rejection -- never combined into one generic
error -- per spec.md's edge cases explicitly listing four separate
learner-facing states.

**Important**: none of the four rejection responses above call
`_already_answered()`'s guard into effect -- no `AssessmentEvent` of
type `ANSWER_SUBMITTED` is written for a rejected submission
(data-model.md), so `question_id` remains open for the learner to
resubmit (a corrected, shorter, or revised answer) against the same
question. This is what makes "content flagged -- please revise and
resubmit your answer" (etc.) an actionable prompt rather than a dead
end.

**Side effects (success path)**: identical downstream calls to the
existing MC/numeric path -- `apply_mastery_update()` then two
`record_event()` calls (`ANSWER_SUBMITTED`, `MASTERY_UPDATED`),
unchanged function signatures, only richer `ANSWER_SUBMITTED` payload
content for free-text (data-model.md). This is what makes FR-006's
"not a second, inconsistent path" structural rather than merely
tested-for.

**Side effects (rejection path)**: one `record_event()` call
(`free_text_submission_rejected`, data-model.md) -- no mastery update,
no `ANSWER_SUBMITTED` event.

---

## Internal contract: backend -> Grading Agent (A2A)

Not a public API -- documented here because it's the one genuinely new
network boundary this project has introduced (Constitution Principle
VI). The backend is an A2A client; the Grading Agent is reached at
`GRADING_AGENT_URL` (its own Vercel deployment, research.md §2).

**Request** (A2A message content, JSON):
```json
{
  "question_stem": "Identify the independent and dependent variables in: y = 3x + 2",
  "rubric": {
    "criteria": [
      { "description": "Correctly identifies the independent variable", "weight": 0.4 },
      { "description": "Correctly identifies the dependent variable", "weight": 0.6 }
    ]
  },
  "learner_answer": "The independent variable is x, the dependent variable is y."
}
```

**Response** (A2A message content, JSON) -- validated by the backend
against this exact shape before acceptance (FR-014):
```json
{
  "graduated_score": 0.82,
  "criteria_results": [
    { "description": "Correctly identifies the independent variable", "met": true },
    { "description": "Correctly identifies the dependent variable", "met": true }
  ],
  "grading_logic_version": "v1"
}
```

**Validation gate (FR-014)**: the backend rejects (and retries, per
research.md §7) a response if: `graduated_score` is missing or outside
`[0.0, 1.0]`; `criteria_results` doesn't have exactly one entry per
rubric criterion, in the same order, with matching `description`
strings; or `grading_logic_version` is missing. This is the same
generate-then-validate shape as `assessment_gen/agent.py`'s
`_validate_draft()` -- the Grading Agent's output is never trusted
blindly, exactly as an LLM's question draft never is.

**Retry policy (FR-010, research.md §7)**: up to 2 retries (3 total
attempts) on timeout, transport failure, or a validation failure above,
short fixed backoff between attempts. After all attempts are
exhausted, the caller returns the `503 grading_unavailable` response
above. Safe to retry unconditionally because the Grading Agent is
stateless (research.md §3) -- retrying never risks a duplicate write,
since the only write happens once, after the backend finally has a
valid response.

**Tracing**: the outbound A2A call is wrapped in the existing
`traced_request()` Langfuse instrumentation, same as every other agent
invocation (Constitution Principle V) -- this is a cross-process call,
but the same trace-and-flush requirement applies regardless of process
boundary.

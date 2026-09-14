# API Contract: Process-Level STEM Grading

**Feature**: `018-process-level-stem-grading` | **Date**: 2026-09-14

Extends `specs/007-grading-agent/contracts/api.md`, which itself
extends `specs/001-domain-agnostic-core/contracts/api.md`'s FastAPI
backend. `GET /api/learners/{learner_id}/next-question` is unchanged
in shape -- it may now return `question_type: "multi_step"` with
`options: null`, exactly like it already does for `numeric`/
`free_text`, whenever the selected topic has
`step_grading_enabled: true` and lists `multi_step` in its content
artifact's `preferred_question_types`. This contract covers only what
actually changes: `POST /api/questions/{id}/answer`'s new multi-step
branch, and the extended internal A2A contract between the backend and
the Grading Agent.

## `POST /api/questions/{question_id}/answer` (EXTENDED)

The MC/numeric/free-text branches are byte-for-byte unchanged. `response`
may now also be a `list[str]` when `question_type == "multi_step"`.

**Request**:
```json
{ "response": ["Subtract 2 from both sides: 3x = 12", "Divide both sides by 3: x = 4"] }
```

**Response** `200` (multi-step, every step correct):
```json
{
  "correct": true,
  "topic_id": "linear-equations",
  "prior_p_mastery": 0.42,
  "posterior_p_mastery": 0.58,
  "band": "developing",
  "graduated_score": 1.0,
  "first_diverging_step_index": null,
  "step_results": [
    { "step_index": 0, "correct": true, "criteria_met": ["Subtracts 2 from both sides correctly"], "criteria_missed": [] },
    { "step_index": 1, "correct": true, "criteria_met": ["Divides both sides by 3 correctly"], "criteria_missed": [] }
  ],
  "grading_logic_version": "v1"
}
```

**Response** `200` (multi-step, step 1 diverges -- step 2 omitted per FR-006):
```json
{
  "correct": false,
  "topic_id": "linear-equations",
  "prior_p_mastery": 0.42,
  "posterior_p_mastery": 0.31,
  "band": "struggling",
  "graduated_score": 0.5,
  "first_diverging_step_index": 1,
  "step_results": [
    { "step_index": 0, "correct": true, "criteria_met": ["Subtracts 2 from both sides correctly"], "criteria_missed": [] },
    { "step_index": 1, "correct": false, "criteria_met": [], "criteria_missed": ["Divides both sides by 3 correctly"] }
  ],
  "grading_logic_version": "v1"
}
```

`first_diverging_step_index`, `step_results` are `null`/absent for
MC/numeric responses (existing behavior, unchanged); `criteria_met`/
`criteria_missed` (top-level, flat) remain `null` specifically for
`multi_step` responses -- the per-step breakdown replaces them, it does
not sit alongside them.

**Response** `422` -- **step count mismatch** (FR-012, checked before
moderation or grading, same ordering position as free-text's
answer-too-long check):
```json
{ "error": "step_count_mismatch", "expected_step_count": 2, "submitted_step_count": 1 }
```

**Response** `422` -- **answer too long**, `429` -- **rate limited**,
`422` -- **moderation rejected**, `503` -- **grading unavailable**: all
identical in shape and ordering to `specs/007-grading-agent/contracts/
api.md`'s existing free-text rows, now also reachable for
`multi_step` responses (length cap and moderation run against the
submission's concatenated step text; grading-unavailable applies after
the same 2-attempt retry policy, research.md §1).

**Error-state ordering**: step-count mismatch is checked first
(cheapest -- one length comparison against the question's own
`answer_key`, no DB query beyond what's already loaded), then
too-long, rate limit, moderation, then grading -- extending free-text's
existing ordering with one new, even-cheaper check at the front.

**Side effects (success path)**: identical downstream calls to the
existing free-text path -- `apply_mastery_update()` then two
`record_event()` calls (`ANSWER_SUBMITTED`, `MASTERY_UPDATED`),
unchanged function signatures, only richer `ANSWER_SUBMITTED` payload
content for `multi_step` (data-model.md).

**Side effects (step-count-mismatch rejection path)**: one
`record_event()` call (`step_count_mismatch_rejected`, data-model.md)
-- no mastery update, no `ANSWER_SUBMITTED` event, question remains
open for resubmission (same non-`_already_answered()` guarantee
free-text's other rejection paths already have).

---

## Internal contract: backend -> Grading Agent (A2A), multi-step

Extends `specs/007-grading-agent/contracts/api.md`'s existing internal
contract -- same endpoint, same shared-secret authentication
(`X-Grading-Agent-Secret`), same Vercel Deployment Protection bypass
header, same leaked-secret compensating guardrails
(`before_model_guardrail`). Nothing about the A2A boundary itself
changes; only the message content's shape gains an ordered-steps
variant.

**Request** (A2A message content, JSON):
```json
{
  "question_stem": "Solve for x: 3x + 2 = 14",
  "steps": [
    {
      "step_prompt": "Isolate the variable term on one side.",
      "criteria": [
        { "description": "Subtracts 2 from both sides correctly", "weight": 1.0 }
      ]
    },
    {
      "step_prompt": "Solve for x.",
      "criteria": [
        { "description": "Divides both sides by 3 correctly", "weight": 1.0 }
      ]
    }
  ],
  "learner_steps": [
    "Subtract 2 from both sides: 3x = 12",
    "Divide both sides by 3: x = 4"
  ]
}
```

**Response** (A2A message content, JSON) -- validated by the backend
against this exact shape before acceptance, same discipline as
`_validate_and_parse()` already applies to free-text:
```json
{
  "graduated_score": 1.0,
  "first_diverging_step_index": null,
  "step_results": [
    {
      "step_index": 0,
      "criteria_results": [{ "description": "Subtracts 2 from both sides correctly", "met": true }]
    },
    {
      "step_index": 1,
      "criteria_results": [{ "description": "Divides both sides by 3 correctly", "met": true }]
    }
  ],
  "grading_logic_version": "v1"
}
```

**Validation gate (extends FR-014's free-text validation)**: the
backend rejects (and retries, research.md §1) a response if:
`graduated_score` is missing, outside `[0.0, 1.0]`, or doesn't match
`(count of step_results entries where every criterion is met) /
(total steps in the request)` recomputed independently; `step_results`
is missing, out of order, or has more entries than
`first_diverging_step_index + 1` (or more than the total step count,
when `first_diverging_step_index` is `null`) -- i.e., the agent
reported a step *after* the one it marked as the first divergence
(FR-006); any `criteria_results` entry's count or `description` doesn't
match that step's own rubric criteria, in order; or `grading_logic_version`
is missing. A response failing this gate is treated exactly like any
other invalid Grading Agent response -- retried, then
`grading_unavailable` once attempts are exhausted.

**Retry policy**: unchanged from free-text -- up to 1 retry (2 total
attempts), `REQUEST_TIMEOUT_SECONDS = 8.0`, `RETRY_BACKOFF_SECONDS =
0.2` (research.md §1). Safe to retry unconditionally; the Grading
Agent remains stateless.

**Tracing**: unchanged -- wrapped in the existing `traced_request()`
Langfuse instrumentation, same as every other agent invocation
(Constitution Principle V).

# Data Model: Free-Text Grading via a Real A2A Service

Extends `specs/001-domain-agnostic-core/data-model.md`'s schema. Two
new enum values -- no new tables (research.md §9).

## Changed entity: `QuestionType` (enum)

One new value: `free_text` (alongside existing `multiple_choice`,
`numeric`). Selected per-topic exactly like every other type, via
`preferred_question_types` in that subject's content artifact
(research.md §10) -- no engine-side branching.

## Changed entity: `GeneratedQuestion`

No new columns. `answer_key` (existing JSON column) gains a third
shape, alongside MC's `{"correct_index": int}` and numeric's `{"value":
float, "tolerance": float}`:

```json
{
  "criteria": [
    { "description": "Correctly identifies the independent variable", "weight": 0.4 },
    { "description": "Correctly identifies the dependent variable", "weight": 0.6 }
  ]
}
```

This is spec.md's **Grading Rubric** entity -- generated alongside the
question by the Assessment-Generation Agent (FR-002, unchanged
generate-before-display path), a unique immutable artifact per
question, weights summing to `1.0` (validated the same way
`_validate_draft()` already validates MC's `correct_index` bound,
before `shown_at` may be set).

## New (not persisted as a row): `GRADING_LOGIC_VERSION`

spec.md's **Grading Logic Version** entity is a Python constant in the
Grading Agent's own source (research.md §8), not a database row.
Copied verbatim into every `ANSWER_SUBMITTED` event payload produced
for a free-text answer (below) -- that's how a Grading Decision records
"which version graded it" without a foreign key to a table that
doesn't exist.

## Changed entity: `AssessmentEventType` (enum)

One new value: `free_text_submission_rejected`. Logged once per
guardrail rejection (FR-012/FR-015/FR-016) -- never alongside an
`ANSWER_SUBMITTED` event for the same submission, since a rejected
submission is never graded.

```json
{
  "reason": "moderation",
  "submitted_text": "...",
  "length": 42
}
```

`reason` is one of `"moderation"` | `"too_long"` | `"rate_limited"`.
For `"too_long"`, `submitted_text` is truncated to the first 2000
characters (the length cap itself, FR-015) rather than storing an
unbounded string. Only `reason: "moderation"` rows count toward FR-013's
per-learner escalation threshold (research.md §7) -- `"too_long"` and
`"rate_limited"` rows are logged for audit but never escalate, per
spec.md's Clarifications.

This is spec.md's **Moderation Flag** entity when `reason:
"moderation"` -- and, more generally, the record of any pre-grading
rejection for the other two reasons. No separate table; distinct from
a Grading Decision (below) precisely because a rejected submission
never reaches grading (SC-007, SC-009, SC-010 all assert this
disjointness).

## Existing entity, richer payload: `AssessmentEvent` (`ANSWER_SUBMITTED`, free-text)

spec.md's **Grading Decision** entity is this existing event type, used
exactly as it already is for MC/numeric (`question_id`, `learner_id`,
`subject_id`, `topic_id` unchanged) but with a free-text-specific
payload:

```json
{
  "response": "the learner's submitted answer text",
  "correct": true,
  "graduated_score": 0.82,
  "threshold_used": 0.7,
  "criteria_met": ["Correctly identifies the independent variable"],
  "criteria_missed": [],
  "grading_logic_version": "v1"
}
```

`correct` is the threshold-derived boolean (`graduated_score >=
threshold_used`) -- the only field the mastery-update pipeline
(`apply_mastery_update`) ever reads, identical to how it already reads
MC/numeric's `correct` field (FR-006: no second, inconsistent path).
`graduated_score`, `criteria_met`, `criteria_missed`, and
`grading_logic_version` exist purely for FR-007/SC-004's
"why was this marked wrong" learner-facing and audit purposes.

The paired `MASTERY_UPDATED` event for a free-text answer is
byte-for-byte the same shape MC/numeric already produce -- it consumes
only the boolean `correct`, so it needs no change at all.

## Idempotency (FR-010, FR-014): no new field

The existing `_already_answered()` guard (`questions.py:136` --
checking for an existing `ANSWER_SUBMITTED` event on `question_id`)
already provides the uniqueness guarantee spec.md's Grading Decision
entity describes ("uniquely keyed to its answer submission"). Combined
with the Grading Agent's statelessness (research.md §3-§4), no new
column or table is needed to satisfy this.

## Derived (not persisted): per-learner moderation-flag count (FR-013)

Computed at query time by counting this learner's
`free_text_submission_rejected` events with `payload["reason"] ==
"moderation"` within the trailing 24-hour window (research.md §7) --
not a persisted counter column, consistent with this project's existing
preference for computing derived state at read time (e.g. mastery band
is never cached, per `models/enums.py`'s `mastery_band_for()`
docstring) rather than risking it drifting from the events that would
recompute it. Exposed as a backend service function only in this
milestone (no new API endpoint) -- there is no consumer yet, since
Milestone 7's instructor role doesn't exist; a future milestone's
review-workflow endpoint calls this same function rather than
re-implementing the count.

## Entity relationship summary

```text
GeneratedQuestion (question_type=free_text) 1---1 AssessmentEvent (ANSWER_SUBMITTED, richer payload)   (existing pattern, extended)
GeneratedQuestion (question_type=free_text) 1---0..1 AssessmentEvent (free_text_submission_rejected)    (NEW -- mutually exclusive with the above)
DemoLearnerProfile 1---* AssessmentEvent (free_text_submission_rejected, reason=moderation)              (queried for FR-013, not a stored relationship)
```

# Data Model: Process-Level STEM Grading

Extends `specs/001-domain-agnostic-core/data-model.md` and
`specs/007-grading-agent/data-model.md`'s schema. One new column, no
new tables (research.md §3).

## Changed entity: `QuestionType` (enum)

One new value: `multi_step` (alongside existing `multiple_choice`,
`numeric`, `free_text`). Selected per-topic exactly like every other
type -- via `preferred_question_types` in that subject's content
artifact -- but only ever offered for a topic where
`Topic.step_grading_enabled` is `true` (FR-001); no engine-side
subject-id branching.

## Changed entity: `Topic`

One new column:

| Column | Type | Notes |
|---|---|---|
| `step_grading_enabled` | `bool`, `NOT NULL`, `DEFAULT false` | Loaded from the content artifact's optional per-topic `process_level_grading` field (research.md §3). `false` for every topic that doesn't declare it -- additive-only migration, matching Milestone 15's precedent (`biology` untouched). |

No change to any other column. No cross-topic validation rule (unlike
`grade`/`GradeBand`'s all-or-nothing-per-subject FK) -- each topic's
flag is independent.

## Changed entity: `GeneratedQuestion`

No new columns. `answer_key` (existing JSON column) gains a fourth
shape, alongside MC's `{"correct_index": int}`, numeric's `{"value":
float, "tolerance": float}`, and free-text's `{"criteria": [...]}`:

```json
{
  "steps": [
    {
      "step_prompt": "Isolate the variable term on one side.",
      "criteria": [
        { "description": "Chooses to subtract 2 from both sides", "weight": 0.5 },
        { "description": "Correctly computes 3x = 12", "weight": 0.5 }
      ]
    },
    {
      "step_prompt": "Solve for x.",
      "criteria": [
        { "description": "Chooses to divide both sides by 3", "weight": 0.5 },
        { "description": "Correctly computes x = 4", "weight": 0.5 }
      ]
    }
  ]
}
```

This is spec.md's **Step Rubric** entity -- generated alongside the
question by the Assessment-Generation Agent (FR-002), validated the
same way `_validate_draft()` already validates free-text's criteria
weights (research.md §4), before `shown_at` may be set. `>= 2` steps
required; each step's `criteria` list follows the exact same shape and
weight-sums-to-`1.0` rule as a free-text question's flat criteria list,
plus a `>= 2` criteria-per-step floor (FR-005) -- one criterion for the
method/operation chosen, a separate one for whether it was executed
correctly, so a computational slip on an otherwise-correct method is
distinguishable from choosing the wrong method entirely.

## New (not persisted as a row): stepwise learner submission

spec.md's **Stepwise Submission** entity is the `response` field of
`POST /api/questions/{id}/answer`'s existing request body, now
`list[str]` instead of `str` when `question_type == "multi_step"` --
one entry per expected step, same order as `answer_key.steps`
(contracts/api.md). Not a new column or table; validated against the
question's own step count before any grading call (FR-012).

## Changed entity: `AssessmentEventType` (enum)

One new value: `step_count_mismatch_rejected`. Logged once per FR-012
rejection -- mirrors `free_text_submission_rejected`'s existing
disjointness guarantee: never alongside an `ANSWER_SUBMITTED` event for
the same submission, since a rejected submission is never graded.

```json
{ "expected_step_count": 2, "submitted_step_count": 1 }
```

## Existing entity, richer payload: `AssessmentEvent` (`ANSWER_SUBMITTED`, multi-step)

spec.md's **Step Grading Result** entity is this existing event type,
used exactly as it already is for MC/numeric/free-text (`question_id`,
`learner_id`, `subject_id`, `topic_id` unchanged) but with a
`multi_step`-specific payload:

```json
{
  "graduated_score": 0.5,
  "first_diverging_step_index": 1,
  "step_results": [
    {
      "step_index": 0,
      "correct": true,
      "criteria_met": ["Chooses to subtract 2 from both sides", "Correctly computes 3x = 12"],
      "criteria_missed": []
    },
    {
      "step_index": 1,
      "correct": false,
      "criteria_met": ["Chooses to divide both sides by 3"],
      "criteria_missed": ["Correctly computes x = 4"]
    }
  ],
  "grading_logic_version": "v1"
}
```

`step_results` contains one entry per step **up to and including** the
first incorrect step (FR-006) -- any step after
`first_diverging_step_index` is omitted from the list entirely, never
included with a placeholder "ungraded" status, so the list's length
itself is the deterministic signal a reader needs (no separate
"ungraded" enum value to keep in sync). `first_diverging_step_index` is
`null` when every step is correct. `graduated_score` is the backend-
computed fraction `(count of correct steps) / (total step count)` --
recomputed from `step_results` and validated against what the Grading
Agent reported (contracts/api.md's validation gate), never trusted
blindly, the same discipline `_validate_and_parse()` already applies to
free-text's `graduated_score`. `correct` (top-level, unchanged field
already present on every `ANSWER_SUBMITTED` event) is
`graduated_score >= SCORE_THRESHOLD` -- the same `0.7` constant, same
comparison, already used for free-text (FR-007: this feature does not
introduce a second correctness threshold).

## Unchanged: `MASTERY_UPDATED` event, mastery-model mechanism

`apply_mastery_update()` receives the same `correct: bool` boolean it
already receives for every other question type -- it has no awareness
that the submission behind that boolean was multi-step. FR-007's
"unchanged mastery mechanism" is structural, not just tested-for: the
mastery pipeline's function signature does not change.

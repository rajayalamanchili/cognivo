# Data Model: Recommendation Agent

Per research.md §2, `WeakAreaReport` and `NextStepSuggestion` (spec.md
Key Entities) are **response-shape concepts, not new persisted tables**
-- computed at request time from Milestone 1's existing entities
(`specs/001-domain-agnostic-core/data-model.md`). The only new
persisted rows are `AssessmentEvent` audit entries (§3 below), via
three new `AssessmentEventType` enum members (no new table).

## Reused entities (no schema change)

| Entity | Fields this feature reads |
|---|---|
| `MasteryState` | `p_mastery`, `band` (derived), `update_count`, `updated_at` -- per (learner, subject, topic). Absence of a row = "unknown" (unchanged from Milestone 1). |
| `AssessmentEvent` | Queried (`event_type = mastery_updated`) to build each flagged topic's evidence citation; new rows also written by this feature (§3). |
| `GeneratedQuestion` | `stem`, joined via `AssessmentEvent.question_id`, so a citation can reference "which question" concretely, not just an id. |
| `Topic` | `display_name`, `order_index` (tie-break, matching Sequencing's existing convention), `is_entry_level`. |
| `PrerequisiteEdge` | `from_topic_id` → `to_topic_id`, walked for FR-007's prerequisite-chain recursion. |
| `Subject` | `validated_at` gate, same as every other endpoint. |

## WeakAreaReport (response shape, not a table)

One report per (`learner_id`, `subject_id`) request.

| Field | Type | Notes |
|---|---|---|
| `subject_id` | string | |
| `data_sufficiency` | enum: `confident` \| `insufficient_data` | `insufficient_data` when every assessed topic has `update_count < 3` (FR-004). |
| `broad_review_needed` | boolean | True when >= 60% of confidently-assessed topics (`update_count >= 3`) are in the `struggling` band (FR-005). |
| `weak_areas` | list of `WeakAreaFlag` | Empty list is valid and distinct from `data_sufficiency = insufficient_data` -- a confident report can correctly find zero struggling topics. |
| `in_progress_topic_ids` | list of string | Topics in the "developing" band (mastery 0.4-0.7, `update_count >= 3`) (FR-003a) -- distinct from a flagged weak area and from "not yet assessed." |
| `not_yet_assessed_topic_ids` | list of string | Topics with no `MasteryState` row at all (FR-003). |
| `insufficient_data_topic_ids` | list of string | Topics with `1 <= update_count < 3` (FR-004) -- distinct from `not_yet_assessed_topic_ids`. |

## WeakAreaFlag (element of `WeakAreaReport.weak_areas`)

| Field | Type | Notes |
|---|---|---|
| `topic_id` | string | |
| `display_name` | string | From `Topic`. |
| `p_mastery` | float | Current posterior, `< 0.4` by construction. |
| `evidence` | list of `EvidenceCitation` | MUST be non-empty (FR-002/SC-002) -- at least the `>= 3` `mastery_updated` events that qualified this topic. |
| `next_step` | `NextStepSuggestion` | Exactly one per flagged topic (FR-006). |

## EvidenceCitation

| Field | Type | Notes |
|---|---|---|
| `event_id` | UUID | `AssessmentEvent.event_id`, `event_type = mastery_updated`. |
| `question_id` | UUID | The question this observation came from. |
| `question_stem` | string | Denormalized from `GeneratedQuestion.stem` for a self-contained citation. |
| `answer_correct` | boolean | From the event's payload. |
| `prior_p_mastery` | float \| null | From the event's payload. |
| `posterior_p_mastery` | float | From the event's payload. |
| `created_at` | timestamp | |

## NextStepSuggestion (response shape, not a table)

| Field | Type | Notes |
|---|---|---|
| `recommended_topic_id` | string | The topic to actually practice next -- either the originally-flagged topic (FR-007 Scenario 1) or a prerequisite root cause (FR-007 Scenario 2 / recursion). |
| `recommended_display_name` | string | |
| `reason` | enum: `direct_practice` \| `prerequisite_gap` \| `prerequisite_not_yet_assessed` | `direct_practice` when the flagged topic's own prerequisites are all `mastered`; `prerequisite_gap` when recursion stopped at an unmastered-but-assessed topic; `prerequisite_not_yet_assessed` when recursion stopped at a topic with no `MasteryState` row (Clarifications / Edge Cases). |
| `prerequisite_chain` | list of string | Topic ids walked from the originally-flagged topic down to `recommended_topic_id`, in order (empty when `reason = direct_practice`). Always references real `Topic` rows in the subject's content artifact (FR-006 Scenario 3, SC-003) -- never a fabricated name, by construction (this field is only ever populated from `PrerequisiteEdge`/`Topic` rows, never LLM output, per FR-011). |

## AssessmentEventType additions

Three new enum members on the existing `AssessmentEvent` table (Alembic
migration adds Postgres enum labels; no new column).

| Member | Written | `question_id` | `payload` shape |
|---|---|---|---|
| `recommendation_report_generated` | Once per report request | `null` | `{"data_sufficiency": ..., "broad_review_needed": ..., "weak_area_count": ..., "not_yet_assessed_count": ..., "insufficient_data_count": ...}` |
| `weak_area_flagged` | Once per flagged topic | `null` | `{"p_mastery": ..., "cited_event_ids": [...]}` |
| `next_step_suggested` | Once per suggestion (always paired 1:1 with a `weak_area_flagged` event) | `null` | `{"flagged_topic_id": ..., "recommended_topic_id": ..., "reason": ..., "prerequisite_chain": [...]}` |

`AssessmentEvent.topic_id` is `nullable=False` today (Milestone 1) because
every existing event type is inherently single-topic. `recommendation_report_generated`
is report-level, not single-topic, so this feature's migration also
relaxes `topic_id` to nullable (additive, backward-compatible -- every
existing event type keeps writing a real `topic_id`, unchanged) and sets
it `null` only for this one event type. `weak_area_flagged` and
`next_step_suggested` remain single-topic and always set a real `topic_id`.

## Entity relationship summary

```text
DemoLearnerProfile 1---* MasteryState *---1 Topic          (existing, read-only here)
DemoLearnerProfile 1---* AssessmentEvent *---0..1 GeneratedQuestion   (existing; 3 new event_type values)
Topic 1---* PrerequisiteEdge (self-referential)             (existing, read-only here)

WeakAreaReport (response shape)
 └─ weak_areas: WeakAreaFlag[]
     ├─ evidence: EvidenceCitation[]  --> AssessmentEvent rows (event_type=mastery_updated)
     └─ next_step: NextStepSuggestion --> PrerequisiteEdge/Topic walk
```

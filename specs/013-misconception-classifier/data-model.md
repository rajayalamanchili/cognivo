# Data Model: Fine-Tuned Misconception Classifier

Extends `specs/001-domain-agnostic-core/data-model.md` and
`specs/002-recommendation-agent/data-model.md`. One new enum value,
one optional content-artifact field, zero new tables (research.md §4).

## Changed entity: `AssessmentEventType` (enum)

One new value: `misconception_classified`, written by the new
classification cron job (research.md §3), never per weak-area-report
request.

```json
{
  "misconception_id": "confuses-independent-dependent-variable",
  "confidence": 0.82,
  "cited_event_ids": ["<uuid>", "<uuid>", "<uuid>"],
  "classifier_version": "v1"
}
```

This is spec.md's **Misconception Classification** entity. `topic_id`
and `subject_id` (existing `AssessmentEvent` columns) are always set to
the classified learner/topic pair; `question_id` is left null (like
`recommendation_report_generated`) since a classification spans
multiple prior answers, not one question. `cited_event_ids` references
the specific `ANSWER_SUBMITTED` events (free-text, incorrect) that
qualified this classification -- FR-004's evidence requirement.
`classifier_version` mirrors `grading_logic_version`'s existing naming
convention (spec 007).

## New (not persisted as a row): Misconception Pattern

spec.md's **Misconception Pattern** entity is authored data, not a
database row -- a `misconceptions` list inside a subject's own
`subject.yaml` content artifact (research.md §9):

```yaml
misconceptions:
  - misconception_id: confuses-independent-dependent-variable
    description: Consistently swaps which variable is manipulated vs. observed.
```

Validated by `services/content_artifact/validator.py` as an optional
field -- a subject with no `misconceptions` list is valid (spec.md's
edge case: a taxonomy-less subject produces zero classifications, never
an error).

## New (not persisted as a row): Validation Set

spec.md's **Validation Set** entity is a checked-in fixture,
`backend/evaluation/misconception_ground_truth.jsonl`, mirroring
`grading_ground_truth.jsonl`'s shape (research.md §6) with one added
field:

```json
{"question": "...", "learner_answer": "...", "expected_grade": false, "expected_misconception_id": "confuses-independent-dependent-variable"}
```

`expected_misconception_id` may be `null` for an example that is simply
wrong without a named pattern -- not every incorrect answer has to
match a taxonomy entry.

## New (not persisted as a row): trained classifier artifact

spec.md's classifier itself is a serialized, versioned file per
subject (research.md §8):
`backend/misconception_models/<subject_id>/<version>/classifier.joblib`
-- bundled with the deployed backend function, read-only at request
time, never written at runtime.

## Existing entity, richer read path: `WeakAreaFlag` (Recommendation Agent, spec 002)

No field renamed or removed. One new optional field added:

| Field | Type | Notes |
|---|---|---|
| `misconception` | `MisconceptionEnrichment \| None` | `None` when no `misconception_classified` event exists for this `(learner_id, subject_id, topic_id)`, the classifier found no match above confidence, or evidence was insufficient (research.md §5) -- FR-006's graceful degradation. Every other `WeakAreaFlag` field is unchanged from spec 002. |

## New (not persisted as a row): `MisconceptionEnrichment`

spec.md's Key Entities section calls this the display-ready, read-time
view of a Misconception Classification attached to a `WeakAreaFlag` --
distinct from the persisted `misconception_classified` event above (the
decision record), the same way `WeakAreaFlag` itself is a read-time
composition over persisted `AssessmentEvent`/`MasteryState` rows rather
than a decision record of its own.

| Field | Type | Notes |
|---|---|---|
| `misconception_id` | string | From the subject's content-artifact taxonomy. |
| `description` | string | Denormalized from the content artifact for a self-contained display. |
| `confidence` | float | From the classifier run that produced it. |
| `evidence` | list of `EvidenceCitation` | **Reuses spec 002's `EvidenceCitation` type exactly** -- all seven fields (`event_id`, `question_id`, `question_stem`, `answer_correct`, `prior_p_mastery`, `posterior_p_mastery`, `created_at`), not a subset. `prior_p_mastery`/`posterior_p_mastery` are populated from that same `ANSWER_SUBMITTED` event's paired `mastery_updated` event, exactly as spec 002's own `EvidenceCitation` construction already does -- no new citation type, no null-padding of fields that type expects. |

## Entity relationship summary

```text
GeneratedQuestion 1---* AssessmentEvent (event_type=answer_submitted, free_text)
                                │
                                │ (offline cron job, research.md §3)
                                ▼
                    AssessmentEvent (event_type=misconception_classified)
                                │
                                │ (read at report-build time, never invoked live)
                                ▼
WeakAreaFlag (existing, spec 002)
 └─ misconception: MisconceptionEnrichment | None
     ├─ evidence: EvidenceCitation[]  --> AssessmentEvent rows (event_type=answer_submitted)
     └─ (misconception_id/description) --> subject.yaml's misconceptions list (read-only here)
```

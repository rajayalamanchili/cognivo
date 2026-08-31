# Quickstart: Fine-Tuned Misconception Classifier

**Feature**: `020-misconception-classifier` (spec directory
`013-misconception-classifier`) | **Date**: 2026-08-31

Validates the classifier end to end -- training, the offline
classification job, and the Recommendation Agent's enriched read path
-- against the already-deployed Milestones 1-10 backend plus this
feature's new enum value and content-artifact taxonomy fields. See
`data-model.md` for entity detail, `research.md` for the
classifier/baseline/storage decisions, and `contracts/api.md` for exact
request/response shapes.

## Prerequisites

- Same as `specs/002-recommendation-agent/quickstart.md` (Postgres,
  both content artifacts loaded, a learner with an accumulated
  free-text answer history from Milestone 6/8/9) -- plus this feature's
  migration (`assessment_event_type` gains `misconception_classified`)
  applied via `alembic upgrade head`.
- At least one topic in each seeded subject (`algebra-1`, `biology`)
  listing a `misconceptions` entry in its content artifact
  (data-model.md), so the domain-agnostic claim (Principle III) is
  proven for a second subject, not just one.
- `VOYAGE_API_KEY` set (already required for the Tutor Agent, Milestone
  9) -- reused here for classifier training/inference embeddings, no
  new credential.
- A trained classifier artifact present at
  `backend/misconception_models/<subject_id>/<version>/classifier.joblib`
  for each subject with a taxonomy (research.md §1/§8) -- produced by
  `backend/scripts/train_misconception_classifier.py`.
- `CRON_SECRET` set (already required for the existing demo-reset cron)
  -- reused by the new `/api/cron/classify-misconceptions` route.

## Run locally

Same as `specs/001-domain-agnostic-core/quickstart.md`'s Run locally
section. To exercise the classification job locally without waiting for
Vercel Cron, call the route directly:

```bash
curl -H "Authorization: Bearer $CRON_SECRET" \
  http://localhost:8000/api/cron/classify-misconceptions
```

## Validation scenario: named misconception appears in a weak-area report

Maps to spec.md's User Story 1 Acceptance Scenarios and SC-001/SC-003.

1. **Sufficient evidence produces a cited misconception label** (US1
   Acceptance Scenario 1)
   Seed a learner with `>= 3` incorrect free-text `ANSWER_SUBMITTED`
   events on one topic, all matching one taxonomy entry's pattern ->
   run the classification job (above) -> confirm a new
   `AssessmentEvent` (`event_type=misconception_classified`) exists for
   that `(learner_id, subject_id, topic_id)` with a non-empty
   `cited_event_ids` list -> `GET
   /api/learners/{learner_id}/recommendations` -> confirm the matching
   `weak_areas[]` entry's `misconception` field is populated and its
   `evidence` list is non-empty (SC-003).

2. **Insufficient evidence yields no label** (US1 Acceptance Scenario 2,
   SC-004)
   Same as above but with only 1-2 qualifying events -> run the
   classification job -> confirm no `misconception_classified` event
   is written -> the weak-area report's `misconception` field for that
   topic is `null`, every other field unchanged from spec 002's
   existing shape.

## Validation scenario: graceful degradation with no classifier

Maps to spec.md's User Story 2 Acceptance Scenarios and SC-002.

1. **No taxonomy authored for a subject** -- `GET
   /api/learners/{learner_id}/recommendations?subject_id=<subject with
   no misconceptions list>` -> confirm `200`, full spec-002 response
   shape, `misconception: null` on every flag, no error.
2. **Classification job never run / model artifact missing for a
   subject** -- same request against a learner in a subject with a
   taxonomy but no trained artifact yet -> confirm the same graceful
   `null` result, not a `5xx`.

## Validation scenario: accuracy measured honestly against baseline

Maps to spec.md's User Story 3 Acceptance Scenarios and SC-001.

```bash
cd backend && uv run python scripts/check_misconception_classifier_eval.py \
  evaluation/misconception_ground_truth.jsonl
```

Confirm the report prints both the trained classifier's accuracy and
the prompted-only baseline's accuracy against every row in the fixture,
and that the script exits `0` regardless of which one scores higher
(research.md §7) -- only a crash or a malformed fixture should produce
a non-zero exit.

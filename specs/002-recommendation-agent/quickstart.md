# Quickstart: Recommendation Agent

**Feature**: `002-recommendation-agent` | **Date**: 2026-08-16

Validates the weak-area report and next-step suggestion flow end to
end, against the already-deployed Milestone 1 backend. See
`data-model.md` for entity detail and `contracts/api.md` for exact
request/response shapes.

## Prerequisites

- Same as `specs/001-domain-agnostic-core/quickstart.md` (Postgres,
  content artifacts loaded, seeded `DemoLearnerProfile`) -- this
  feature adds no new provisioning step, only new endpoints on the
  already-running backend.
- The new `AssessmentEventType` enum labels migrated:
  `alembic upgrade head` picks up
  `alembic/versions/<new>_recommendation_event_types.py`.
- A learner with some existing `MasteryState`/`AssessmentEvent` history
  on `algebra-1` -- e.g. run `specs/001-domain-agnostic-core/quickstart.md`
  steps 1-4 a few times first to produce real data to report on.

## Run locally

Same as `specs/001-domain-agnostic-core/quickstart.md`'s Run locally
section -- no new process.

## Validation scenario: weak-area report and next steps

Maps directly to spec.md User Stories 1-3's Acceptance Scenarios.

1. **Script a known-weak-topic fixture**
   Using the scripted-answer approach from Milestone 1's quickstart
   step 2, drive a learner to >= 3 wrong answers on one topic (e.g.
   `linear-equations`) so `MasteryState.band = struggling` and
   `update_count >= 3`.

2. **Request a report**
   `GET /api/learners/{learner_id}/recommendations?subject_id=algebra-1`
   → Confirm the scripted topic appears in `weak_areas`, with `evidence`
   citing the specific `AssessmentEvent` rows from step 1 (FR-002,
   SC-001, SC-002) -- not just a topic name and a number.
   → Confirm any topic never touched appears in
   `not_yet_assessed_topic_ids` (FR-003).
   → Confirm a topic touched fewer than 3 times appears in
   `insufficient_data_topic_ids`, not in `weak_areas` (FR-004, the
   "single wrong answer" Edge Case).

3. **Insufficient-data check** (SC-004)
   Against a fresh learner with zero or `< 3`-event topics only →
   confirm `data_sufficiency = "insufficient_data"` and `weak_areas` is
   empty, rather than a confident-sounding empty report.

4. **Broad-review threshold check** (FR-005)
   Script a learner where >= 60% of confidently-assessed topics
   (`update_count >= 3`) are `struggling` → confirm
   `broad_review_needed = true`. Script a learner just under that
   proportion → confirm `false`.

5. **Prerequisite-gap suggestion check** (FR-007, User Story 2)
   Script a learner where a flagged topic's prerequisite is itself
   `struggling` → confirm `next_step.reason = "prerequisite_gap"` and
   `next_step.recommended_topic_id` names the prerequisite, not the
   originally-flagged topic.
   → Extend the fixture so that prerequisite's own prerequisite is also
   `struggling` → confirm the suggestion recurses to the deeper topic
   (the root cause), per the Clarifications.
   → Script a case where the chain hits a topic with no `MasteryState`
   row at all → confirm `reason = "prerequisite_not_yet_assessed"`
   rather than assuming mastered or unmastered.
   → Confirm every `recommended_topic_id` and every `prerequisite_chain`
   entry is a real `topic_id` present in `algebra-1`'s content artifact
   (SC-003).

6. **Audit trail check** (User Story 3, FR-008)
   Query `AssessmentEvent` rows for the request in step 2 → confirm one
   `recommendation_report_generated` row, one `weak_area_flagged` row
   per flagged topic, and one `next_step_suggested` row per suggestion,
   each with enough `payload` detail to reconstruct why it was produced.

7. **Trace check**
   Compare the request in step 2 against Langfuse for the same time
   window → confirm a trace was recorded (same mechanism as Milestone
   1's SC-008 check).

8. **Test-suite independence check** (SC-005)
   Run `backend/scripts/check_no_shared_recommendation_sequencing_fixtures.py`
   (research.md §6) → confirm it passes, i.e. no scripted scenario
   module or helper is imported by both
   `tests/integration/recommendation/` and
   `tests/integration/test_next_topic_*.py`.

9. **Sequencing-divergence check** (User Story 4, FR-010)
   Using the same scripted mastery-state fixture from step 1, call both
   `GET /api/learners/{learner_id}/next-question?subject_id=algebra-1`
   and this feature's `/recommendations` endpoint → confirm they are
   permitted to name different topics as most urgent, and that each
   response's own reasoning (Sequencing's `candidate_topics_considered`
   audit payload vs. Recommendation's `evidence`/`prerequisite_chain`)
   is independently traceable without needing to reconcile the two.

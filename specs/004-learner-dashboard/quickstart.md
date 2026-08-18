# Quickstart: Learner Dashboard

**Feature**: `004-learner-dashboard` | **Date**: 2026-08-17

Validates the multi-subject dashboard end to end, against the
already-deployed Milestone 1-2 backend plus this feature's two new
endpoints. See `data-model.md` for entity detail and `contracts/api.md`
for exact request/response shapes.

## Prerequisites

- Same as `specs/002-recommendation-agent/quickstart.md` (Postgres,
  both content artifacts loaded, seeded `DemoLearnerProfile`) -- this
  feature adds no new provisioning step and no migration, only two new
  read-only endpoints and one new frontend route.
- A learner with some existing `MasteryState`/`AssessmentEvent` history
  on at least one subject, and zero history on the other, to exercise
  both a populated section and a "just getting started" section in the
  same dashboard load.

## Run locally

Same as `specs/001-domain-agnostic-core/quickstart.md`'s Run locally
section, plus load `/dashboard` in the frontend (new route).

## Validation scenario: multi-subject combined view

Maps directly to spec.md User Stories 1-4's Acceptance Scenarios and
this feature's Clarifications.

1. **Subject discovery check**
   `GET /api/subjects` -> confirm both `algebra-1` and `biology` appear,
   ordered by `subject_id`, with no hardcoded list anywhere in the
   frontend (research.md §4).

2. **Combined multi-subject render** (User Story 1, FR-001)
   Load `/dashboard` for a learner with mastery data on `algebra-1`
   only -> confirm the dashboard renders **two** sections (one per
   subject from step 1), the `algebra-1` section shows every topic with
   its real mastery value or "not yet assessed," and the `biology`
   section shows every topic as "not yet assessed" (not omitted, not a
   missing section).

3. **Freshness check** (FR-006)
   Answer one more question on `algebra-1`, reload `/dashboard` ->
   confirm the updated mastery value appears immediately -- no stale
   cache.

4. **Weak-area section match** (User Story 2, FR-002, SC-003)
   For the `algebra-1` section, compare the dashboard's displayed weak
   areas/next-step suggestions against a direct
   `GET /api/learners/{learner_id}/recommendations?subject_id=algebra-1`
   call made independently in the same test -> confirm they match
   exactly, including verbatim `data_sufficiency`/`broad_review_needed`
   framing when applicable (never paraphrased).

5. **Path visualization + count check** (User Story 3, FR-003, FR-004, SC-004, SC-006)
   For each subject section -> confirm the path visualization shows
   assessed topics, the current top-priority next topic (matching a
   direct `GET .../topic-priority-preview` call), and **exactly 3**
   upcoming topics (or fewer only if that subject's remaining topic
   graph has fewer than 3 left) -- each carrying the illustrative/
   subject-to-change disclosure.

6. **Brand-new-learner state** (User Story 4, FR-005, SC-002)
   Load `/dashboard` for a learner with zero `MasteryState` rows in any
   subject -> confirm every section (one per platform subject) shows
   every topic "not yet assessed," the Recommendation Agent's own
   "insufficient data" framing verbatim, and a path visualization
   anchored on that subject's entry-level topics -- a coherent
   "just getting started" view, not an empty or broken page.

7. **Recommendation-failure isolation** (Edge Cases, FR-007)
   Force the `/recommendations` call for one subject to fail (e.g. mock
   a 500) -> confirm that subject's mastery-view section still renders
   correctly, only the weak-area section shows a "couldn't load" state,
   and every other subject's section (all three of its sub-sections)
   renders unaffected.

8. **Sequencing-preview-failure isolation** (Edge Cases, FR-008)
   Force the `/topic-priority-preview` call for one subject to fail ->
   confirm that subject's mastery-view and weak-area sections still
   render correctly, only the path-visualization portion shows a
   "couldn't load" state, and every other subject's section renders
   unaffected.

9. **Extensibility check** (SC-005)
   Run `backend/scripts/check_no_subject_conditionals.py` (unchanged
   from Milestone 1) over the two new route/service files added by this
   feature -> confirm it still passes -- no subject-id-keyed
   conditional introduced.

10. **No audit-log/trace pollution from the preview endpoint** (research.md §3)
    Query `AssessmentEvent` rows spanning several dashboard reloads ->
    confirm no `next_topic_selected` events were written by
    `/topic-priority-preview` calls (only by an actual
    `/next-question` call, unchanged from Milestone 1), and confirm no
    Langfuse trace was recorded for a `/topic-priority-preview` or
    `/subjects` request.

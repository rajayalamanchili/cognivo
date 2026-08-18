# Tasks: Learner Dashboard

**Input**: Design documents from `/specs/004-learner-dashboard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present)

**Tests**: Included. `roadmap.md`'s Milestone 4 Definition of Done makes SC-003 and SC-004 hard gates and requires all acceptance scenarios plus Milestones 1-3's full suites to pass -- so the test tasks below are load-bearing, not optional scaffolding.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete same-phase task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are per `plan.md`'s Project Structure

## Path Conventions

Extends the existing `backend/` + `frontend/` monorepo from Milestones 1-2: `backend/src/{agents/sequencing,api/routes}/`, `backend/tests/{unit,integration}/`; `frontend/src/{app/dashboard,components,services}/`, `frontend/tests/{unit,e2e}/`. This is the first Learner-Dashboard-specific frontend work and the first feature since Milestone 1 to add both backend and frontend code in the same milestone.

---

## Phase 1: Setup

**Purpose**: Confirm this feature needs no new dependency before any code is written

- [X] T001 [P] Confirm no new dependency is required in `backend/pyproject.toml` or `frontend/package.json` (research.md -- reuses the already-locked FastAPI/SQLAlchemy/Pydantic and Next.js/React/Tailwind stacks; no `uv add` / `npm install` needed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The subject-discovery endpoint and the dashboard page's per-subject-section shell every user story renders into

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Implement `SubjectSummary` Pydantic model and `GET /api/subjects` endpoint (validated subjects only, ordered by `subject_id`) in `backend/src/api/routes/subjects.py` per contracts/api.md and research.md §4
- [X] T003 Mount the subjects router (`app.include_router(subjects.router)`) in `backend/src/api/main.py` (depends on T002)
- [X] T004 [P] Integration test for `GET /api/subjects` -- both seeded subjects returned ordered by `subject_id`, only `validated_at IS NOT NULL` subjects included, no `AssessmentEvent`/trace side effects -- in `backend/tests/integration/test_subjects_list.py` (depends on T002, T003)
- [X] T005 [P] Add `getSubjects()` client function and `SubjectSummary` type to `frontend/src/services/api.ts` per contracts/api.md
- [X] T006 [P] Create `frontend/src/components/DashboardSubjectSection.tsx` skeleton -- accepts `subjectId`/`displayName` props, renders a heading and three empty child slots (mastery, weak-area, path) that later stories populate independently
- [X] T007 Scaffold `frontend/src/app/dashboard/page.tsx` + `frontend/src/app/dashboard/dashboard-flow.tsx`: resolve the demo learner, fetch the subject list via `getSubjects()`, and render one `DashboardSubjectSection` per subject (mirrors `mastery-flow.tsx`'s top-level loading/loaded/error phase, scoped only to "did we get the subject list at all" -- each section's own data is fetched independently starting in Phase 3) (depends on T005, T006)

**Checkpoint**: Foundation ready -- `/dashboard` loads and renders one empty section per platform subject; user story implementation can now begin.

---

## Phase 3: User Story 1 - See overall progress at a glance (Priority: P1) 🎯 MVP

**Goal**: Every topic in every subject's content artifact appears in its own subject section with its correct current mastery value or an explicit "not yet assessed" state, reused directly from the existing `MasteryView` component and `GET /mastery-state` endpoint (both unchanged).

**Independent Test**: Given a learner with a mix of mastered, in-progress, and untouched topics across two subjects, load `/dashboard` and confirm every topic in each subject's content artifact appears, grouped under its own subject section, with its correct mastery value or "not yet assessed."

### Tests for User Story 1

- [X] T008 [P] [US1] Frontend unit test: `DashboardSubjectSection` fetches its subject's mastery state and renders it via the reused `MasteryView` component, including "not yet assessed" for untouched topics (FR-001) in `frontend/tests/unit/dashboard-mastery-section.test.tsx` (depends on T006)

### Implementation for User Story 1

- [X] T009 [US1] Wire a per-subject mastery-state fetch (existing `getMasteryState`, no backend change) into `DashboardSubjectSection` with its own loading/loaded/error phase, passing the result into the reused `MasteryView` component (FR-001, FR-006: fetched fresh on every mount, no caching) (depends on T007, T008)

### Additional Verification for User Story 1

- [X] T010 [US1] Playwright E2E test: answer a question via the API for one subject, reload `/dashboard`, and confirm the displayed mastery value for that topic matches the updated `MasteryState` exactly, with no drift (SC-001; US1 Acceptance Scenario 2's freshness requirement) -- in the same test, confirm the other, untouched subject's section still renders its own "just getting started" state correctly alongside the updated one (US1 Acceptance Scenario 3, the mixed-subject case) in `frontend/tests/e2e/dashboard-freshness.spec.ts` (depends on T009)

**Checkpoint**: User Story 1 is independently functional and demoable -- the multi-subject mastery view is live, and its exact-match freshness guarantee is mechanically verified.

---

## Phase 4: User Story 2 - See weak areas and next steps without asking (Priority: P1)

**Goal**: Each subject section triggers a fresh, subject-scoped call to the existing Recommendation Agent endpoint and displays its flagged weak areas and next-step suggestions verbatim, including its own uncertainty framing -- and a failure of this call must not affect the mastery view (FR-007).

**Independent Test**: Given a learner with a known weak topic in one subject, load `/dashboard` and confirm that subject's section shows the same flagged weak area and next-step suggestion a direct `GET /recommendations` call would independently produce.

### Tests for User Story 2

- [X] T011 [P] [US2] Frontend unit test: `WeakAreaSection` renders `weak_areas`/`next_step` and `data_sufficiency`/`broad_review_needed` framing verbatim, never paraphrased (FR-002) in `frontend/tests/unit/weak-area-section.test.tsx`
- [X] T012 [P] [US2] Frontend unit test: a failed/rejected recommendations fetch renders a distinct "couldn't load" state in the weak-area section while the mastery view (US1) still renders correctly (FR-007) in `frontend/tests/unit/dashboard-failure-isolation.test.tsx` (depends on T009)

### Implementation for User Story 2

- [X] T013 [P] [US2] Add `getRecommendations()` client function and `RecommendationsResponse`/`WeakAreaFlag`/`NextStepSuggestion`/`EvidenceCitation` types to `frontend/src/services/api.ts` per `specs/002-recommendation-agent/contracts/api.md` (first frontend consumer of this existing endpoint)
- [X] T014 [US2] Implement `WeakAreaSection.tsx` component rendering the response verbatim per FR-002 (depends on T013, T011)
- [X] T015 [US2] Wire a per-subject recommendations fetch (existing `getRecommendations`, no backend change) into `DashboardSubjectSection` with its own independent loading/loaded/error phase, rendering `WeakAreaSection` on success and a "couldn't load" state on failure without affecting the mastery-view phase (FR-007) (depends on T009, T014, T012)

### Additional Verification for User Story 2

- [X] T016 [US2] Playwright E2E test: call `GET /api/learners/{learner_id}/recommendations?subject_id=X` directly and compare its `weak_areas`/`next_step`/`data_sufficiency`/`broad_review_needed` content against that subject's rendered weak-area section on `/dashboard` for the same learner -- confirm an exact match, per quickstart.md step 4 (SC-003 -- **hard gate** per roadmap.md) in `frontend/tests/e2e/dashboard-weak-area-match.spec.ts` (depends on T015)

**Checkpoint**: User Stories 1 and 2 together deliver the dashboard's two P1 slices -- mastery + weak-area sections, each independently resilient, with SC-003's dashboard-matches-direct-call gate mechanically verified.

---

## Phase 5: User Story 3 - See the path so far and what's likely ahead (Priority: P2)

**Goal**: Each subject section shows topics already assessed, the Sequencing Agent's current top-priority next topic, and up to 3 likely-upcoming topics from that same ranking -- clearly marked illustrative -- and a failure of this call must not affect the mastery or weak-area sections (FR-008).

**Independent Test**: Given a learner's mastery state in a subject, load `/dashboard` and confirm that subject's "upcoming topics" list is generated by consulting the Sequencing Agent's current selection logic for that subject (not a separately invented ordering) and is visibly labeled as subject to change.

### Tests for User Story 3

- [ ] T017 [P] [US3] Unit test: the extracted eligibility/ranking helper preserves `select_next_topic`'s existing chosen-topic behavior (regression) and the new `preview_topic_priority` returns up to 3 correctly-ranked upcoming topics plus the correct `is_fallback` flag when zero topics are strictly eligible (research.md §1) in `backend/tests/unit/test_topic_priority_ranking.py`
- [ ] T018 [P] [US3] Integration test for `GET /api/learners/{learner_id}/topic-priority-preview` per contracts/api.md -- `next_topic` always present, `upcoming_topics` capped at 3, `404` on unknown/unvalidated `subject_id`, zero `AssessmentEvent` rows written and zero Langfuse spans emitted (research.md §3) in `backend/tests/integration/test_topic_priority_preview.py`

### Implementation for User Story 3

- [ ] T019 [US3] Refactor `backend/src/agents/sequencing/agent.py`: extract the eligible-topic ranking (currently inline in `select_next_topic`) into a shared private helper, then add `preview_topic_priority(db, *, learner_id, subject_id, upcoming_count=3)` reusing it -- `select_next_topic`'s own return value and behavior are unchanged (research.md §1, data-model.md) (depends on T017)
- [ ] T020 [US3] Implement `GET /api/learners/{learner_id}/topic-priority-preview` in `backend/src/api/routes/sequencing_preview.py` -- no `AssessmentEvent` write, not wrapped in `traced_request()` (research.md §3) -- and mount its router in `backend/src/api/main.py` (depends on T019, T018)
- [ ] T021 [P] [US3] Add `getTopicPriorityPreview()` client function and `TopicPriorityPreview`/`TopicPreviewEntry` types to `frontend/src/services/api.ts` per contracts/api.md
- [ ] T022 [P] [US3] Frontend unit test: `PathVisualization` renders assessed topics (derived from the existing mastery-state response), the top-priority next topic, and up to 3 upcoming topics, and every render that includes an upcoming-topics list carries the visible illustrative/subject-to-change disclosure (FR-003, FR-004, SC-004, SC-006) in `frontend/tests/unit/path-visualization.test.tsx`
- [ ] T023 [US3] Implement `PathVisualization.tsx` component per FR-003/FR-004 (depends on T021, T022)
- [ ] T024 [US3] Wire a per-subject topic-priority-preview fetch into `DashboardSubjectSection` with its own independent loading/loaded/error phase, deriving "already assessed" topics from the existing mastery-state fetch and rendering `PathVisualization` (depends on T015, T020, T023)
- [ ] T025 [P] [US3] Frontend unit test: a failed/rejected topic-priority-preview fetch renders a "couldn't load" state in the path-visualization portion only, while the mastery view and weak-area section (US1/US2) still render correctly (FR-008), extending `frontend/tests/unit/dashboard-failure-isolation.test.tsx` (depends on T024)

**Checkpoint**: User Stories 1-3 together deliver the full dashboard for an engaged learner -- mastery, weak-area, and path sections, each independently resilient.

---

## Phase 6: User Story 4 - The dashboard makes sense for a brand-new learner (Priority: P2)

**Goal**: Prove the "just getting started" state falls out correctly from US1-US3's already-built sections for a learner with zero assessment history in any subject -- no new production code, only verification (each underlying endpoint already handles the zero-history case by construction: `mastery-state` reports "unknown," `recommendations` reports `insufficient_data`, and `preview_topic_priority`'s ranking naturally selects entry-level topics when every band is "unknown").

**Independent Test**: Load `/dashboard` for a learner with no assessment history at all and confirm it renders a coherent "just getting started" state -- every topic "not yet assessed," the weak-area section reflecting the Recommendation Agent's own insufficient-data framing, and the path visualization anchored on each subject's entry-level topics -- rather than an empty or broken page.

### Tests for User Story 4

- [ ] T026 [US4] Backend integration test: for a learner with zero `MasteryState` rows, exercise `mastery-state`, `recommendations`, and `topic-priority-preview` against **both** platform subjects (`algebra-1`, `biology`) -- confirm every topic reports "not yet assessed"/`unknown`, `data_sufficiency = "insufficient_data"`, and `next_topic` is an entry-level topic for each subject, with zero engine-code branching between the two (SC-002, SC-005 -- mirrors `backend/tests/integration/test_second_subject.py`'s pattern) in `backend/tests/integration/test_dashboard_two_subjects.py` (depends on T003, T020)
- [ ] T027 [P] [US4] Playwright E2E test: load `/dashboard` for a brand-new learner and confirm one section per platform subject renders, each showing every topic "not yet assessed," the Recommendation Agent's own "insufficient data" framing, and a path visualization anchored on entry-level topics with the illustrative disclosure visible -- a coherent page, no error (SC-002) in `frontend/tests/e2e/dashboard-new-learner.spec.ts` (depends on T009, T015, T024, T026)

**Checkpoint**: All four user stories independently functional; the empty-state gate (SC-002) is mechanically verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and the extensibility gate this milestone shares with every prior one

- [ ] T028 [P] Regression check: run Milestones 1-3's full test suites (`backend/tests/`, excluding this feature's new tests; relevant `frontend/tests/`) and confirm they still pass unmodified (roadmap.md Milestone 4 Definition of Done: "Milestones 1-3's full suites still pass")
- [ ] T029 [P] Run `backend/scripts/check_no_subject_conditionals.py` (unchanged from Milestone 1) over this feature's new/changed files (`subjects.py`, `sequencing_preview.py`, `agents/sequencing/agent.py`) -- confirm SC-005's automated Principle III scan still passes with zero subject-id-keyed conditionals introduced
- [ ] T030 Run `quickstart.md`'s 10 validation scenarios end to end against the deployed environment and record results (depends on all prior tasks)
- [ ] T031 [P] Frontend unit test: FR-007's and FR-008's failure states render via the same shared failure-state presentation pattern (not two independently-styled "couldn't load" variants), and neither auto-retries within a single page load (FR-010), extending `frontend/tests/unit/dashboard-failure-isolation.test.tsx` (depends on T015, T025)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion -- BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion only.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; its component/types (T013, T014) are independently implementable in parallel with US1, but its `DashboardSubjectSection` wiring task (T015) has a same-file sequencing dependency on US1's mastery-fetch wiring (T009) -- not a functional dependency on US1's feature.
- **User Story 3 (Phase 5)**: Depends on Foundational completion; its backend work (T017-T020) is fully independent of US1/US2 and can proceed in parallel with them -- only its final wiring task (T024) has a same-file sequencing dependency on US2's recommendations-fetch wiring (T015), which itself already depends on US1's mastery-fetch wiring (T009).
- **User Story 4 (Phase 6)**: Depends on US1 (T009), US2 (T015), and US3 (T020, T024) all existing -- it verifies the composed behavior those stories produce; no new production code of its own.
- **Polish (Phase 7)**: T028/T029 have no hard dependency (can run any time after Foundational); T030 needs everything.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3/US4.
- **US2 (P1)**: Its component and API-client work (T013, T014) are independently implementable in parallel with US1, and its pre-implementation tests (T011, T012) can be written before either exists; only its `DashboardSubjectSection` wiring task (T015) has a same-file sequencing dependency on US1's mastery-fetch wiring (T009), since both edit the same shared component -- not a functional dependency on US1's feature being complete.
- **US3 (P2)**: Its backend endpoint (T017-T020) has no dependency on US1/US2 at all; only the frontend wiring task (T024) sequences after US1's and US2's wiring are already in `DashboardSubjectSection`, for the same same-file reason as US2 above.
- **US4 (P2)**: Depends on US1+US2+US3's endpoints all existing to have a composed page to verify.

### Within Each User Story

- Tests written and failing before implementation, except each story's "Additional Verification" task(s) (T010, T016) and Polish's cross-cutting consistency check (T031), which validate already-composed behavior after implementation completes -- mirroring spec 002's own precedent of a late-phase explainability/audit check run after its endpoint exists, rather than a pre-implementation TDD test.
- Backend before frontend, where both exist (US3): ranking refactor -> endpoint -> frontend client -> component -> wiring.
- Types/client functions (`api.ts`) before the component that consumes them; component before the `DashboardSubjectSection` wiring task that renders it.

---

## Parallel Example: User Story 3

```bash
# Backend (after Foundational is complete, independent of US1/US2):
Task: "Unit test: ranking-helper extraction + preview_topic_priority in backend/tests/unit/test_topic_priority_ranking.py"
Task: "Integration test: GET topic-priority-preview contract in backend/tests/integration/test_topic_priority_preview.py"

# Frontend (after Foundational is complete, independent of the backend tasks above):
Task: "Add getTopicPriorityPreview() + types to frontend/src/services/api.ts"
Task: "Unit test: PathVisualization rendering + disclosure + count in frontend/tests/unit/path-visualization.test.tsx"
```

---

## Implementation Strategy

### MVP scope: User Story 1 alone

Unlike Milestones 1-2 (whose two P1 stories had to ship together because
one FR required the other's output in the same response), US1 and US2
here are genuinely independent -- each is its own unchanged backend
endpoint plus its own frontend section. The smallest real MVP is US1
alone: a multi-subject mastery view, which already makes Milestone 1's
mastery model visible to a learner for the first time.

1. Complete Phase 1 (Setup) + Phase 2 (Foundational) -- `/dashboard`
   loads with one empty section per subject.
2. Complete Phase 3 (US1) -- multi-subject mastery view is live, and
   its exact-match freshness guarantee (SC-001) is mechanically
   verified.
3. **STOP and VALIDATE**: run US1's Independent Test. This is the
   smallest demoable increment.
4. Complete Phase 4 (US2) -- weak-area sections live, failure-isolated
   from US1, with SC-003's dashboard-matches-direct-call hard gate
   mechanically verified.
5. Complete Phase 5 (US3) -- path visualization live, failure-isolated
   from US1/US2. Backend half (T017-T020) can start as early as
   Foundational completes, in parallel with US1/US2.
6. Complete Phase 6 (US4) -- brand-new-learner state mechanically
   verified across both subjects.
7. Complete Phase 7 (Polish) -- Milestones 1-3 regression check,
   extensibility scan, full quickstart.md validation.

### Incremental delivery

Each phase checkpoint (end of Phase 3, 4, 5, 6, 7) is a point where the
dashboard is in a coherent, independently testable state -- consistent
with FR-007/FR-008's failure-isolation requirement holding at every
increment, not just once all four stories are done.

---

## Notes

- `[P]` tasks = different files, no dependency on an incomplete same-phase task.
- `[Story]` label maps a task to its user story for traceability; Setup, Foundational, and Polish tasks carry no `[Story]` label by design.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently before continuing.
- `/speckit-analyze` MUST run before `/speckit-implement` per CLAUDE.md/Constitution Development Workflow -- do not skip it once this task list is approved.

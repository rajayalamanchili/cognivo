---

description: "Task list for Learner-Facing Explainability UI"
---

# Tasks: Learner-Facing Explainability UI

**Input**: Design documents from `/specs/025-learner-explainability-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md (all present)

**Tests**: Included, matching this project's established convention (every Success Criteria in this repo's specs ships with an automated check, not verified by inspection alone -- see CLAUDE.md and every prior milestone's Definition of Done in `roadmap.md`).

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P1/P2/P2/P3/P3) to enable independent implementation and testing of each story. No new dependency, no migration -- see plan.md's Technical Context.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1-US6)

## Path Conventions

Web app split per plan.md: `backend/src/`, `backend/tests/`, `frontend/src/`.

## Note on `/speckit-analyze` remediation (2026-09-27)

This revision fixes four findings from the `/speckit-analyze` pass: (C1) `frontend/src/components/LearnerAssignments.tsx` is a genuinely separate component from `quiz-flow.tsx` -- it independently calls `answerQuestion` and discards the result today, so it needs its own wiring tasks for US1/US3/US4, not just `quiz-flow.tsx`'s; (I1) the Foundational phase's dependency notes below now correctly list all four stories that depend on T003/T004; (U1) T011 now explicitly names the `NEXT_PUBLIC_EXPLAIN_EVERY_PICK` scope switch as part of its own scope.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: Shared backend primitives that both US3 (placement) and US4 (refreshed acknowledgment) need, and the shared frontend copy-tier helper US1, US2, US4, and US6 all read from. No user story work in those stories can begin until this phase is complete; US2/US5/US6 do not depend on this phase's backend half but do depend on T003/T004 for copy framing.

**⚠️ CRITICAL**: T001/T002 block US3 and US4's implementation tasks. T003/T004 block US1, US2, US4, and US6 -- every story that renders explanation copy.

- [X] T001 [P] Unit test for `MasteryUpdateResult.prior_band` and a `refreshed_from_bands(prior_band, posterior_band)` helper, covering no-prior-state, never-mastered, already-mastered-reanswered, and newly-crossed cases in `backend/tests/unit/test_mastery_tool_prior_band.py`
- [X] T002 Add `prior_band: MasteryBand` to `MasteryUpdateResult` (derived from `prior_observation.band` if present, else `MasteryBand.STRUGGLING`) and a `refreshed_from_bands(prior_band, posterior_band) -> bool` helper in `backend/src/agents/sequencing/mastery_tool.py` (depends on T001)
- [X] T003 [P] Component test for grade-band-keyed copy tier selection across all four bands (1-2, 3-5, 6-8, 9-12) in `frontend/tests/unit/explainability-copy.test.ts`
- [X] T004 [P] Create `getExplanationCopyTier(unlockedGrade)` grade-band-keyed copy-tier helper, mirroring `frontend/src/lib/pacing.ts`'s `getPacingProfile` pattern, in `frontend/src/lib/explainabilityCopy.ts` (depends on T003)

**Checkpoint**: `prior_band`/`refreshed_from_bands` available to US3/US4; `getExplanationCopyTier` available to US1/US2/US4/US6.

---

## Phase 2: User Story 1 - A learner sees why the current question was chosen (Priority: P1) 🎯 MVP

**Goal**: Every question served by the Sequencing Agent's next-question picker (ordinary next-question, both timed-practice routes) carries its real selection reason, rendered as a distinct-worded chip for a fallback/decay pick vs. a normal next-step pick. **Correction found mid-implementation** (see T006/T009/T010/T013/T014 below): quiz and instructor-assigned quiz attempts select topics via a separate round-robin mechanism (Milestone 5, `next_quiz_topic`) with no eligible-pool/fallback concept at all -- they get no chip, per FR-004's "omit rather than fabricate" rule (spec.md Edge Cases, research.md §1).

**Independent Test**: Serve a question via the eligible pool and via a decay-driven fallback (per spec 024's backdating technique); confirm the chip's wording differs and matches the recorded reason exactly.

### Tests for User Story 1

- [X] T005 [P] [US1] Contract test: `NextQuestionOut` includes `is_fallback`/`p_mastery`/`effective_p_mastery` for both an eligible-pool pick and a fallback pick in `backend/tests/contract/test_next_question_selection_reason.py`
- [X] T006 [P] [US1] N/A -- found during implementation that quiz question selection (`next_quiz_topic`, Milestone 5) is a round-robin with no `is_fallback`/decay concept at all; `QuizQuestionOut` gains no selection-reason fields, so there is nothing to contract-test here (research.md §1 correction, spec.md Edge Cases)
- [X] T007 [P] [US1] Component test: `SelectionReasonChip` renders distinct copy for a fallback/decayed pick vs. an eligible-pool pick, omits itself when the selection reason is absent (FR-004), and respects the `NEXT_PUBLIC_EXPLAIN_EVERY_PICK` scope switch (FR-003) in `frontend/tests/unit/selection-reason-chip.test.tsx`

### Implementation for User Story 1

- [X] T008 [US1] Extend `NextQuestionOut` and `build_next_question_out` to populate `is_fallback`/`p_mastery`/`effective_p_mastery` from `NextTopicSelection` (fixes the ordinary next-question route and both timed-practice routes via the shared builder) in `backend/src/api/routes/questions.py` (depends on T005)
- [X] T009 [US1] N/A -- same finding as T006; `quiz.py` is not touched (research.md §1 correction)
- [X] T010 [US1] N/A -- same finding as T006; `quiz_assignments.py` is not touched (research.md §1 correction)
- [X] T011 [P] [US1] Create `SelectionReasonChip` component reading `is_fallback`/`p_mastery`/`effective_p_mastery`/`last_practiced_at` and `getExplanationCopyTier`, including the `NEXT_PUBLIC_EXPLAIN_EVERY_PICK` scope switch's render-gating logic (FR-003) and an `Intl.RelativeTimeFormat`-based elapsed-time formatter for FR-002's wording, in `frontend/src/components/SelectionReasonChip.tsx` (depends on T007, T004)
- [X] T012 [US1] Wire `SelectionReasonChip` into the served-question render path in `frontend/src/app/practice/practice-flow.tsx` (depends on T008, T011)
- [X] T013 [US1] N/A -- quiz-flow.tsx has no `SelectionReasonChip` to wire (no backend fields exist, T009); its US3/US4 work (T023's disclosure, T029's `RefreshedBanner`) is unaffected
- [X] T014 [US1] N/A -- same as T013, for `LearnerAssignments.tsx`; its US3/US4 work (T023's disclosure, T030's `RefreshedBanner`) is unaffected

**Checkpoint**: User Story 1 is fully functional and independently testable/demoable, across ordinary practice, quiz, and instructor-assigned attempts.

---

## Phase 3: User Story 2 - A learner sees mastery as reversible upkeep, not a fixed grade (Priority: P1)

**Goal**: The dashboard shows both peak and decay-adjusted effective mastery per topic, with a "last practiced" indicator that warms in color and states elapsed time in text, framed as recoverable upkeep.

**Independent Test**: Load the dashboard for a learner with one recently-mastered and one long-untouched mastered topic; confirm the long-untouched one shows lower effective-than-peak mastery and a warmer, text-labeled indicator.

### Tests for User Story 2

- [X] T015 [P] [US2] Contract test: `MasteryTopicOut.effective_p_mastery` matches `decay.py`'s `effective_mastery_for_review` output exactly for both a backdated and a freshly-practiced topic in `backend/tests/contract/test_mastery_state_effective_mastery.py`
- [X] T016 [P] [US2] Component test: `MasteryView` renders peak vs. effective mastery and a "last practiced" indicator that intensifies in color *and* carries a text label (never color alone, FR-007) as elapsed time grows, in `frontend/tests/unit/mastery-view.test.tsx`

### Implementation for User Story 2

- [X] T017 [US2] Add `effective_p_mastery` to `MasteryTopicOut`, computed via `effective_mastery_for_review` per topic, in `backend/src/api/routes/mastery.py` (depends on T015)
- [X] T018 [US2] Extend `MasteryView` to render peak vs. effective mastery, the color+text "last practiced" indicator (using the already-fetched-but-unused `last_updated_at`), and recovery/upkeep copy framing via `getExplanationCopyTier` in `frontend/src/components/MasteryView.tsx` (depends on T016, T017, T004)

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 4: User Story 3 - A learner understands why an answer was marked the way it was, in every flow that grades one (Priority: P2)

**Goal**: The per-criterion grading view that already renders in ordinary practice also reaches placement (immediately, per answer) and quiz/instructor-assigned attempts (gathered in the end-of-session summary -- **corrected mid-implementation** after confirming with the user: quiz has no per-question pause today, and inserting one would change its established auto-advance pacing; see spec.md Clarifications and research.md §4).

**Independent Test**: Complete a quiz containing one free-text answer; confirm the learner sees the identical per-criterion breakdown practice already shows, in that quiz's end-of-session summary, for both a passing and a failing answer. Same for a placement free-text answer, shown immediately.

### Tests for User Story 3

- [X] T019 [P] [US3] Contract test: `QuizSummaryOut`/`QuizSummaryResponse.per_question_results` matches each answered question's `ANSWER_SUBMITTED`/`MASTERY_UPDATED` event data (`correct`, `criteria_met`, `criteria_missed`, `step_results`, `prior_p_mastery`, `posterior_p_mastery`) in `backend/tests/contract/test_quiz_summary_grading_detail.py`
- [X] T020 [P] [US3] Component test: `QuizSummary` renders `AnswerResultView` per question from `per_question_results` (tolerating a missing `band`), and the quiz start screen discloses results appear at the end (FR-010a) -- extends the existing `frontend/tests/unit/quiz-summary.test.tsx` and `frontend/tests/unit/quiz-flow.test.tsx`
- [X] T021 [P] [US3] Integration test: `POST /api/placement/submit` returns `per_question_results` matching `AnswerOut`-equivalent fields (`correct`, `criteria_met`, `criteria_missed`, `step_results`, `prior_p_mastery`, `posterior_p_mastery`, `refreshed`) for a passing and a failing free-text placement answer in `backend/tests/integration/test_placement_grading_detail.py`

### Implementation for User Story 3

- [X] T022 [US3] Extend `compute_quiz_summary`'s existing `GeneratedQuestion`+`ANSWER_SUBMITTED`-event join with a second join to each question's `MASTERY_UPDATED` event; add `per_question_results: list[QuizAnswerResult]` to `QuizSummaryOut`/`QuizSummaryResponse` in `backend/src/services/quiz/session.py` and `backend/src/api/routes/quiz.py` (depends on T019)
- [X] T023 [US3] Render `per_question_results` via `AnswerResultView` in `frontend/src/components/QuizSummary.tsx` (making `AnswerResultView`'s `band` line conditional, since quiz-summary reconstruction has no `band` to show); add the FR-010a disclosure to `quiz-flow.tsx`'s start screen and `LearnerAssignments.tsx`'s start-attempt trigger -- covers both flows in one change, since both share `QuizSummary`/`getQuizSummary` (depends on T020, T022)
- [X] T024 [US3] Add `PlacementQuestionResult` model and `per_question_results: list[PlacementQuestionResult]` to `PlacementSubmitResponse`, populated inside the existing per-answer grading loop (including `refreshed` via T002's `refreshed_from_bands`) in `backend/src/api/routes/placement.py` (depends on T021, T002)

**Checkpoint**: User Stories 1-3 all work independently, across every flow named in FR-009.

---

## Phase 5: User Story 4 - A learner is celebrated when they refresh a decayed topic (Priority: P2)

**Goal**: A one-shot "refreshed" acknowledgment appears in the response to the specific answer that crosses a topic from below to above the mastered band -- never recomputed or re-shown later -- across every flow that grades an answer.

**Independent Test**: Answer a below-threshold decayed topic up past the mastered band; confirm `refreshed: true` in that response only. Answer the same topic again: confirm `refreshed: false`.

### Tests for User Story 4

- [X] T025 [P] [US4] Integration test: `AnswerOut.refreshed` is `true` only on a below-to-above `MASTERED` crossing, `false` for an already-mastered reanswer and a stays-below answer, and never re-appears on a later, unrelated request in `backend/tests/integration/test_refreshed_acknowledgment.py`
- [X] T026 [P] [US4] Component test: `RefreshedBanner` renders only when `refreshed` is `true` and renders nothing otherwise in `frontend/tests/unit/refreshed-banner.test.tsx`; plus a test extending `frontend/tests/unit/quiz-summary.test.tsx` confirming `QuizSummary` reveals an accumulated set of refreshed topics passed to it, and nothing when the set is empty

### Implementation for User Story 4

- [X] T027 [US4] Add `refreshed: bool` to `AnswerOut`, computed via T002's `refreshed_from_bands(prior_band, posterior_band)` at the answer route, in `backend/src/api/routes/questions.py` (depends on T025, T002)
- [X] T028 [P] [US4] Create `RefreshedBanner` component in `frontend/src/components/RefreshedBanner.tsx` (depends on T026, T004)
- [X] T029 [US4] Wire `RefreshedBanner` into `frontend/src/app/practice/practice-flow.tsx`'s immediate answer-result view; in `frontend/src/app/quiz/quiz-flow.tsx`, capture (never recompute) each answer's `refreshed` value into ephemeral session-local state and pass the accumulated set to `QuizSummary` for its end-of-session reveal (research.md §5 correction -- quiz has no per-question pause to show this in immediately) (depends on T027, T028)
- [X] T030 [US4] Same accumulate-and-reveal-at-summary wiring as T029's quiz half, in `frontend/src/components/LearnerAssignments.tsx` (depends on T027, T028)

**Checkpoint**: User Stories 1-4 all work independently.

---

## Phase 6: User Story 5 - A learner sees their mastery trend for a topic (Priority: P3)

**Goal**: A topic detail view shows a small trend line built from the topic's recorded `MASTERY_UPDATED` history, degrading gracefully for single-point and no-history topics.

**Independent Test**: Request mastery history for a topic with several updates, one update, and no updates; confirm chronological points, a graceful single-point render, and an empty/no-trend render respectively.

### Tests for User Story 5

- [X] T031 [P] [US5] Integration test: mastery-history endpoint returns chronologically ordered points for a multi-update topic, a single point for a once-answered topic, and an empty list for a topic with no `MasteryState` in `backend/tests/integration/test_mastery_history.py`
- [X] T032 [P] [US5] Component test: `MasteryTrend` renders a trend line for multiple points, a graceful single-point state, and nothing for zero points in `frontend/tests/unit/mastery-trend.test.tsx`

### Implementation for User Story 5

- [X] T033 [US5] Create a mastery-history query helper mirroring `weak_area.py`'s `_build_evidence` pattern (filter by learner/subject/topic/`MASTERY_UPDATED`, order by `created_at`) in `backend/src/services/mastery/mastery_history.py` (depends on T031)
- [X] T034 [US5] Add `GET /api/learners/{learner_id}/topics/{topic_id}/mastery-history` route with `MasteryHistoryOut`/`MasteryHistoryPoint` response models in `backend/src/api/routes/mastery_history.py` (depends on T033)
- [X] T035 [P] [US5] Create `MasteryTrend` sparkline component in `frontend/src/components/MasteryTrend.tsx` (depends on T032)
- [X] T036 [US5] Add a `getMasteryHistory` API client function and wire `MasteryTrend` into the topic detail view in `frontend/src/services/api.ts` and `frontend/src/app/mastery/mastery-flow.tsx` (depends on T034, T035)

**Checkpoint**: User Stories 1-5 all work independently.

---

## Phase 7: User Story 6 - A learner sees a gentle summary of what to shore up (Priority: P3)

**Goal**: A learner-facing, softened rendering of the existing Recommendation Agent weak-area report, with an encouraging empty state.

**Independent Test**: For a learner with a known weak-area report, confirm the summary's contents match the report exactly; for an empty report, confirm the encouraging empty state.

### Tests for User Story 6

- [X] T037 [P] [US6] Component test: `WeakAreaSummary` renders weak areas matching `getRecommendations()`'s response exactly and an encouraging empty state when `weak_areas` is empty in `frontend/tests/unit/weak-area-summary.test.tsx` (a new, learner-facing component and test file -- distinct from the existing instructor-facing `weak-area-section.test.tsx`)

### Implementation for User Story 6

- [X] T038 [US6] Create `WeakAreaSummary` component consuming the existing `getRecommendations()` client call with softened, encouraging copy via `getExplanationCopyTier` in `frontend/src/components/WeakAreaSummary.tsx` (depends on T037, T004)
- [X] T039 [US6] Wire `WeakAreaSummary` into the dashboard in `frontend/src/components/DashboardSubjectSection.tsx` (depends on T038) -- replaces the raw `WeakAreaSection` on the learner's own dashboard specifically; the instructor dashboard's separate usage of `WeakAreaSection` is untouched

**Checkpoint**: All six user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Confirm zero regression and zero constitutional drift across the whole feature.

- [X] T040 [P] Run `backend/scripts/check_no_subject_conditionals.py`, confirm clean (FR-017, Constitution Principle III)
- [X] T041 [P] Run `alembic check` (or its pytest equivalent), confirm zero migration drift -- this feature ships no migration
- [X] T042 Run the full backend regression suite (`uv run pytest`), confirm no regressions against Milestones 1-22
- [X] T043 Run the full frontend regression suite (`npm test -- --run`), confirm no regressions
- [X] T044 Execute `quickstart.md`'s 6 scenarios against a real dev database and record the results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies -- start immediately. T001/T002 block US3 (T024) and US4 (T027). T003/T004 block US1 (T011), US2 (T018), US4 (T028), and US6 (T038).
- **User Stories (Phase 2-7)**: US1/US2 depend only on Foundational; US3/US4 additionally depend on T002 (`prior_band`/`refreshed_from_bands`); US5/US6 depend only on Foundational's T003/T004 (copy tier). All six stories are otherwise independent of each other and may proceed in any order once their specific Foundational prerequisites are met.
- **Polish (Phase 8)**: Depends on all six user stories being complete.

### Within Each User Story

- Tests are written first and MUST fail before the corresponding implementation task.
- Backend response-model/route changes before the frontend components that consume them.
- Story complete and checkpointed before moving to the next priority.

### Parallel Opportunities

- T001 and T003 (Foundational tests, different files/languages) can run in parallel.
- Within US1: T005, T007 in parallel (T006 is N/A); T011 in parallel with T008.
- Within US2: T015, T016 in parallel.
- Within US3: T019, T020, T021 in parallel.
- Within US4: T025, T026 in parallel; T028 in parallel with T027.
- Within US5: T031, T032 in parallel; T035 in parallel with T033/T034.
- Within Polish: T040, T041 in parallel.
- Once Foundational is done, US1, US2, US5, and US6 can all start in parallel (different files, no cross-story dependency); US3 and US4 can start as soon as T002 lands.

---

## Parallel Example: User Story 1

```bash
# Launch all three tests for User Story 1 together:
Task: "Contract test for NextQuestionOut selection-reason fields in backend/tests/contract/test_next_question_selection_reason.py"
Task: "Contract test for QuizQuestionOut selection-reason fields in backend/tests/contract/test_quiz_question_selection_reason.py"
Task: "Component test for SelectionReasonChip in frontend/tests/unit/selection-reason-chip.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2, both P1)

1. Complete Phase 1: Foundational.
2. Complete Phase 2: User Story 1 -- **STOP and VALIDATE** independently.
3. Complete Phase 3: User Story 2 -- **STOP and VALIDATE** independently.
4. Deploy/demo: both P1 explanations (why this question, decay-aware dashboard) are live.

### Incremental Delivery

1. Foundational -> US1 -> validate -> US2 -> validate -> demo (MVP: both P1 stories).
2. Add US3 -> validate -> demo (grading detail everywhere, including instructor-assigned attempts).
3. Add US4 -> validate -> demo (refreshed celebration).
4. Add US5 -> validate -> demo (mastery trend).
5. Add US6 -> validate -> demo (weak-area summary).
6. Polish: regression, drift, and constitutional gates.

Each story adds value without breaking a previously delivered one -- consistent with spec.md's own Independent Test criteria for all six stories.

---

## Notes

- No new dependency, no new migration anywhere in this task list (plan.md's Technical Context).
- T002's `refreshed_from_bands` helper exists specifically so the below-to-above-`MASTERED` check is written once and reused by both `questions.py` (T027) and `placement.py` (T024) -- never two independently-drifting copies of the same compound condition (research.md §5).
- `AnswerResultView` (US3) and the copy-tier helper (Foundational T004) are reused, not rebuilt -- per research.md's explicit "reuse before build" findings.
- `frontend/src/components/LearnerAssignments.tsx` is a genuinely separate component from `quiz-flow.tsx` (confirmed by reading it during `/speckit-analyze`), not a thin wrapper around it -- US1/US4 each carry an explicit task for it (T014, T030). US3 is the one exception: `LearnerAssignments.tsx` shares `QuizSummary`/`getQuizSummary` with `quiz-flow.tsx` directly (confirmed during Phase 4 implementation), so T022/T023 cover both flows in one change with no separate `LearnerAssignments.tsx`-specific US3 task needed.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

---

description: "Task list for Guardian Multi-Subject Cards & Practice/Tutor Shortcuts"
---

# Tasks: Guardian Multi-Subject Cards & Practice/Tutor Shortcuts

**Input**: Design documents from `/specs/044-guardian-learner-shortcuts/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md (all present)

**Tests**: Every story in this feature is a real behavior change (not a pure restyle), so each gets test tasks -- backend `pytest` for the two real-learner-gating fixes (US2, US5) and the assignments filter (US1), frontend `Vitest` for everything UI-facing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md's User Story 1-6

## Path Conventions

Web application: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/` -- matches plan.md's Project Structure exactly.

---

## Phase 1: Setup

**Purpose**: Confirm the exact existing patterns this feature mirrors, before touching any of them (zero new dependency, zero migration -- nothing else to initialize).

- [X] T001 [P] Re-read `require_learner_ownership_if_real`/`optional_session_claims` in `backend/src/services/auth/dependencies.py` and `get_next_question`'s exact `has_placement_data` bypass in `backend/src/api/routes/questions.py` (research.md §1) -- confirm the exact call shape to mirror in Phase 4/7 before writing those routes.
- [X] T002 [P] Confirm every consumer of `MyLearnerOut.enrollment`/`MyLearnerEnrollment` via `grep -rn "\.enrollment\b" frontend/src backend/src` -- expect exactly two frontend consumers (`GuardianLearnerCard.tsx`, `frontend/src/app/(auth)/guardian/settings/page.tsx`) needing an update once the shape becomes a list (Phase 2).

**Checkpoint**: Integration points confirmed -- Phase 2 can proceed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared API response-shape change every other phase's UI work builds on. Not itself a user story.

**⚠️ CRITICAL**: User Story 1 cannot start until T003 lands.

- [X] T003 Change `MyLearnerOut.enrollment: MyLearnerEnrollmentOut | None` to `enrollments: list[MyLearnerEnrollmentOut]` in `list_my_learners_route` (`backend/src/api/routes/learners.py`), returning every `(learner_id, roster)` row instead of collapsing to the first via the existing `setdefault` -- remove the `ponytail:` comment documenting the old gap (data-model.md §Enrollment, FR-001).
- [X] T004 [P] Update/add a backend test asserting a learner enrolled in two rosters gets both back as a list, in `backend/tests/integration/test_my_learners.py` (new file -- no `backend/tests/api/` directory exists in this repo; real convention is `tests/integration/`, matching `test_learner_enrollments.py`'s sibling pattern).
- [X] T005 [P] Update `MyLearnerEnrollment`/`MyLearner` TypeScript interfaces in `frontend/src/services/api.ts`: `enrollment: MyLearnerEnrollment | null` -> `enrollments: MyLearnerEnrollment[]`.
- [X] T006 [P] Update the per-learner summary line in `frontend/src/app/(auth)/guardian/settings/page.tsx` (~line 434) to read `learner.enrollments` (a list) -- e.g. join each enrollment's subject into one line, or show a count -- instead of the old singular `learner.enrollment`. `GuardianLearnerCard.tsx` itself is rewritten in Phase 3 (T011), not here.

**Checkpoint**: `GET /api/learners/mine` returns every enrollment; both non-card consumers of the old shape are fixed. User Story 1 can now proceed.

---

## Phase 3: User Story 1 - Multi-subject guardian cards (Priority: P1) 🎯 MVP

**Goal**: A learner's card on Guardian · My learners shows every enrollment, with tabs to switch and an "Add a subject" action available regardless of how many a learner already has.

**Independent Test**: Enroll one learner in two classes; confirm both appear as separate tabs on one card, each with its own stat tiles/quizzes/standards; join a third via "Add a subject" with the first two unaffected (quickstart.md Story 1).

### Tests for User Story 1

- [X] T007 [P] [US1] Test multi-enrollment tab rendering, switching, "Add a subject" always offered (even with 1+ enrollments), and no tab chrome for exactly one enrollment, in `frontend/tests/unit/guardian-learners.test.tsx`. Include one integration-style assertion that switching tabs updates stat tiles, standards, career connections, and assigned quizzes *together* (not just that each is individually filterable) (FR-002).
- [X] T008 [P] [US1] Test `GuardianLearnerStandards.tsx`/`GuardianLearnerCareerConnections.tsx`'s new `subjectId` filter (only that subject's standards/careers shown when provided) in their existing test files.
- [X] T009 [P] [US1] Test `list_learner_assignments_route`'s new `roster_id` filter (only that roster's assignments returned when provided, unfiltered when omitted) in `backend/tests/integration/test_quiz_assignment_roster_filter.py` (new file, following this repo's existing `test_quiz_assignment_*.py` naming -- no `backend/tests/api/` directory exists here).

### Implementation for User Story 1

- [X] T010 [US1] Add optional `roster_id: uuid.UUID | None = None` query param to `list_learner_assignments_route` (`backend/src/api/routes/quiz_assignments.py`), filtering `.filter(QuizAssignment.roster_id == roster_id)` when provided (research.md §3).
- [X] T011 [US1] Rewrite `frontend/src/components/GuardianLearnerCard.tsx`: `enrollment` prop becomes `enrollments: MyLearnerEnrollment[]`; add a tab row (one per enrollment) with local `selected` state defaulting to the first; render the selected enrollment's stat tiles scoped to it; "Add a subject" shown regardless of `enrollments.length`; no tab chrome when `enrollments.length === 1`; "Not in a class yet" when `enrollments.length === 0` (FR-002-FR-006). On a successful join via "Add a subject," select the newly-added tab explicitly (set `selected` to its index) while leaving every existing tab's state untouched (FR-004).
- [X] T012 [P] [US1] Add optional `subjectId?: string` prop to `GuardianLearnerStandards.tsx` -- filter the already-fetched `listLearnerEnrollments` result to that one subject before computing standards, when provided (research.md §4).
- [X] T013 [P] [US1] Same `subjectId?: string` prop addition to `GuardianLearnerCareerConnections.tsx`.
- [X] T014 [P] [US1] Update `listLearnerAssignments` in `frontend/src/services/api.ts` to accept an optional `rosterId` param, appended as a query string to match T010.
- [X] T015 [US1] Add optional `rosterId?: string` prop to `LearnerAssignments.tsx`, threaded into `listLearnerAssignments(learnerId, rosterId)` (T014).
- [X] T016 [US1] Wire `GuardianLearnerCard.tsx`'s selected tab's `subjectId`/`rosterId` into `GuardianLearnerStandards`/`GuardianLearnerCareerConnections`/`LearnerAssignments` (T012, T013, T015), so each switches with the tab.
- [X] T017 [US1] Update `frontend/src/app/(auth)/guardian/learners/page.tsx` to pass `learner.enrollments` (plural, from T003/T005) to `GuardianLearnerCard`.

**Checkpoint**: quickstart.md Story 1, steps 1-5. User Story 1 is independently functional and demoable.

---

## Phase 4: User Story 2 - One-click 15-minute practice shortcut (Priority: P2)

**Goal**: Clicking "Start practice" on a learner's subject tile lands directly on a running 15-minute timed session for that subject -- no picker.

**Depends on**: User Story 1 (the subject tile this action attaches to doesn't exist before T011).

**Independent Test**: Click "Start practice" on a tile; confirm the next screen is an active countdown with no intermediate form; confirm it works even for a subject the learner has never answered a question in before (quickstart.md Story 2).

### Tests for User Story 2

- [X] T018 [P] [US2] Test `start_practice_session` with a real `learner_id`: success case, the zero-`MasteryState` bypass (research.md §1), and `ForbiddenError` for a learner belonging to a different guardian, in `backend/tests/contract/test_practice_session_start.py` (extend existing file -- no `backend/tests/api/` directory exists here).
- [X] T019 [P] [US2] Test `get_practice_next_question`/`end_practice_session`/`get_practice_session_summary`'s new ownership check (using the session's own `learner_id`), in their respective existing files: `backend/tests/contract/test_practice_session_next_question.py`, `test_practice_session_manual_end.py`, `test_practice_session_summary.py`.
- [X] T020 [P] [US2] Test Practice's new autostart entry (skips the picker, starts a 15-minute timed session directly given a subject + real-learner session) in `frontend/tests/unit/practice-flow.test.tsx`.

### Implementation for User Story 2

- [X] T021 [US2] Add `learner_id: uuid.UUID | None = None` and `claims: SessionClaims | None = Depends(optional_session_claims)` to `start_practice_session` (`backend/src/api/routes/practice_sessions.py`); call `require_learner_ownership_if_real`; mirror `get_next_question`'s `has_placement_data` bypass for a non-demo real learner (FR-008, research.md §1).
- [X] T022 [US2] Add the same ownership check (using the already-resolved `practice_session.learner_id`, no new param needed) to `get_practice_next_question`, `end_practice_session`, `get_practice_session_summary`, same file.
- [X] T023 [P] [US2] Update `startPracticeSession` in `frontend/src/services/api.ts` to accept an optional `learnerId` param, included in the POST body when present.
- [X] T024 [US2] Add an autostart mode to `frontend/src/app/practice/practice-flow.tsx`: when a real learner session is active and a subject is supplied, skip `phase: "start"` and call `startPracticeSession(subjectId, 900, learnerId)` immediately (FR-008-FR-010).
- [X] T025 [US2] Add a "Start practice" action to each subject tile in `GuardianLearnerCard.tsx`, calling `enterRealLearnerSession` then navigating to Practice's autostart entry (T024) for that tile's subject (FR-007).

**Checkpoint**: quickstart.md Story 2. User Stories 1-2 both independently functional.

---

## Phase 5: User Story 3 - Inline AI Tutor hint on Practice (Priority: P2)

**Goal**: "Ask the AI Tutor" opens a side-panel chat on Practice itself, with a hint about the current question already sent -- no navigation to `/tutor`.

**Independent Test**: Click "Ask the AI Tutor for a hint" mid-question; confirm a side panel opens next to the (still-visible) question with a tutor response already addressing it, with no page navigation (quickstart.md Story 3).

### Tests for User Story 3

- [X] T026 [P] [US3] Test the inline panel opens on both "Ask the AI Tutor" entry points (mid-question and post-answer), auto-sends a hint referencing the current question's topic/stem, and the question stays rendered (no overlay), in `frontend/tests/unit/practice-flow.test.tsx`.
- [X] T027 [P] [US3] Test closing the panel preserves the in-progress answer/flag/read-aloud state on the question underneath, same file. Also test the get-or-create/resume case: if the learner already has an open Tutor Session for Practice's current subject, opening the panel sends the hint into that existing session rather than starting a new one (FR-017).

### Implementation for User Story 3

- [X] T028 [US3] Add a collapsible side-panel layout to `practice-flow.tsx`'s "answering" and "result" phases (split view, question always visible -- FR-013), opening/resuming a Tutor Session for Practice's current subject via the existing `openTutorSession` and mounting `TutorChat.tsx` inside it (FR-012).
- [X] T029 [US3] On opening, auto-compose and send one message through `TutorChat`'s existing submit path -- referencing the current question's topic and stem, explicitly asking for a hint not the answer -- without the learner typing first (FR-014-FR-016).
- [X] T030 [US3] Replace both "Ask the AI Tutor"/"Talk it through with the AI Tutor" plain `<Link href="/tutor">` navigations in `practice-flow.tsx` with the panel toggle from T028.

**Checkpoint**: quickstart.md Story 3. User Stories 1-3 all independently functional.

---

## Phase 6: User Story 4 - Context-relevant suggested prompts (Priority: P3)

**Goal**: Dashboard's Tutor link opens chat directly, scoped to its subject; suggested prompts everywhere reference the learner's current topic instead of generic wording.

**Independent Test**: Click a subject's "Ask the AI Tutor first" link on Dashboard; confirm chat opens with no picker step and topic-worded prompts; confirm the plain nav link still shows the picker (quickstart.md Story 4).

### Tests for User Story 4

- [X] T031 [P] [US4] Test `TutorChat`'s suggested prompts reflect an optional `currentTopicDisplayName` prop when provided, and fall back to today's generic wording when absent, in `frontend/tests/unit/tutor-chat.test.tsx`.
- [X] T032 [P] [US4] Test Dashboard's "Ask the AI Tutor first" link carries `?subject=`, and `tutor-flow.tsx` skips its picking phase when that param is present, in the existing dashboard/tutor test files.

### Implementation for User Story 4

- [X] T033 [US4] Add optional `currentTopicDisplayName?: string` prop to `TutorChat.tsx`; `SUGGESTED_PROMPTS` becomes a small function substituting the topic name into each prompt's wording when provided (FR-020/FR-021).
- [X] T034 [P] [US4] Update `DashboardSubjectSection.tsx`'s "Ask the AI Tutor first" link to `href={\`/tutor?subject=${subjectId}\`}` (FR-020).
- [X] T035 [US4] Update `tutor-flow.tsx` to read `?subject=` via `useSearchParams` (mirroring Practice's existing `urlSubjectId` pattern), skip `phase: "picking"` when present, and pass `topicPreview.next_topic.display_name` into `TutorChat`'s new prop (T033).
- [X] T036 [US4] Pass the current question's topic display name (via `formatTopicId`, or the subject's topic-priority preview) into `TutorChat` from Practice's inline panel (T028), so Story 3's panel also gets topic-worded prompts (spec Acceptance Scenario 5).

**Checkpoint**: quickstart.md Story 4. User Stories 1-4 all independently functional.

---

## Phase 7: User Story 5 - Guardian-initiated real placement (Priority: P2)

**Goal**: "Take placement" on a graded, not-yet-placed subject tile opens that subject's placement flow directly for the real learner, assigning a starting grade the same way the demo learner's already does.

**Depends on**: User Story 1 (the subject tile this action attaches to doesn't exist before T011).

**Independent Test**: Click "Take placement" on a graded subject tile with no starting grade yet; complete it; confirm a grade is assigned and the action disappears; confirm a learner who never takes it still unlocks grades organically (quickstart.md Story 5).

### Tests for User Story 5

- [X] T037 [P] [US5] Test `start_placement` with a real `learner_id`: success case and `ForbiddenError` for a different guardian's learner, in `backend/tests/integration/test_placement.py` (extend existing file -- no `backend/tests/api/` directory exists here).
- [X] T038 [P] [US5] Test the new `has_starting_grade` field on `GET /api/learners/{learner_id}/enrollments` agrees with `_assign_starting_grade_if_graded`'s own `GradeProgress`-existence guard (no drift between the two checks), in `backend/tests/integration/test_learner_enrollments.py` (extend existing file).
- [X] T039 [P] [US5] Test "Take placement" appears only for a graded, not-yet-placed subject tile and opens Placement directly, in `frontend/tests/unit/guardian-learners.test.tsx`. Also test the regression case: a second learner in the same graded subject who never takes placement can still start/answer ordinary practice questions normally, with no gating on `has_starting_grade` anywhere outside the tile-visibility check itself (FR-027).

### Implementation for User Story 5

- [X] T040 [US5] Add `learner_id: uuid.UUID | None = None` and the same ownership gate to `start_placement` (`backend/src/api/routes/placement.py`), mirroring T021 exactly (FR-025, research.md §2).
- [X] T041 [P] [US5] Update `startPlacement` in `frontend/src/services/api.ts` to accept an optional `learnerId` param.
- [X] T042 [US5] Add `has_starting_grade: bool` to `LearnerEnrollmentOut` in `list_learner_enrollments_route` (`backend/src/api/routes/rosters.py`), querying `GradeProgress` existence for that `(learner_id, subject_id)` -- same "no second round-trip" precedent `is_default_instructor_roster` already establishes on this exact response.
- [X] T043 [US5] Fetch `listLearnerEnrollments` once in `GuardianLearnerCard.tsx` (same call `GuardianAssignQuiz` already makes per-roster) and use T042's `has_starting_grade` to decide whether to show "Take placement" on each graded tile.
- [X] T044 [US5] Add the "Take placement" action to each eligible tile in `GuardianLearnerCard.tsx`, calling `enterRealLearnerSession` then navigating to `/placement?subject={subjectId}` (FR-024).

**Checkpoint**: quickstart.md Story 5. User Stories 1-5 all independently functional.

---

## Phase 8: User Story 6 - Warning before losing unsubmitted progress (Priority: P3)

**Goal**: Leaving Practice or Placement via in-app navigation while a question is unsubmitted shows a confirmation first.

**Independent Test**: Start a question, don't submit, click a Nav link; confirm a warning appears before navigating; cancel and confirm nothing was lost; confirm no warning once submitted (quickstart.md Story 6).

### Tests for User Story 6

- [X] T045 [P] [US6] Unit test for `leave-guard.ts` itself (set/clear/subscribe notify) in `frontend/tests/unit/leave-guard.test.ts`.
- [X] T046 [P] [US6] Test Nav link clicks show the confirmation when a guard is active and proceed/cancel correctly, in `frontend/tests/unit/nav.test.tsx`.
- [X] T047 [P] [US6] Test Practice/Placement set the guard while unsubmitted and clear it on submit/picker-phase/skip (never on "Next question"/skip itself), in their respective test files.

### Implementation for User Story 6

- [X] T048 [US6] Create `frontend/src/lib/leave-guard.ts`: in-memory (not `localStorage`) `setGuard(message)`/`clearGuard()`/`onGuardChange(callback)`, mirroring `visitor-state.ts`'s existing subscriber shape (research.md §5).
- [X] T049 [US6] Create `frontend/src/components/LeaveGuardDialog.tsx`: a small confirmation modal driven by the guard's active state, mounted once near the app root.
- [X] T050 [US6] Wire `practice-flow.tsx` to call `setGuard(...)` on entering "answering" with the current question unsubmitted, `clearGuard()` on submit or while on the picker (FR-028, FR-032, FR-033).
- [X] T051 [US6] Wire `placement-flow.tsx` to call `setGuard(...)` while any shown question is unsubmitted, `clearGuard()` once `submit_placement` succeeds (same FRs).
- [X] T052 [US6] Update `Nav.tsx`'s link clicks and `router.push` call sites (`handleExitDemo`, `handleExitLearnerView`, the real-learner banner's "End session" action) to check the guard first and show `LeaveGuardDialog` instead of navigating immediately when active (FR-028, FR-031).
- [X] T053 [US6] Update Practice's own "End session" link (untimed-practice path) in `practice-flow.tsx` to go through the same guard check.

**Checkpoint**: quickstart.md Story 6. All six user stories independently functional.

---

## Final Phase: Polish & Cross-Cutting Concerns

- [ ] T054 [P] Run the full existing `pytest` + `Vitest` suites; fix any regression surfaced by the `enrollments` shape change (T003/T005) or the two real-learner-gating additions (T021, T040).
- [ ] T055 Walk through quickstart.md's "Regression check" section manually: a single-enrollment learner's card, the demo learner's own Practice/Placement/Tutor flows, and assigned-quiz questions all behave exactly as before this feature.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. Blocks User Story 1 (T011 reads the new list shape).
- **User Story 1 (Phase 3)**: Depends on Foundational. Independent of every other story otherwise.
- **User Story 2 (Phase 4)**: Depends on User Story 1 (the subject tile its "Start practice" action attaches to is built in T011) -- otherwise independent.
- **User Story 3 (Phase 5)**: Independent of every other story -- does not touch `GuardianLearnerCard.tsx` at all.
- **User Story 4 (Phase 6)**: T036 (passing `currentTopicDisplayName` into Practice's inline panel) depends on User Story 3's T028 existing; otherwise independent.
- **User Story 5 (Phase 7)**: Depends on User Story 1 (same tile dependency as US2) -- otherwise independent.
- **User Story 6 (Phase 8)**: Independent of every other story -- guards Practice/Placement's existing phases, not any new UI this feature adds.
- **Polish (Final Phase)**: Depends on every story you choose to ship.

### Parallel Opportunities

- T001/T002 (Setup) in parallel.
- T004/T005/T006 (Foundational) in parallel once T003 lands.
- Within each story's Tests subsection, all `[P]` tasks in parallel.
- User Stories 3 and 6 can be built in parallel with 1/2/5 by a second developer -- neither touches `GuardianLearnerCard.tsx` or the tile structure.

---

## Parallel Example: User Story 1

```bash
# Tests together:
Task: "Test multi-enrollment tab rendering in frontend/tests/unit/guardian-learners.test.tsx"
Task: "Test subjectId filter in GuardianLearnerStandards/CareerConnections test files"
Task: "Test roster_id filter in backend/tests/integration/test_quiz_assignment_roster_filter.py"

# Independent-file implementation together (after T011 lands):
Task: "Add subjectId prop to GuardianLearnerStandards.tsx"
Task: "Add subjectId prop to GuardianLearnerCareerConnections.tsx"
Task: "Update listLearnerAssignments in frontend/src/services/api.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1).
3. **STOP and VALIDATE**: quickstart.md Story 1, independently.
4. Deploy/demo if ready -- a guardian can already see and manage every enrollment, the correctness gap this feature's Context opens with.

### Incremental Delivery

1. Setup + Foundational -> Foundation ready.
2. User Story 1 -> validate -> demo (MVP).
3. User Story 2 -> validate -> demo (practice shortcut).
4. User Story 3 -> validate -> demo (inline tutor hint) -- can be built in parallel with 2/5 by a second developer.
5. User Story 4 -> validate -> demo (contextual prompts).
6. User Story 5 -> validate -> demo (real placement).
7. User Story 6 -> validate -> demo (leave-guard warning) -- can be built in parallel with any other story.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. Developer A: User Story 1, then 2, then 5 (same `GuardianLearnerCard.tsx` file -- keep sequential to avoid merge conflicts on one component).
3. Developer B: User Story 3, then 4 (Tutor-side files, independent of A's track).
4. Developer C: User Story 6 (entirely separate files -- `leave-guard.ts`, `LeaveGuardDialog.tsx`, plus small hooks into A's and B's files once those land).

---

description: "Task list for Age-Adaptive Learner Experience"
---

# Tasks: Age-Adaptive Learner Experience

**Input**: Design documents from `specs/019-age-adaptive-learner-experience/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included per this repo's established convention (every prior
milestone's `tasks.md` writes unit/integration tests alongside
implementation, matched to specific FR/SC IDs).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3).
Unlike some prior milestones, these three stories share almost no
backend surface area (research.md's "Summary of new surface area" table)
-- US1 and US3 are additive changes with no schema/enum work at all, and
only US2 needs the new `MediationTier`/hand-off-token/`guardian_viewed_at`
plumbing. Phase 2 (Foundational) is therefore empty; each story's
schema/enum work lives inside that story's own phase.

## Phase 1: Setup

No new project, service, or dependency -- this feature extends the
existing `backend` and `frontend` in place (plan.md's Structure
Decision). Nothing to do here.

---

## Phase 2: Foundational (Blocking Prerequisites)

No shared blocking prerequisites. US1 (read-aloud), US2 (guardian
mediation), and US3 (pacing) each introduce their own, non-overlapping
surface area and can be implemented and tested in any order or in
parallel (spec.md's own "independent of whether Story X or Y are
implemented" framing for every story).

**Checkpoint**: Proceed directly to any user story phase below.

---

## Phase 3: User Story 1 - Read-aloud support for pre-fluent readers (Priority: P1) 🎯 MVP

**Goal**: A grade-1 or grade-2 learner can hear a question's full text
and every answer choice read aloud, on demand and replayable, across
every subject/question type/flow (practice, quiz, placement); no other
learner sees a forced read-aloud control.

**Independent Test**: Place a synthetic grade-1 learner in front of a
question from either seeded subject and confirm read-aloud is offered
and replayable (quickstart.md Scenario 1); confirm a grade-10 learner
sees no such control.

### Tests for User Story 1

- [ ] T001 [P] [US1] Vitest tests for the new read-aloud control in `frontend/tests/QuestionCard.test.tsx`: control renders when `readAloudEnabled` is true, absent when false; clicking play/replay does not clear `response`/navigate away (FR-002); control is entirely absent when `window.speechSynthesis` is unavailable (FR-002a)
- [ ] T002 [P] [US1] Backend unit test for the new `read_aloud_used` field in `backend/tests/unit/test_audit_log_writer.py`: `record_event` for `ANSWER_SUBMITTED` accepts and stores `read_aloud_used` in its payload, defaulting to `false` when the caller omits it
- [ ] T003 [P] [US1] Integration test in new `backend/tests/integration/test_answer_read_aloud_logging.py`: `POST /api/questions/{id}/answer` with `read_aloud_used: true` in the request body produces an `ANSWER_SUBMITTED` event whose payload includes `read_aloud_used: true`, reconstructable via a direct query (FR-012/SC-007)

### Implementation for User Story 1

- [ ] T004 [US1] Add a `readAloudEnabled: boolean` prop to `QuestionCard` in `frontend/src/components/QuestionCard.tsx`; render a read-aloud control using the browser's native `window.speechSynthesis` (`SpeechSynthesisUtterance`) that speaks the question stem and every answer choice, is replayable without limit, and renders nothing at all when `window.speechSynthesis` is undefined (FR-001, FR-002, FR-002a; research.md Decision 1)
- [ ] T005 [US1] Compute `readAloudEnabled` (`unlockedGrade <= 2`) in `frontend/src/app/practice/practice-flow.tsx`, `frontend/src/app/quiz/quiz-flow.tsx`, `frontend/src/app/placement/placement-flow.tsx`, and `frontend/src/components/LearnerAssignments.tsx`, passed down to each's `QuestionCard` usage (FR-001, FR-003) (depends on T004)
- [ ] T006 [US1] Track, per question, whether read-aloud was triggered at least once (local component state alongside `response`); include `read_aloud_used: boolean` in the existing answer-submission call in `frontend/src/services/api.ts`'s `answerQuestion` (depends on T004, T005)
- [ ] T007 [US1] Accept an optional `read_aloud_used: bool = False` field on `POST /api/questions/{question_id}/answer`'s request body in `backend/src/api/routes/questions.py`, and pass it through into the `ANSWER_SUBMITTED` event payload written via `record_event` (`backend/src/services/audit_log/writer.py`) (research.md Decision 2) (depends on T002)

**Checkpoint**: User Story 1 is fully functional and independently
testable -- read-aloud works in every flow for grades 1-2 only, and
usage is reconstructable from the audit log.

---

## Phase 4: User Story 2 - Guardian-mediation intensity by grade band (Priority: P2)

**Goal**: Every real learner's quiz session still requires a guardian to
start it (unchanged), but what happens after start now differs by
grade-band tier: co-present (1-2) keeps requiring the guardian's own
session throughout; check-in (3-5), opt-in-nudges (6-8), and independent
(9-12) each get a scoped hand-off token letting the learner's device
continue without it, differing only in what the guardian sees afterward
(summary, in-app indicator, or nothing).

**Independent Test**: Create one real guardian-learner pair per grade
band, start a quiz session for each, and confirm each pair's post-start,
mid-session, and completion behavior matches its tier (quickstart.md
Scenarios 2-3), independent of US1/US3.

### Schema and pure-function groundwork for User Story 2

- [ ] T008 [P] [US2] Add `MediationTier` enum (`CO_PRESENT`, `CHECK_IN`, `OPT_IN_NUDGES`, `INDEPENDENT`) to `backend/src/models/enums.py` (data-model.md)
- [ ] T009 [P] [US2] Add `AssessmentEventType.GUARDIAN_MEDIATION_APPLIED = "guardian_mediation_applied"` to `backend/src/models/enums.py` (data-model.md)
- [ ] T010 [P] [US2] Add `guardian_viewed_at: Mapped[datetime.datetime | None]` (nullable, no default) to `QuizAssignmentTarget` in `backend/src/models/quiz_assignment_target.py` (data-model.md)
- [ ] T011 [US2] Alembic migration in `backend/alembic/versions/<rev>_guardian_mediation_schema.py`: add `quiz_assignment_targets.guardian_viewed_at` (nullable, no backfill) and `ALTER TYPE` for the two new enum values -- additive-only (depends on T008, T009, T010)
- [ ] T012 [P] [US2] Add `determine_mediation_tier(unlocked_grade: int | None) -> MediationTier | None` (pure function) in new `backend/src/services/mediation/tier.py`: 1-2 → `CO_PRESENT`, 3-5 → `CHECK_IN`, 6-8 → `OPT_IN_NUDGES`, 9-12 → `INDEPENDENT`, `None` → `None` (research.md Decision 3) (depends on T008)
- [ ] T013 [P] [US2] Unit tests for `determine_mediation_tier` in new `backend/tests/unit/test_mediation_tier.py`, covering every band boundary (1, 2, 3, 5, 6, 8, 9, 12) plus the `None` input case (depends on T012)
- [ ] T014 [P] [US2] Add `issue_handoff_token(quiz_session_id: uuid.UUID) -> str` and `verify_handoff_token(token: str) -> uuid.UUID | None` to `backend/src/services/auth/tokens.py`: `pyjwt`-signed, `{quiz_session_id, token_type: "quiz_handoff", exp}` claims, fixed 2-hour expiry, using the same signing key already locked for guardian/instructor sessions (research.md Decision 4)
- [ ] T015 [P] [US2] Unit tests for `issue_handoff_token`/`verify_handoff_token` in new `backend/tests/unit/test_handoff_token.py`: a freshly-issued token round-trips to its `quiz_session_id`; an expired token is rejected; a malformed/mis-signed token is rejected (depends on T014)

### Tests for User Story 2

- [ ] T016 [P] [US2] Integration test in new `backend/tests/integration/test_mediation_tier_gating.py`: starting a quiz-assignment attempt for a grade-1/2 learner returns `handoff_token: null`, and a subsequent `next-question` call with no guardian cookie and no header returns `403 not_learner_guardian` (Acceptance Scenario 1)
- [ ] T017 [P] [US2] Integration test (same file): starting an attempt for a grade-4, grade-7, and grade-10 learner each returns a non-null `handoff_token`, and a subsequent `next-question`/`answer` call using only `X-Quiz-Handoff-Token` (no guardian cookie) succeeds for all three (Acceptance Scenarios 2-4, FR-005b)
- [ ] T018 [P] [US2] Integration test (same file): a handoff token presented against a different `quiz_session_id` returns `403 invalid_handoff_token`; a structurally valid token presented after its quiz session reaches `completed`/`ended_early` returns `409 quiz_session_not_in_progress` (FR-005c, Acceptance Scenario 5)
- [ ] T019 [P] [US2] Integration test in new `backend/tests/integration/test_guardian_mediation_audit.py`: `GUARDIAN_MEDIATION_APPLIED` is recorded exactly once per start attempt, with the correct `tier`/`handoff_token_issued` payload for each of the four tiers plus the `tier: null` ungraded-subject case (FR-012/SC-007, data-model.md)
- [ ] T020 [P] [US2] Integration test in new `backend/tests/integration/test_guardian_viewed_indicator.py`: for an **opt-in-nudges** (grade-7) target, `has_unviewed_activity` is `true` immediately after completion, becomes `false` the first time the guardian loads its summary, and a second summary load does not change `guardian_viewed_at`; for a **check-in** (grade-4) and an **independent** (grade-10) target, `has_unviewed_activity` is `false` at every point even while completed and unviewed, though `guardian_viewed_at` still gets set on summary view for both (FR-006/FR-007/FR-007a/FR-008, research.md Decision 7)
- [ ] T021 [P] [US2] Regression test in `backend/tests/integration/test_quiz_assignment_start_authorization.py`: a demo-learner quiz session (never assignment-linked) is completely unaffected -- start response has no behavior change from `handoff_token` being present, and no `GUARDIAN_MEDIATION_APPLIED` event is ever written for it (FR-014, SC-008)

### Implementation for User Story 2

- [ ] T022 [US2] Rename `assert_guardian_owns_assignment_session` to `assert_quiz_session_access` in `backend/src/services/quiz_assignment/assignment.py`; add a `handoff_token: str | None` parameter; implement: no-op if not assignment-linked (unchanged), else look up tier via `determine_mediation_tier`, require guardian claims if tier is `CO_PRESENT`/`None`, else accept guardian claims OR a `handoff_token` valid for this `quiz_session_id` with the session still `IN_PROGRESS` (contracts/api.md) (depends on T012, T014)
- [ ] T023 [US2] Update both call sites in `backend/src/api/routes/quiz.py` and `backend/src/api/routes/questions.py` to the renamed function, reading a new optional `X-Quiz-Handoff-Token` request header and passing it through (depends on T022)
- [ ] T024 [US2] Extend `start_assignment_attempt` in `backend/src/services/quiz_assignment/assignment.py`: after creating the `QuizSession`, call `determine_mediation_tier` on the target learner's `GradeProgress` for the assignment's subject, mint a handoff token via `issue_handoff_token` when the tier is not `CO_PRESENT`/`None`, and record a `GUARDIAN_MEDIATION_APPLIED` event with `{quiz_session_id, tier, handoff_token_issued}` (data-model.md) (depends on T009, T012, T014)
- [ ] T025 [US2] Add `handoff_token: str | None` to the assignment-attempt-start response model (`QuizStartOut` or its spec-011 equivalent) in `backend/src/api/routes/quiz_assignments.py` (contracts/api.md) (depends on T024)
- [ ] T026 [US2] In the existing `GET /api/quizzes/{quiz_session_id}` summary handler, set `quiz_assignment_targets.guardian_viewed_at = now()` the first time it's called for an assignment-linked session whose value is still `NULL` (research.md Decision 7) (depends on T011)
- [ ] T027 [US2] Add `has_unviewed_activity: bool` to each item in `GET /api/learners/{learner_id}/assignments`'s response in `backend/src/api/routes/quiz_assignments.py`, `true` only when **all three** hold: `status in (completed, ended_early)`, `guardian_viewed_at is null`, **and** `determine_mediation_tier(...)` (re-derived live for that target's learner+subject) equals `OPT_IN_NUDGES` -- `false` for check-in/independent targets even when completed and unviewed (contracts/api.md, FR-006/FR-008) (depends on T012, T026)
- [ ] T028 [US2] Update `frontend/src/services/api.ts`: `startAssignment`'s return type gains `handoff_token: string | null`; `LearnerAssignment`'s type gains `has_unviewed_activity: boolean`; `getQuizNextQuestion`/`answerQuestion` accept an optional handoff token and send it as `X-Quiz-Handoff-Token` when present (depends on T025, T027)
- [ ] T029 [US2] Update `frontend/src/components/LearnerAssignments.tsx`: store `handoff_token` from `handleStart`'s response in component state, pass it through `advanceToNextQuestion`/`handleSubmitAnswer`'s API calls for that `quizSessionId`, and render an unviewed-activity badge/dot next to any assignment with `has_unviewed_activity: true` (depends on T028)
- [ ] T030 [P] [US2] Vitest tests for the handoff-token plumbing and unviewed-activity badge in `frontend/tests/LearnerAssignments.test.tsx` (depends on T029)

**Checkpoint**: User Story 2 is fully functional and independently
testable -- every tier's post-start behavior matches spec.md, and demo
learners are provably unaffected.

---

## Phase 5: User Story 3 - Session pacing and motivation by age (Priority: P3)

**Goal**: A quiz session for an early grade band surfaces a positive-
reinforcement stopping point at a shorter recommended length; a later
grade band's quiz session imposes no such checkpoint, exactly as today.

**Independent Test**: Start a quiz session as a synthetic learner in
each of two grade bands and confirm the recommended length/reinforcement
cadence differ (quickstart.md Scenario 4), independent of US1/US2.

### Tests for User Story 3

- [ ] T031 [P] [US3] Unit tests for the pacing lookup in new `frontend/tests/pacing.test.ts`: an early grade band returns a short `recommendedQuestionCount` and frequent `reinforcementEveryN`; a late grade band returns a longer/effectively-unbounded value (research.md Decision 6)
- [ ] T032 [P] [US3] Vitest test for the stopping-point prompt in `frontend/tests/quiz-flow.test.tsx` (new or extended): reaching the recommended count for an early band shows a continue/stop prompt without ending the quiz on its own (Acceptance Scenario 1, SC-009); a later band never shows it (Acceptance Scenario 2, SC-009)

### Implementation for User Story 3

- [ ] T033 [US3] Add `frontend/src/lib/pacing.ts`: a pure function mapping grade band (using the same 1-2/3-5/6-8/9-12 boundaries as US2, independently -- no shared code with `MediationTier`, research.md Decision 6) to `{ recommendedQuestionCount: number, reinforcementEveryN: number }`
- [ ] T034 [US3] Update `frontend/src/app/quiz/quiz-flow.tsx` to consult `pacing.ts` after each answered question using the learner's `unlocked_grade`, rendering a positive-reinforcement stopping-point prompt (continue or stop, never a forced end) once the recommended count is reached (FR-009) (depends on T033)

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T035 Run all 5 `quickstart.md` scenarios end to end against a real dev database with real guardian+learner pairs across all four grade tiers
- [ ] T036 [P] Confirm Milestone 15's existing grade-banding test suite passes unmodified (SC-006)
- [ ] T037 [P] Confirm `backend/scripts/check_no_subject_conditionals.py` (Constitution Principle III) stays clean
- [ ] T038 Full backend (`pytest`) + frontend (`Vitest`) regression suite run, per this repo's "run touched tests per phase, full suite at the end" convention

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** and **Foundational (Phase 2)**: both empty -- proceed directly to any story.
- **User Stories (Phase 3-5)**: fully independent of each other (no shared schema, no shared function, no shared component beyond `QuestionCard`, which US1 alone modifies). Any order, or all three in parallel.
- **Polish (Phase 6)**: depends on whichever stories are in scope for this delivery being complete.

### Within Each User Story

- Schema/enum tasks before the pure functions that use them (US2: T008-T011 before T012, T014).
- Pure functions and their unit tests before the integration tests that exercise them end to end.
- Backend route/service changes before the frontend changes that call them (US2: T022-T027 before T028-T030).
- Story complete (all its tasks) before its Checkpoint is considered met.

### Parallel Opportunities

- All `[P]`-marked tasks within a phase touch different files and can run concurrently.
- US1, US2, and US3 can be staffed and implemented fully in parallel -- there is no cross-story file overlap (US1 touches `QuestionCard.tsx` and the answer-submission payload; US2 touches `quiz_assignment/assignment.py`, `tokens.py`, `mediation/tier.py`, and `LearnerAssignments.tsx`; US3 touches only `pacing.ts` and `quiz-flow.tsx`).

---

## Parallel Example: User Story 2's groundwork

```bash
# Launch all of US2's schema/enum/pure-function tasks together (different files):
Task: "Add MediationTier enum in backend/src/models/enums.py"
Task: "Add GUARDIAN_MEDIATION_APPLIED in backend/src/models/enums.py"
Task: "Add guardian_viewed_at column in backend/src/models/quiz_assignment_target.py"
Task: "Add issue_handoff_token/verify_handoff_token in backend/src/services/auth/tokens.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3 (User Story 1) -- read-aloud, the correctness-critical gap.
2. **STOP and VALIDATE**: run quickstart.md Scenario 1 and 5's demo/`biology` regression check.
3. Deploy/demo if ready -- US1 alone is a complete, shippable increment.

### Incremental Delivery

1. User Story 1 (read-aloud) → validate → deploy/demo.
2. User Story 2 (guardian mediation + hand-off token) → validate (Scenarios 2-3) → deploy/demo.
3. User Story 3 (pacing) → validate (Scenario 4) → deploy/demo.
4. Each story adds value without touching the others' code.

### Parallel Team Strategy

With three developers: one takes US1 (frontend-heavy, one backend field), one takes US2 (the only story with real backend/schema work), one takes US3 (frontend-only). All three can start immediately -- there is no Foundational phase blocking them.

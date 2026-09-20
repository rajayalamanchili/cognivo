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

- [X] T001 [P] [US1] Vitest tests for the new read-aloud control in `frontend/tests/unit/question-card-read-aloud.test.tsx` (actual repo convention is `frontend/tests/unit/`, not `frontend/tests/`): control renders when `readAloudEnabled` is true, absent when false; clicking play/replay does not clear `response`/call `onResponseChange` (FR-002); control is entirely absent when `window.speechSynthesis` is unavailable (FR-002a); `onReadAloudUsed` fires once even across replays. Also added equivalent coverage in `frontend/tests/unit/placement-flow.test.tsx` (placement renders its own question UI, not `QuestionCard` -- see T005 note).
- [X] T002 [P] [US1] Superseded by T003: `record_event` is a generic, unchanged function that already accepts any payload dict -- there is nothing new in it to unit-test. Its actual new behavior (the route setting `read_aloud_used` correctly) is covered end-to-end by T003's integration tests instead.
- [X] T003 [P] [US1] Integration tests in new `backend/tests/integration/test_answer_read_aloud_logging.py`: `POST /api/questions/{id}/answer` with `read_aloud_used: true` produces an `ANSWER_SUBMITTED` event whose payload includes it (reconstructable via direct query, FR-012/SC-007); omitting the field defaults to `false`; also covers `read_aloud_eligible` on the next-question response (see T005 note) for both an ineligible (real `algebra-1` grade band) and an eligible (directly-seeded `GradeProgress`) case.

### Implementation for User Story 1

- [X] T004 [US1] Added a `readAloudEnabled`/`onReadAloudUsed` prop pair to `QuestionCard` in `frontend/src/components/QuestionCard.tsx`; renders a read-aloud control via the browser's native `window.speechSynthesis`/`SpeechSynthesisUtterance` (extracted to shared `frontend/src/lib/read-aloud.ts` since `placement-flow.tsx` needed the same primitive independently, see T005), speaking the stem plus every option/step, replayable without limit, rendering nothing when `window.speechSynthesis` is undefined (FR-001, FR-002, FR-002a; research.md Decision 1). Also threaded a `readAloudUsed` prop into `FreeTextAnswerInput`/`MultiStepAnswerInput`, which submit their own answers independently of the parent flow.
- [X] T005 [US1] **Deviated from the plan**: rather than computing `readAloudEnabled` client-side from an `unlockedGrade` the frontend never actually had access to (no endpoint exposed `GradeProgress.unlocked_grade` before this feature), the backend now computes `read_aloud_eligible` per-question and returns it directly on `NextQuestionOut`/`QuizQuestionOut`/`PlacementQuestionOut` (see T007). `practice-flow.tsx`, `quiz-flow.tsx`, and `LearnerAssignments.tsx` pass `question.read_aloud_eligible` straight through to `QuestionCard`, plus `key={question.question_id}` so read-aloud state resets per question. `placement-flow.tsx` renders its own question UI (not `QuestionCard`) and got its own inline read-aloud button reading `question.read_aloud_eligible` directly, using the same shared `frontend/src/lib/read-aloud.ts` helpers (FR-001, FR-003).
- [X] T006 [US1] Tracks, per question, whether read-aloud was triggered at least once (local `readAloudUsed` state in each flow, reset alongside `response`/`flagged` on every new question); passed as a third argument to `answerQuestion()` (`frontend/src/services/api.ts`, now `(questionId, response, readAloudUsed)`) in `practice-flow.tsx`, `quiz-flow.tsx`, and `LearnerAssignments.tsx`, and as a `readAloudUsed` prop into `FreeTextAnswerInput`/`MultiStepAnswerInput` for those question types. Placement's batch `submitPlacement` call is a different endpoint/shape and was **not** wired up -- out of scope for this task as literally scoped (T007 only touches the single-answer endpoint); noted as a known gap.
- [X] T007 [US1] Added `read_aloud_used: bool = False` to `AnswerIn` in `backend/src/api/routes/questions.py`, included in all three `answer_payload` branches (free-text/multi-step/MC-numeric) written via `record_event`. Also added the read side: a new `backend/src/services/mediation/read_aloud.py` (`is_read_aloud_eligible` pure function + `resolve_read_aloud_eligible` DB-aware wrapper, shared by `questions.py` and `quiz.py` rather than duplicated) computes `read_aloud_eligible` from live `GradeProgress.unlocked_grade`; `placement.py` uses `is_read_aloud_eligible(grade)` directly against each question's own declared grade, since no `GradeProgress` row exists yet during placement itself.

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

- [X] T008 [P] [US2] Added `MediationTier` enum (`CO_PRESENT`, `CHECK_IN`, `OPT_IN_NUDGES`, `INDEPENDENT`) to `backend/src/models/enums.py` (data-model.md)
- [X] T009 [P] [US2] Added `AssessmentEventType.GUARDIAN_MEDIATION_APPLIED = "guardian_mediation_applied"` to `backend/src/models/enums.py` (data-model.md)
- [X] T010 [P] [US2] Added `guardian_viewed_at: Mapped[datetime.datetime | None]` (nullable, no default) to `QuizAssignmentTarget` in `backend/src/models/quiz_assignment_target.py` (data-model.md)
- [X] T011 [US2] Alembic migration `backend/alembic/versions/d28eac600969_guardian_mediation_schema.py`: adds `quiz_assignment_targets.guardian_viewed_at` (nullable, no backfill) and `ALTER TYPE assessment_event_type ADD VALUE 'guardian_mediation_applied'` -- additive-only. `MediationTier` needed no DB enum/migration at all (never persisted as a column, data-model.md). Applied to the dev DB; also had to run the documented `alembic stamp base` + `upgrade head` fix for this sandbox's known stamped-past-migrations flake (memory: `project_dev_db_stamped_past_migrations_flake`).
- [X] T012 [P] [US2] Added `determine_mediation_tier(unlocked_grade: int | None) -> MediationTier | None` (pure function) in new `backend/src/services/mediation/tier.py`, plus `resolve_mediation_tier(db, learner_id, subject_id)` -- the one shared DB-aware wrapper `assignment.py` and `quiz_assignments.py` both use (mirrors `read_aloud.py`'s `resolve_read_aloud_eligible` pattern from Phase 3, avoiding a 3rd/4th duplicate `GradeProgress` lookup)
- [X] T013 [P] [US2] Unit tests for `determine_mediation_tier` in new `backend/tests/unit/test_mediation_tier.py`, covering every band boundary (1, 2, 3, 5, 6, 8, 9, 12) plus the `None` input case
- [X] T014 [P] [US2] Added `issue_handoff_token(quiz_session_id) -> str` and `verify_handoff_token(token) -> uuid.UUID | None` to `backend/src/services/auth/tokens.py`: `pyjwt`-signed, `{quiz_session_id, token_type: "quiz_handoff", exp}` claims, fixed 2-hour expiry, same signing key as guardian/instructor sessions
- [X] T015 [P] [US2] Unit tests in new `backend/tests/unit/test_handoff_token.py`: round-trip, expiry (via `monkeypatch` on `_HANDOFF_TOKEN_TTL`, not real time), wrong signature (via `monkeypatch` on `_secret`), malformed token, and wrong-token-type (a real login token rejected) -- `JWT_SECRET` isn't set globally in this sandbox, so tests set it locally via `monkeypatch.setenv`, matching this repo's existing auth-test convention (`test_auth_guardian.py`)

### Tests for User Story 2

- [X] T016 [P] [US2] Integration test in new `backend/tests/integration/test_mediation_tier_gating.py`: starting a quiz-assignment attempt for a grade-1/2 learner returns `handoff_token: null`, and a subsequent `next-question` call with no guardian cookie and no header returns `403 not_learner_guardian` (Acceptance Scenario 1)
- [X] T017 [P] [US2] Integration test (same file, parametrized over grades 4/7/10): starting an attempt returns a non-null `handoff_token`, and a subsequent `next-question`/`answer` call using only `X-Quiz-Handoff-Token` (no guardian cookie) succeeds for all three (Acceptance Scenarios 2-4, FR-005b)
- [X] T018 [P] [US2] Integration tests (same file): a handoff token presented against a different `quiz_session_id` returns `403 invalid_handoff_token`; a structurally valid token presented after its quiz session reaches `completed` returns `409 quiz_session_not_in_progress` (FR-005c, Acceptance Scenario 5)
- [X] T019 [P] [US2] Integration tests in new `backend/tests/integration/test_guardian_mediation_audit.py`: `GUARDIAN_MEDIATION_APPLIED` recorded exactly once per start attempt with the correct `tier`/`handoff_token_issued` payload for all four tiers, plus a dedicated `test_ungraded_subject_records_a_null_tier_and_no_token` using `biology_subject` (a truly ungraded subject, not just "no `GradeProgress` row yet" on a graded one) for the `tier: null` case (FR-012/SC-007, data-model.md)
- [X] T020 [P] [US2] Integration tests in new `backend/tests/integration/test_guardian_viewed_indicator.py`: the opt-in-nudges (grade-7) indicator is `true` only for that tier (parametrized against grade-4/check-in and grade-10/independent, both `false`); viewing the summary clears it and is idempotent; `guardian_viewed_at` is confirmed set for check-in/independent targets too even though their badge never shows (FR-006/FR-007/FR-007a/FR-008, research.md Decision 7 -- this tier-gating was the exact bug `/speckit-analyze` caught and fixed in the design docs before implementation)
- [X] T021 [P] [US2] Regression test added to `backend/tests/integration/test_quiz_assignment_start_authorization.py`: a demo-learner quiz session (never assignment-linked) gets `handoff_token: null` and zero `GUARDIAN_MEDIATION_APPLIED` events -- distinct from an ungraded *subject*, which does get a `tier: null` event (FR-014, SC-008)

### Implementation for User Story 2

- [X] T022 [US2] Renamed `assert_guardian_owns_assignment_session` to `assert_quiz_session_access` in `backend/src/services/quiz_assignment/assignment.py`; added `handoff_token: str | None` param. No-op if not assignment-linked (unchanged); else guardian claims are always accepted (`_guardian_owns_target` helper), and for `check_in`/`opt_in_nudges`/`independent` tiers a valid `handoff_token` scoped to this exact `quiz_session_id` with the session still `IN_PROGRESS` is accepted too (contracts/api.md)
- [X] T023 [US2] Updated both call sites in `backend/src/api/routes/quiz.py` and `backend/src/api/routes/questions.py`: renamed function, added `x_quiz_handoff_token: str | None = Header(default=None)` and passed it through
- [X] T024 [US2] Extended `start_assignment_attempt`: after the claim succeeds (before question generation, so it happens regardless of an immediate ended-early outcome), resolves the tier, mints a handoff token via `issue_handoff_token` when the tier isn't `CO_PRESENT`/`None`, and records `GUARDIAN_MEDIATION_APPLIED`. Return signature changed to a 3-tuple `(QuizSession, QuizQuestionResult | None, str | None)`
- [X] T025 [US2] Added `handoff_token: str | None = None` to `QuizStartOut` in `backend/src/api/routes/quiz.py` (shared with the demo/ad-hoc route, always `null` there); updated `quiz_assignments.py`'s start route for the new 3-tuple. **Also fixed a pre-existing Phase 3 gap found while touching this exact call site**: the assignment-start route's `QuizQuestionOut(...)` construction was missing `image_url`/`image_alt_text`/`read_aloud_eligible` entirely (silently defaulting `read_aloud_eligible` to `false` for every guardian-started quiz) -- now wired to `resolve_read_aloud_eligible()`, matching `quiz.py`'s own two construction sites
- [X] T026 [US2] `GET /api/quizzes/{quiz_session_id}` now sets `guardian_viewed_at = now()` the first time it's called for an assignment-linked session with a still-`NULL` value -- unconditional on tier (this route already had no auth gate for any quiz session, demo or assigned; that didn't change)
- [X] T027 [US2] Added `has_unviewed_activity: bool` to `GET /api/learners/{learner_id}/assignments`'s response, `true` only when status is completed/ended_early AND `guardian_viewed_at is null` AND the live-resolved tier is exactly `OPT_IN_NUDGES` -- confirmed via T020 that check-in/independent targets never show it even when completed and unviewed
- [X] T028 [US2] Updated `frontend/src/services/api.ts`: `StartQuizResponse` gains `handoff_token: string | null`; `LearnerAssignment` gains `has_unviewed_activity: boolean`; `getQuizNextQuestion`/`answerQuestion` accept an optional `handoffToken` and send it via a new `handoffHeaders()` helper as `X-Quiz-Handoff-Token`. **Extended beyond the task's literal scope**: `FreeTextAnswerInput`/`MultiStepAnswerInput`/`QuestionCard` also needed a `handoffToken` prop threaded through, since those two question types submit their own answers independently of the parent flow (same reasoning as Phase 3's `readAloudUsed` threading) -- without this, a check-in/opt-in-nudges/independent-tier learner answering a free-text or multi-step question via hand-off token alone would have gotten a 403.
- [X] T029 [US2] Updated `frontend/src/components/LearnerAssignments.tsx`: stores `handoff_token` from `handleStart`'s response, passes it to `getQuizNextQuestion`/`answerQuestion` and down to `QuestionCard`, resets it on returning to the list, and renders a small dot badge (`data-testid="learner-assignment-unviewed-{id}"`) next to any assignment with `has_unviewed_activity: true`
- [X] T030 [P] [US2] Vitest tests added to `frontend/tests/unit/learner-assignments.test.tsx` (actual repo convention, not `frontend/tests/LearnerAssignments.test.tsx`): badge shown/hidden by `has_unviewed_activity`; `handoff_token` from start is threaded through to both the `answerQuestion` and `getQuizNextQuestion` calls that follow

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

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

- [X] T031 [P] [US3] Unit tests for the pacing lookup in new `frontend/tests/unit/pacing.test.ts`: an early grade band returns a short, finite `recommendedQuestionCount` with a low `reinforcementEveryN`; counts increase progressively through mid bands; a late band and a `null` (no grade-band data) both return `Infinity` (research.md Decision 6)
- [X] T032 [P] [US3] Vitest tests added to `frontend/tests/unit/quiz-flow.test.tsx`: an early band (grade 1, threshold 3) shows the stopping-point prompt after 3 answered questions without ending the quiz session or calling `getQuizSummary`, and "Keep going" continues the same session (Acceptance Scenario 1, SC-009); a late band (grade 11) never shows it after the same number of answers (Acceptance Scenario 2, SC-009)

### Implementation for User Story 3

- [X] T033 [US3] Added `frontend/src/lib/pacing.ts`: `getPacingProfile(unlockedGrade: number | null): { recommendedQuestionCount: number, reinforcementEveryN: number }`, its own independent 1-2/3-5/6-8/9-12 boundaries (no shared code with `MediationTier`) -- 1-2 -> 3 questions/every-question reinforcement, 3-5 -> 5/every-2nd, 6-8 -> 8/every-3rd, 9-12 and `null` -> `Infinity` (no checkpoint)
- [X] T034 [US3] Updated `frontend/src/app/quiz/quiz-flow.tsx`: a new `advanceAfterAnswer` helper (called from both the MC/numeric submit path and `handleFreeTextGraded`, mirroring how `readAloudUsed` was already threaded in Phase 3) increments an `answeredCount`, checks it against `getPacingProfile(currentQuestion.unlocked_grade)` *before* fetching the next question, and shows a new `"stopping-point"` phase (`data-testid="quiz-stopping-point"`) with "Keep going" (continues the same quiz session) and "I'm done for now" (a link to `/mastery`, no new backend call -- the quiz session simply stays `IN_PROGRESS`, matching spec.md's "no penalty, no partial-session state" edge case) instead of the next question (FR-009).
  **Deviated from the plan, same shape as Phase 3's `read_aloud_eligible` gap**: `quiz-flow.tsx` never had access to the learner's `unlocked_grade` at all -- no endpoint exposed it. Added a new `resolve_unlocked_grade()` resolver (`backend/src/services/mediation/grade.py`, deliberately its own module, not reusing US1's `read_aloud.py` or US2's `tier.py` -- the three stories share no backend surface area on purpose) and a new `unlocked_grade: int | None` field on `NextQuestionOut`/`QuizQuestionOut`, wired into all three question-response construction sites (`questions.py`, both in `quiz.py`, and `quiz_assignments.py`) so the shared frontend `NextQuestion` type stays honest across every flow that produces it, not just `quiz-flow.tsx`.

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T035 **Found a real gap while preparing this task**: `LearnerAssignments.tsx` -- the *only* quiz path any real (non-demo) learner ever reaches -- had no pacing/stopping-point logic at all (Phase 5 only touched the demo-only `quiz-flow.tsx`), meaning Story 3 (FR-009) was unreachable for a real learner. Fixed as part of Polish rather than deferred: ported the identical `advanceAfterAnswer`/`getPacingProfile`/stopping-point-phase pattern into `LearnerAssignments.tsx` (new `data-testid="quiz-stopping-point"` block with "Keep going"/"I'm done for now", the latter calling `handleBackToList()` directly since this component has no standalone `/mastery` context), plus a new Vitest case in `learner-assignments.test.tsx` mirroring `quiz-flow.test.tsx`'s. Also corrected `quickstart.md` Scenarios 1 and 4, which referenced a `?learner_id=` query param on `/practice`/`/quiz` that was never real -- those routes are demo-learner-only; a real learner only ever reaches a question through the guardian-started assignment flow at `/guardian/learners`. Ran the corrected scenarios' equivalent assertions via the full integration suite (every scenario's expected response shape/status is covered by `test_read_aloud_eligibility.py`, `test_mediation_tier_gating.py`, `test_guardian_mediation_audit.py`, `test_guardian_viewed_indicator.py`, `test_answer_read_aloud_logging.py`, `test_resolve_unlocked_grade.py`, and the `quiz-flow`/`learner-assignments` pacing tests) against the real dev Postgres DB rather than a separate manual curl/browser walkthrough of all four grade tiers.
- [X] T036 [P] Confirmed: Milestone 15's grade-banding suite (`test_grade_progression.py`, `test_next_topic_eligibility.py`, `test_placement.py`, `test_placement_determinism.py`, `test_placement_skip.py`, `test_sequencing.py`, `test_topic_priority_ranking.py`, `test_next_topic_fallback.py`) passes unmodified -- 37/37 (SC-006)
- [X] T037 [P] Confirmed: `uv run python scripts/check_no_subject_conditionals.py` -- `OK: no subject-id-keyed conditionals found in backend/src for ['algebra-1', 'biology']`
- [X] T038 Full backend (`pytest`) + frontend (`Vitest`) regression suite run. Frontend: 19 files/96 tests, all passing. Backend: first full run surfaced 3 pre-existing contract-test failures unrelated to this task's own code -- `test_placement_api.py`/`test_question_api.py` had stale exact-key-set assertions never updated when Phase 3/5 added `read_aloud_eligible`/`unlocked_grade` to `PlacementQuestionOut`/`NextQuestionOut` (a Phase 3/5 documentation gap, same class as T005/T025's/T034's noted deviations); fixed both. A third, `test_submit_placement_twice_returns_409`, failed only in the full-suite run with a Postgres "cache lookup failed for type" error and passed cleanly in isolation -- the known Neon-pooler stale-type-OID flake after a migration adds an enum value (this feature's `GUARDIAN_MEDIATION_APPLIED`), not a real bug. Full suite re-run clean after the two contract-test fixes.

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

---

description: "Task list for Tutor Agent Answer-Shielding"
---

# Tasks: Tutor Agent Answer-Shielding

**Input**: Design documents from `/specs/016-tutor-answer-shielding/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present)

**Tests**: Included -- matches this project's established convention (every prior milestone's `tasks.md` includes contract/integration/unit tests per user story, e.g. spec 007/010/011/012).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3, priority order) so each can be implemented and demonstrated independently.

**Revision note (2026-09-04)**: Revised after `/speckit-analyze` found five issues (0 CRITICAL, 3 HIGH, 1 MEDIUM, 1 LOW), all remediated here and in `spec.md`/`research.md`/`data-model.md`/`plan.md`: T003/T006 now explicitly cover the cancelled-instructor-assigned-attempt branch of FR-006 and the instructor-assigned-quiz case of FR-002 (findings C1/U1); T009 now requires its own explicit trace wrapper rather than reusing an already-unwrapped call site (finding I1); T017 is new, covering the cancellation-lift scenario (C1); T020 is new, building the eval fixture SC-001/SC-002/SC-004 actually require (finding C2). Finding U2 (no learner-facing shielding indicator) was resolved directly in `spec.md`'s Assumptions with no task needed.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3 -- Foundational and Polish tasks carry no story label
- Paths: `backend/`, `tutor-agent/` (both existing projects; no new project or service, per plan.md)

---

## Phase 1: Setup

**No new setup required.** This feature introduces no new dependency, package, or service (plan.md's Technical Context) -- every task below runs against `backend/`'s and `tutor-agent/`'s already-`uv sync`'d environments. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema change every user story's tests and implementation read or write against.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T001 [P] Add `shielded` (`Boolean`, not null, default `false`) and `shielded_question_id` (nullable `UUID`, FK -> `generated_questions.question_id`) columns to the `TutorExchange` model in `backend/src/models/tutor_exchange.py` (data-model.md)
- [ ] T002 Alembic migration in `backend/alembic/versions/<hash>_tutor_exchange_shielding_columns.py`: add `shielded`/`shielded_question_id` to `tutor_exchanges`, additive-only, no backfill needed (data-model.md's Migration section) (depends on T001)

**Checkpoint**: Schema ready -- user story implementation can now begin.

---

## Phase 3: User Story 1 - Tutor declines to hand over the answer to an open question (Priority: P1) 🎯 MVP

**Goal**: When a learner has a practice, quiz, or placement question open and unanswered, and asks the Tutor Agent something that would reveal its answer, the Tutor Agent responds with a hint instead -- and that decision is persisted and inspectable.

**Independent Test**: Open a practice question, leave it unanswered, ask the Tutor Agent to solve it, and verify the response is a hint (no final answer stated) and the persisted exchange shows `shielded=true` with the matching `shielded_question_id` (spec.md US1, quickstart.md Scenario 1).

### Tests for User Story 1

- [ ] T003 [P] [US1] Unit tests for `backend/src/services/tutor/shielding.py` in `backend/tests/unit/test_tutor_shielding.py`: open-question lookup across practice-, learner-initiated-quiz-, instructor-assigned-quiz-, and placement-sourced `GeneratedQuestion` rows (FR-002, each as its own asserted case, not inferred from "same table"); a cancelled instructor-assigned attempt's shown-but-unanswered question is correctly excluded from "open" (FR-006, research.md decision 1's correction); direct-or-paraphrase classification (match and no-match cases); the multi-open-question most-recently-`shown_at` tie-break; and the FR-010 fail-toward-shielding path when the classification call raises or times out
- [ ] T004 [P] [US1] Integration test in `backend/tests/integration/test_tutor_messages.py`: with a practice question open and unanswered, a tutor question asking to "just solve it" / state the answer produces a hint-only streamed response and a persisted `shielded=true` exchange with `shielded_question_id` set
- [ ] T005 [P] [US1] Extend `tutor-agent/tests/test_agent_instruction.py`: when the request includes a `shielding` payload, the instruction directs the model to ground its response in retrieved passages without stating a final answer value; assert `TUTOR_INSTRUCTION_VERSION == "v2"`

### Implementation for User Story 1

- [ ] T006 [US1] Implement the open-question lookup in `backend/src/services/tutor/shielding.py`: for a learner+subject, query `GeneratedQuestion` rows with `shown_at IS NOT NULL`, no matching `AssessmentEvent(event_type=ANSWER_SUBMITTED)` row, and (for a quiz-sourced row) no `QuizAssignmentTarget` joined to a `QuizAssignment` with `cancelled_at IS NOT NULL` (research.md decision 1 and its correction, data-model.md) -- covers practice, quiz (learner-initiated and instructor-assigned), and placement uniformly since all three set `shown_at` on the same table (depends on T001)
- [ ] T007 [US1] Implement the direct-or-paraphrase classification in `backend/src/services/tutor/shielding.py`: a local `google-adk` `LlmAgent` + `LiteLlm` call mirroring `grading_cache/equivalence.py`'s shape (structured Pydantic output, cheap model), with its own `SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION` module constant (research.md decisions 2 and 5); any error, timeout, or malformed response returns the FR-010 fail-toward-shielding result instead of raising (depends on T006)
- [ ] T008 [US1] When more than one open question matches in T007, select the most recently `shown_at` one as `shielded_question_id` (data-model.md's tie-break rule) (depends on T007)
- [ ] T009 [US1] Wire the shielding check into `prepare_message` (`backend/src/services/tutor/session.py`): call `shielding.py` after the existing moderation check and before retrieval/context bundling, wrapped in its **own** `traced_request(...)` block (research.md's tracing note, `/speckit-analyze` finding I1) -- do not place it in the same unwrapped position the (non-LLM) delegation-context lookup already occupies, since this call is a real LLM invocation and must not lose its Langfuse span the way the moderation check once did before that was fixed. When shielding applies (confident match or FR-010 fail-safe), the request assembled for `tutor-agent/` MUST include only the open question's `stem`/`topic_id`, never its `answer_key` (contracts/api.md, research.md decision 3) (depends on T007, T008)
- [ ] T010 [US1] Extend `stream_tutor_answer`'s `request_payload` construction in `backend/src/services/tutor_agent_client/client.py` to include the optional `shielding: {open_question_stem, open_question_topic_id}` key exactly as contracts/api.md specifies (depends on T009)
- [ ] T011 [US1] Add the hint-only shielding mode to `tutor-agent/src/agent.py`'s instruction: when the request's `shielding` key is present, ground the response in retrieved passages while never stating a final numeric/choice/short-answer value for `shielding.open_question_stem`; bump `TUTOR_INSTRUCTION_VERSION` from `"v1"` to `"v2"` (research.md decisions 3 and 5 -- required by `check_prompt_versioning.py`, Milestone 12) (depends on T010)
- [ ] T012 [US1] Persist `shielded`/`shielded_question_id` on the `TutorExchange` row and add the same two fields to the `TUTOR_EXCHANGE_COMPLETED` audit-log payload in `_persist_completed_exchange` (`backend/src/services/tutor/session.py`) (FR-007) (depends on T009)
- [ ] T013 [US1] Expose `shielded`/`shielded_question_id` on `ExchangeOut` and the `GET /api/tutor/exchanges/{exchange_id}` response in `backend/src/api/routes/tutor.py` (contracts/api.md, FR-007/SC-003); extend `backend/tests/integration/test_tutor_exchange_inspection.py` to assert both fields (depends on T012)

**Checkpoint**: User Story 1 is fully functional and independently testable (quickstart Scenarios 1 and 4).

---

## Phase 4: User Story 2 - Tutor keeps answering normally when nothing is being shielded (Priority: P2)

**Goal**: A tutor question unrelated to any currently-open question, or asked while no question is open at all, gets a normal, direct, grounded answer -- shielding introduces no false positives.

**Independent Test**: Ask the Tutor Agent a question unrelated to any currently-open question (or with none open) and confirm a normal answer, `shielded=false`, and no `shielding` key sent to `tutor-agent/` (spec.md US2, quickstart.md Scenario 2).

**No new implementation** -- this story validates the "no match" branch of Phase 3's `shielding.py` (T006-T009), the same way this feature's design already guarantees FR-005. Only tests are needed here.

### Tests for User Story 2

- [ ] T014 [P] [US2] Integration test in `backend/tests/integration/test_tutor_messages.py`: with a question open and unanswered, an unrelated conceptual tutor question (different topic, no restatement of the open question) receives a normal direct answer -- `shielded=false`, `shielded_question_id=null`, and no `shielding` key present in the request sent to `tutor-agent/` (depends on T013)
- [ ] T015 [P] [US2] Integration test in `backend/tests/integration/test_tutor_messages.py`: with no question currently open at all for the learner/subject, any in-scope tutor question is answered normally (depends on T013)

**Checkpoint**: User Stories 1 and 2 both work independently (quickstart Scenario 2).

---

## Phase 5: User Story 3 - Shielding lifts once the question is no longer open (Priority: P3)

**Goal**: Once a previously-open question has been answered, or its instructor-assigned attempt has been cancelled, a tutor question about it gets a normal, direct answer -- shielding never outlives the question it protected.

**Independent Test**: Answer a previously-shielded question, then re-ask the Tutor Agent about it and confirm a normal, direct answer; separately, cancel an assignment while its attempt's question is open, and confirm the same (spec.md US3, quickstart.md Scenarios 3 and 3b).

**No new implementation** -- T006's derived open-question query already excludes any question with a submitted `AssessmentEvent(ANSWER_SUBMITTED)` row or a cancelled owning assignment, so neither case is ever treated as open. Only tests are needed to prove both branches.

### Tests for User Story 3

- [ ] T016 [US3] Integration test in `backend/tests/integration/test_tutor_messages.py`: after submitting an answer to a previously-open (and previously-shielded, per US1's T004) question, a follow-up tutor question about that same question receives a normal, direct answer (depends on T013)
- [ ] T017 [US3] Integration test in `backend/tests/integration/test_tutor_messages.py`: with an instructor-assigned quiz attempt's question open and unanswered (and previously shielded), cancelling the assignment (`cancel_assignment`) then asking the Tutor Agent about that question receives a normal, direct answer -- proves FR-006's "session/attempt ended" branch independent of an answer ever being submitted (`/speckit-analyze` finding C1) (depends on T013)

**Checkpoint**: All three user stories are independently functional (quickstart Scenarios 1-4, 3b).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Constitution gates, a real measured eval against this feature's percentage-based Success Criteria, and full regression.

- [ ] T018 [P] Run `backend/scripts/check_no_subject_conditionals.py` against `backend/src/services/tutor/shielding.py` and `tutor-agent/src/agent.py` (Constitution Principle III gate -- the lookup and classification must stay subject-agnostic)
- [ ] T019 [P] Run `backend/scripts/check_prompt_versioning.py` against `backend/src/services/tutor/shielding.py` and `tutor-agent/src/agent.py` (Constitution-adjacent Milestone 12 CI gate -- confirms T007's and T011's version constants satisfy it)
- [ ] T020 Author an eval fixture (`specs/016-tutor-answer-shielding/eval/shielding-test-questions.md`: direct-ask, paraphrased-ask, unrelated-ask, and post-answer/post-cancellation-ask cases across both seeded subjects) and a script (`backend/scripts/check_shielding_eval.py`, mirroring `check_misconception_classifier_eval.py`'s honest-reporting shape) that runs it against a live/local stack with real model calls and reports the actual SC-001 (>=90% direct-ask shielded), SC-002 (100% unrelated-ask unshielded), and SC-004 (100% post-resolution normal) rates -- resolves `/speckit-analyze` finding C2, since single-example integration tests (T004/T014/T015/T016/T017) cannot themselves verify a percentage claim (depends on T013-T017)
- [ ] T021 Run the full `backend`, `tutor-agent`, `grading-agent`, and `frontend` test suites against a freshly migrated dev database; confirm SC-005 (Milestones 1-13 unmodified) and record the result in `roadmap.md`'s new milestone entry, following the precedent set by every prior milestone's DoD confirmation
- [ ] T022 Run `quickstart.md`'s scenarios end to end against a live/local stack with real model calls, including the new Scenario 3b (assignment cancellation) added alongside finding C1's fix

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None -- no new setup, proceed directly to Phase 2.
- **Foundational (Phase 2)**: No dependencies -- BLOCKS all user stories (T001/T002 must land before any story's tests can assert on the new columns).
- **User Stories (Phase 3-5)**: All depend on Foundational (Phase 2) completion.
  - US1 (Phase 3) delivers the entire mechanism -- US2 and US3 depend on US1's T013 (both test branches of the same `shielding.py`/`session.py` code US1 builds), so in practice they run after US1 completes, even though they add no new production code of their own.
- **Polish (Phase 6)**: Depends on all three user stories being complete; T020 additionally depends on T013-T017 existing (it exercises every scenario they cover, at eval scale).

### Within Each User Story

- Tests (T003-T005, T014-T015, T016-T017) are written alongside their implementation tasks; run them and confirm they fail before the corresponding implementation task (T006-T013) lands, per this project's standard practice.
- Model/schema (T001-T002) before service logic (T006-T009) before the A2A client/agent (T010-T011) before persistence/inspection (T012-T013).

### Parallel Opportunities

- T001 has no same-phase dependency and can start immediately; T002 depends on it.
- T003, T004, T005 (US1's three test tasks) touch different files and can be written in parallel once T001/T002 land.
- T014 and T015 (US2), and T016 and T017 (US3), each touch the same file (`test_tutor_messages.py`) but are independent test cases -- can be written in parallel by different people, sequenced on merge.
- T018 and T019 (Polish gates) are independent scripts and can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Once T001/T002 (Foundational) are done, launch US1's test-writing in parallel:
Task: "Unit tests for shielding.py in backend/tests/unit/test_tutor_shielding.py"
Task: "Integration test for a shielded exchange in backend/tests/integration/test_tutor_messages.py"
Task: "Extend tutor-agent/tests/test_agent_instruction.py for hint-only mode"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (no-op).
2. Complete Phase 2: Foundational (T001-T002).
3. Complete Phase 3: User Story 1 (T003-T013).
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 and confirm SC-001/SC-003 hold.
5. This alone is the feature's entire reason for existing (spec.md's own "Why this priority" for US1) -- US2/US3 harden it against false positives and stale shielding, but US1 is a demoable increment on its own.

### Incremental Delivery

1. Foundational -> US1 (MVP: shielding actually works).
2. Add US2's tests -> confirms no over-blocking regression.
3. Add US3's tests -> confirms shielding doesn't outlive its purpose, including the assignment-cancellation branch.
4. Polish (T018-T022) -> constitution gates, the actual SC-001/002/004 eval, full regression, quickstart sign-off.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- US2 and US3 are validation-only phases by design -- the spec's derived-state approach (research.md decision 1) means the "no match" and "no-longer-open" behaviors fall out of US1's implementation rather than needing separate code paths. Their tasks exist to prove that, not to build something new.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.

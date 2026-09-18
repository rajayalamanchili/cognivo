---

description: "Task list for Process-Level STEM Grading"
---

# Tasks: Process-Level STEM Grading

**Input**: Design documents from `specs/018-process-level-stem-grading/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included per this repo's established convention (every prior
milestone's `tasks.md` writes unit/integration tests alongside
implementation, matched to specific FR/SC IDs).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3)
to enable independent implementation and testing of each.

## Phase 1: Setup

No new project, service, or dependency -- this feature extends the
existing `backend`, `grading-agent`, and `frontend` in place
(plan.md's Structure Decision). Nothing to do here beyond what
Foundational already covers.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, enum, and content-artifact plumbing every user
story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T001 [P] Add `QuestionType.MULTI_STEP = "multi_step"` in `backend/src/models/enums.py` (data-model.md)
- [ ] T002 [P] Add `AssessmentEventType.STEP_COUNT_MISMATCH_REJECTED = "step_count_mismatch_rejected"` in `backend/src/models/enums.py` (data-model.md)
- [ ] T003 [P] Add `step_grading_enabled: Mapped[bool]` column (`NOT NULL`, `default=False`) to `Topic` in `backend/src/models/topic.py` (data-model.md, research.md §3)
- [ ] T004 Alembic migration in `backend/alembic/versions/<rev>_process_level_stem_grading_schema.py`: add `topics.step_grading_enabled` (`NOT NULL DEFAULT false`) and `ALTER TYPE` for the two new enum values above -- additive-only, no backfill needed beyond the column default (depends on T001, T002, T003)
- [ ] T005 Update `backend/src/services/content_artifact/validator.py`: parse and validate an optional per-topic `process_level_grading` boolean field (type-check only -- no cross-topic rule, unlike `grade_bands`' all-or-nothing check; research.md §3)
- [ ] T006 Update `backend/src/services/content_artifact/loader.py`: persist `Topic.step_grading_enabled` from the validated artifact in `persist_content_artifact` (depends on T003, T005)
- [ ] T007 [P] Unit tests for the validator's new field in `backend/tests/unit/test_content_artifact_validator.py`: `process_level_grading: true` accepted; a non-boolean value rejected; a topic that omits the field defaults to `false`; a fully valid artifact with a mix of opted-in and opted-out topics accepted (no all-or-nothing rule) (depends on T005)

**Checkpoint**: Foundation ready -- user story implementation can now begin.

---

## Phase 3: User Story 1 - A wrong answer names the step that went wrong (Priority: P1) 🎯 MVP

**Goal**: A multi-step submission is graded step by step, returning the
first step that diverges from the rubric instead of one undifferentiated
"incorrect" -- and an all-correct submission behaves exactly like any
other correct answer today.

**Independent Test**: Generate a `multi_step` question for a topic with
`step_grading_enabled: true`, submit a stepwise answer with a known-
correct setup and one wrong step, and confirm the response names that
specific step (quickstart.md Scenario 1).

### Tests for User Story 1

- [ ] T008 [P] [US1] Unit tests for `_validate_draft`'s new `MULTI_STEP` branch in `backend/tests/unit/test_assessment_gen_free_text.py` (or a new `test_assessment_gen_multi_step.py` alongside it): fewer than 2 steps rejected; a step with no criteria rejected; a step with exactly one criterion rejected (FR-005); a step whose criteria weights don't sum to ~1.0 rejected; a valid 2+-step draft with 2+ criteria per step accepted (research.md §4, FR-002/FR-010)
- [ ] T009 [P] [US1] Unit tests for `grading_client/client.py`'s new response-shape validation in `backend/tests/unit/test_grading_client_validation.py`: `graduated_score` outside `[0,1]` rejected; `step_results` longer than `first_diverging_step_index + 1` rejected (FR-006 violation); a `step_results` entry's `criteria_results` not matching that step's rubric rejected; a well-formed all-correct response and a well-formed one-wrong-step response both accepted (contracts/api.md's validation gate)
- [ ] T010 [P] [US1] Unit tests for `validate_response_shape`'s new `MULTI_STEP` branch in `backend/tests/unit/test_grading_tolerance.py` (or a new `test_multi_step_response_shape.py`): a `list[str]` of the right length accepted; a non-list response rejected; a list containing a non-string entry rejected
- [ ] T011 [P] [US1] Integration test in new `backend/tests/integration/test_multi_step_question_generation.py`: a `next-question` call against a `step_grading_enabled: true` topic returns `question_type: "multi_step"` with an ordered list of step prompts, no `answer_key` leaked to the client (mirrors `test_free_text_question_generation.py`)
- [ ] T012 [P] [US1] Integration test in new `backend/tests/integration/test_multi_step_answer_grading.py`: submitting an all-correct stepwise answer returns `correct: true`, `first_diverging_step_index: null`, one `step_results` entry per step, all correct, and the same `posterior_p_mastery` movement any other correct answer would produce (Acceptance Scenario 2); submitting an answer wrong at step 1 (of 2+) returns `first_diverging_step_index: 1` and exactly 2 `step_results` entries, not more (FR-006, SC-001); two disposable questions with the identical rubric graded with the identical submission produce byte-identical `step_results` (SC-002)
- [ ] T013 [P] [US1] Integration test in new `backend/tests/integration/test_multi_step_grading_decision_audit.py`: the `ANSWER_SUBMITTED` event's payload matches data-model.md's shape exactly (`graduated_score`, `first_diverging_step_index`, `step_results`, `grading_logic_version`), reconstructable after the fact per FR-008 (mirrors `test_free_text_grading_decision_audit.py`)
- [ ] T014 [P] [US1] Integration test in new `backend/tests/integration/test_multi_step_grading_unavailable.py`: the Grading Agent returning a malformed multi-step response on every attempt results in `503 grading_unavailable`, no `ANSWER_SUBMITTED` event written (mirrors `test_free_text_grading_unavailable.py`)
- [ ] T037 [P] [US1] Integration test in new `backend/tests/integration/test_multi_step_grading_latency.py`: a full-path `POST /answer` call for a multi-step submission (submission received to result returned) completes within 15s (SC-006), mirroring `test_free_text_grading_latency.py`'s measurement approach

### Implementation for User Story 1

- [ ] T015 [US1] Add `StepDraft` (`step_prompt: str`, `rubric_criteria: list[RubricCriterion]`) and an optional `steps: list[StepDraft] | None` field to `GeneratedQuestionDraft`; extend `_validate_draft()` with the `MULTI_STEP` branch (research.md §4) in `backend/src/agents/assessment_gen/agent.py` (depends on T001, T008)
- [ ] T016 [US1] Extend `_build_instruction()` in `backend/src/agents/assessment_gen/agent.py` with multi-step-specific prompt guidance: ask for an ordered list of steps, each with at least two weighted criteria -- one method/operation-choice criterion, one separate execution/computation-correctness criterion -- so a computational slip on a correct method is distinguishable from choosing the wrong method (FR-005, research.md §4) (depends on T015)
- [ ] T017 [US1] Extend `draft_to_answer_key()` in `backend/src/agents/assessment_gen/agent.py` (the same function that already builds free-text's `{"criteria": [...]}` shape) to build the `{"steps": [{"step_prompt": ..., "criteria": [...]}]}` shape for `MULTI_STEP` (data-model.md) (depends on T015)
- [ ] T018 [US1] Extend `grading-agent/src/agent.py`'s instruction-building (`_build_agent`/its prompt template) with a multi-step branch: given `steps` + `learner_steps`, grade each step in order against its own criteria, stop describing steps after the first incorrect one, and return `graduated_score`, `first_diverging_step_index`, and `step_results` per contracts/api.md (research.md §1, FR-003a's single-batched-call requirement)
- [ ] T019 [US1] Add `grade_stepwise_answer()` to `backend/src/services/grading_client/client.py`: builds the multi-step A2A request payload, and a new `_validate_and_parse_stepwise()` (or extend the existing one) implementing contracts/api.md's validation gate -- recomputes `graduated_score` from `step_results` independently rather than trusting the agent's reported value, rejects (retries) if they disagree or if `step_results` extends past `first_diverging_step_index` (FR-006) (depends on T009, T018)
- [ ] T020 [US1] Extend `validate_response_shape()` in `backend/src/services/mastery/grading.py` with a `MULTI_STEP` branch: response must be `list[str]` (depends on T001, T010)
- [ ] T021 [US1] Add a `multi_step` branch to `answer_question()` in `backend/src/api/routes/questions.py`: call `grade_stepwise_answer()` directly, bypassing `grading_cache/cache.py`'s semantic cache (research.md §6); feed the same `correct`/`graduated_score` into the existing `apply_mastery_update()` call unchanged; record `ANSWER_SUBMITTED` with the richer multi-step payload (depends on T017, T019, T020)
- [ ] T022 [US1] Update `frontend/src/services/api.ts` (`response` may be `string[]`, response type gains `first_diverging_step_index`/`step_results`) and add a stepwise-answer input component (one text field per step prompt) plus a per-step result display, rendered only when `question_type === "multi_step"`
- [ ] T023 [P] [US1] Vitest test for the stepwise input/result component in new `frontend/tests/unit/multi-step-question.test.tsx` (depends on T022)

**Checkpoint**: User Story 1 is fully functional and independently
testable -- a wrong step is named, an all-correct submission is
unaffected, mastery updates exactly as before.

---

## Phase 4: User Story 2 - The learner can see why a step was marked wrong (Priority: P2)

**Goal**: The graded result exposes which specific rubric criterion the
diverging step failed, not just that it failed.

**Independent Test**: Submit a stepwise answer with one wrong step,
retrieve the recorded grading decision, and confirm it cites the exact
rubric criterion that step failed (quickstart.md Scenario 1's audit-log
check).

### Tests for User Story 2

- [ ] T024 [P] [US2] Extend `test_multi_step_answer_grading.py` (T012): the response's `step_results` entry for the diverging step includes non-empty `criteria_missed` naming the specific failed criterion's description, and `criteria_met`/`criteria_missed` are correctly split per step (not aggregated across steps) (Acceptance Scenario 1); a case where the step's method criterion is met but its execution criterion is missed (correct method, computational slip) is distinguishable in the response from a case where the method criterion itself is missed (FR-005)

### Implementation for User Story 2

- [ ] T025 [US2] Confirm/extend `GradingResult`'s step-result dataclass (from T019) exposes `criteria_met`/`criteria_missed` per step (not just `met: bool`), threading the same per-step criteria-description split `_validate_and_parse()` already does for flat free-text criteria (depends on T019)
- [ ] T026 [US2] Surface `step_results[*].criteria_met`/`criteria_missed` in the `POST /answer` response body and in the stepwise result display added in T022 (depends on T021, T022, T025)

**Checkpoint**: User Stories 1 and 2 both work independently -- a wrong
step is named AND explained.

---

## Phase 5: User Story 3 - Everything that already works keeps working (Priority: P3)

**Goal**: An unopted-in topic is byte-for-byte unaffected; a step-count
mismatch is rejected before grading; the Grading Agent's step logic
redeploys independently of everything else.

**Independent Test**: Run Milestones 1-16's existing suites unmodified
against a database with this feature's migration applied and confirm
zero behavior change for `biology` (quickstart.md Scenario 4); submit a
mismatched-step-count answer and confirm rejection before grading
(quickstart.md Scenario 3).

### Tests for User Story 3

- [ ] T027 [P] [US3] Integration test in new `backend/tests/integration/test_multi_step_response_validation.py`: submitting fewer or more steps than the question's rubric expects returns `422 step_count_mismatch` with `expected_step_count`/`submitted_step_count`; a `step_count_mismatch_rejected` event is recorded, no `ANSWER_SUBMITTED` event, question remains open for resubmission (FR-012, mirrors `test_free_text_response_validation.py`/`test_free_text_length_cap.py`'s rejection-path assertions)
- [ ] T028 [P] [US3] Integration test confirming a `biology`-style ungraded topic never returns `question_type: "multi_step"` and every existing MC/numeric/free-text integration test still passes unmodified against a DB with this feature's migration applied (SC-003) -- extend `test_next_question_variety.py` or add alongside it

### Implementation for User Story 3

- [ ] T029 [US3] Add the FR-012 step-count check to `answer_question()`'s `multi_step` branch in `backend/src/api/routes/questions.py`, ordered first (cheapest, before length/rate-limit/moderation/grading per contracts/api.md's error-state ordering) -- reject with `422 step_count_mismatch` and record `step_count_mismatch_rejected` via `record_event()` (depends on T002, T021, T027)
- [ ] T030 [US3] Retrofit `backend/content/algebra-1/subject.yaml`: set `process_level_grading: true` on 1-2 naturally multi-step topics (e.g. `solving-one-step-equations` or a peer topic), author `preferred_question_types` to include `multi_step` (research.md §5) (depends on T006)
- [ ] T031 [US3] Reload `algebra-1`'s content artifact against the dev DB and confirm `biology`'s artifact still loads unchanged (SC-003 smoke check) (depends on T030)
- [ ] T032 [P] [US3] Confirm `grading-agent/`'s existing total-request-length cap (research.md §2) against a realistic multi-step payload (e.g., the 2-step example in contracts/api.md, scaled to the actual authored question from T030) -- raise the constant if it's too tight, documented in `grading-agent/src/guardrails.py`; add/extend a `grading-agent/tests/test_guardrails.py` case for a multi-step-shaped request

**Checkpoint**: All user stories independently functional. Regression
proven, not just claimed.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T033 [P] Run this repo's Constitution Principle III extensibility check (`check_no_subject_conditionals.py` or equivalent) against every file touched above -- confirm it stays clean for `['algebra-1', 'biology']`
- [ ] T034 Run `quickstart.md` Scenarios 1-5 end to end against a real dev database (Scenario 5 requires an actual `grading-agent/` redeploy -- may be simulated/documented if no live Vercel deploy is available in this environment, same honesty standard prior milestones' quickstart records used)
- [ ] T035 Run the full backend (`pytest`) and frontend (`npm test`) suites -- confirm Milestones 1-16 pass unmodified (SC-003). Per this project's convention, only the touched test files were run per phase above; this is the one full, unfiltered run.
- [ ] T036 Update `roadmap.md`'s entry for this feature (currently under "Out of current roadmap") once implementation lands -- assign it a milestone number/status per this repo's roadmap-status-line discipline, with a full Definition of Done written against spec.md's SC-001-006

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Nothing to do -- proceed straight to Foundational.
- **Foundational (Phase 2)**: BLOCKS all user stories -- schema/enum/validator must exist first.
- **User Stories (Phase 3-5)**: All depend on Foundational. US1 is the
  MVP and has no dependency on US2/US3. US2 depends on US1's
  `GradingResult`/response shape existing (T019, T021) but adds no new
  schema. US3's step-count-mismatch check (T029) is independent of
  US1/US2's grading path and could be built in parallel, but its content-
  artifact retrofit (T030) is what US1/US2's own tests need to run
  against real content -- in practice, build T030 early, alongside
  Foundational.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests written first, confirmed to fail before implementation.
- Assessment-Generation Agent (draft schema + validation) before the
  Grading Agent prompt (needs to know the rubric shape it's grading
  against) before the backend grading client (needs to know the
  Grading Agent's response shape) before the API route (wires
  everything together) before the frontend (renders what the API
  returns).

### Parallel Opportunities

- T001-T003 (Foundational schema/enum additions, different files).
- T008-T014, T037 (all US1 tests, different files) once Foundational is done.
- T024, T027, T028 (US2/US3 tests) can run alongside US1 implementation
  once Foundational is done, since they target different files.
- T032 (guardrail cap check) is independent of the rest of US3.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: "Unit tests for _validate_draft's MULTI_STEP branch in backend/tests/unit/test_assessment_gen_multi_step.py"
Task: "Unit tests for grading_client's response-shape validation in backend/tests/unit/test_grading_client_validation.py"
Task: "Unit tests for validate_response_shape's MULTI_STEP branch in backend/tests/unit/test_multi_step_response_shape.py"
Task: "Integration test for multi-step question generation in backend/tests/integration/test_multi_step_question_generation.py"
Task: "Integration test for multi-step answer grading in backend/tests/integration/test_multi_step_answer_grading.py"
Task: "Integration test for multi-step grading latency (SC-006) in backend/tests/integration/test_multi_step_grading_latency.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational.
2. Complete Phase 3: User Story 1 (including the `algebra-1` content
   retrofit, pulled forward from Phase 5 since US1's own tests need it).
3. **STOP and VALIDATE**: run quickstart.md Scenarios 1-2 against a real
   dev database.
4. Deploy/demo if ready -- this alone delivers the feature's entire
   stated value (naming the wrong step).

### Incremental Delivery

1. Foundational -> US1 (MVP: wrong step is named) -> US2 (MVP + why it
   was wrong) -> US3 (regression guarantees, step-count-mismatch
   handling, guardrail-cap confirmation) -> Polish.
2. Each story adds value without breaking the previous one -- US2 and
   US3 touch different concerns (explainability vs. regression safety)
   and don't require re-testing US1's core mechanism.

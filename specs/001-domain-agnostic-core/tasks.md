---

description: "Task list template for feature implementation"
---

# Tasks: Domain-Agnostic Core -- Content Schema, Structured Assessment, Single-Learner Mastery Model

**Input**: Design documents from `/specs/001-domain-agnostic-core/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present, spec.md/data-model.md/contracts/api.md/quickstart.md re-synced 2026-08-15 after `/speckit-clarify` and again after `/speckit-analyze` findings C1/F1/A1/E1)

**Tests**: Included. `roadmap.md`'s Milestone 1 Definition of Done makes SC-001, SC-003, SC-004, and SC-005 hard automated gates, not inspection-verified claims -- so the corresponding test tasks below are load-bearing, not optional scaffolding.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete same-phase task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are per `plan.md`'s Project Structure

## Path Conventions

Web application per plan.md: `backend/src/`, `backend/tests/`, `backend/content/`, `backend/scripts/`; `frontend/src/`, `frontend/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create backend/ and frontend/ directory skeletons per plan.md Project Structure: `backend/src/{agents/{diagnostic,sequencing,assessment_gen},models,services/{mastery,content_artifact,dedup,audit_log},api,observability}`, `backend/content/`, `backend/scripts/`, `backend/tests/{contract,integration,unit}`; `frontend/src/{components,pages,services}`, `frontend/tests/{unit,e2e}`
- [X] T002 Initialize backend Python project in `backend/pyproject.toml` (or requirements.txt) with FastAPI, google-adk, litellm, openinference-instrumentation-google-adk, langfuse, sqlalchemy, alembic, psycopg, pytest (depends on T001)
- [X] T003 [P] Initialize frontend Next.js + TypeScript project in `frontend/` with Vitest, React Testing Library, Playwright (depends on T001)
- [X] T004 [P] Configure backend linting/formatting (ruff + black) in `backend/pyproject.toml` (depends on T002)
- [X] T005 [P] Configure frontend linting/formatting (ESLint + Prettier) in `frontend/.eslintrc`, `frontend/.prettierrc` (depends on T003)
- [X] T006 [P] Create `backend/.env.example` documenting `DATABASE_URL`, `ASSESSMENT_GEN_MODEL`, `ANTHROPIC_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` per research.md (depends on T002)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 [P] Configure Alembic migrations against Postgres/Neon in `backend/alembic/` (depends on T002)
- [X] T008 [P] Create Subject model in `backend/src/models/subject.py` per data-model.md
- [X] T009 [P] Create Topic model in `backend/src/models/topic.py` per data-model.md, including `order_index` (the content artifact's authored declaration order -- the deterministic tiebreaker FR-006's next-topic selection uses)
- [X] T010 [P] Create PrerequisiteEdge model in `backend/src/models/prerequisite_edge.py` per data-model.md
- [X] T011 [P] Create MasteryState model in `backend/src/models/mastery_state.py` per data-model.md (three-band `band` derived live from `p_mastery`, never cached, not independently authoritative)
- [X] T012 [P] Create GeneratedQuestion model in `backend/src/models/generated_question.py` per data-model.md (numeric `answer_key` includes a per-question relative tolerance, e.g. `±0.5%`)
- [X] T013 [P] Create AssessmentEvent model in `backend/src/models/assessment_event.py` per data-model.md
- [X] T014 [P] Create DemoLearnerProfile model in `backend/src/models/demo_learner_profile.py` per data-model.md (`is_demo` non-nullable, explicit at creation -- Constitution Principle VIII)
- [X] T015 Generate initial Alembic migration covering all Phase 2 models in `backend/alembic/versions/`, verified via `alembic upgrade head --sql` (depends on T007-T014) -- NOTE: `alembic upgrade head` against a real database has NOT been run; no Postgres instance is available in the implementation sandbox. Run it once `DATABASE_URL` points to a provisioned instance (e.g. Neon).
- [X] T016 Implement content-artifact load-time validator (schema + cycle/reachability check, FR-002) in `backend/src/services/content_artifact/validator.py` (depends on T009, T010)
- [X] T017 Implement content-artifact loader in `backend/src/services/content_artifact/loader.py`, assigning `Topic.order_index` from declaration order and setting `validated_at` only after T016 passes (depends on T016)
- [X] T018 [P] Implement AssessmentEvent audit-log writer service in `backend/src/services/audit_log/writer.py` (depends on T013)
- [X] T019 [P] Configure ADK Postgres-backed `DatabaseSessionService` in `backend/src/observability/session.py` (depends on T002)
- [X] T020 [P] Configure Langfuse + OpenInference `GoogleADKInstrumentor` instrumentation with explicit span-flush-before-response in `backend/src/observability/tracing.py` per FR-014 (depends on T002)
- [X] T021 Create FastAPI app skeleton with routing structure and error-handling middleware in `backend/src/api/main.py` (depends on T002)
- [X] T022 [P] Implement `seed_demo_learner.py` script in `backend/scripts/seed_demo_learner.py` (sets `is_demo=true` explicitly) (depends on T014)
- [X] T023 [P] Implement `load_content_artifact.py` CLI script in `backend/scripts/load_content_artifact.py` (depends on T017)

**Checkpoint**: Foundation ready -- user story implementation can now begin.

---

## Phase 3: User Story 1 - Take a placement assessment and get a real starting mastery estimate (Priority: P1) 🎯 MVP (part 1 of 2 -- see Implementation Strategy)

**Goal**: A new learner completes placement (one dynamically generated question per entry-level topic) and receives an explicit, deterministic, per-topic mastery estimate.

**Independent Test**: Load a subject's content artifact, run the placement flow end to end with a scripted set of answers, and confirm the resulting per-topic mastery values are deterministic given those answers.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementation

- [ ] T024 [P] [US1] Integration test: placement determinism (SC-001) -- rerun identical placement answers, submitted in the same order, 10x, assert byte-identical mastery output, in `backend/tests/integration/test_placement_determinism.py`
- [ ] T025 [P] [US1] Unit test: BKT update function determinism and three-band boundary correctness (< 0.4 struggling, >= 0.4 and < 0.7 developing, >= 0.7 mastered) in `backend/tests/unit/test_mastery_bkt.py`
- [ ] T026 [P] [US1] Unit test: degenerate answer pattern -- same multiple-choice option regardless of content, and same numeric value regardless of content -- does not yield a "mastered" band for either question type (SC-005) in `backend/tests/unit/test_mastery_degenerate.py`
- [ ] T027 [P] [US1] Contract test for `POST /api/subjects/{subject_id}/placement/start` and `POST /api/placement/{id}/submit` per contracts/api.md in `backend/tests/contract/test_placement_api.py`
- [ ] T028 [P] [US1] Unit test: multiple-choice grading is exact-match; numeric grading accepts answers within the question's own relative tolerance (e.g. `±0.5%`) and rejects answers outside it (FR-009) in `backend/tests/unit/test_grading_tolerance.py`

### Implementation for User Story 1

- [ ] T029 [P] [US1] Author Algebra I content artifact (topic graph in intended authoring/tiebreak order, prerequisite edges, skill definitions, three difficulty bands) in `backend/content/algebra-1/`
- [ ] T030 [P] [US1] Implement BKT mastery model service (`p(L0)=0.3`, `p(T)=0.1`, `p(S)=0.1`, `p(G)=0.25` MC / `0.05` numeric; three-band derivation) in `backend/src/services/mastery/bkt.py` per research.md §1
- [ ] T031 [P] [US1] Implement deterministic structured-answer grading in `backend/src/services/mastery/grading.py` (FR-009): exact-match for `multiple_choice`; relative-tolerance comparison against `answer_key`'s per-question tolerance for `numeric`
- [ ] T032 [P] [US1] Implement Assessment-Generation Agent (ADK sub-agent, LiteLlm-wrapped, Claude Sonnet default) generating a structured question + answer key (numeric questions include a generated relative tolerance) + internal-consistency validation (FR-007) in `backend/src/agents/assessment_gen/agent.py`
- [ ] T033 [US1] Implement Diagnostic Agent (ADK sub-agent) selecting one placement question per entry-level topic, always requesting `"easy"` difficulty from the Assessment-Generation Agent (FR-003, FR-006's difficulty mapping -- every entry-level topic is `unknown` at placement time) in `backend/src/agents/diagnostic/agent.py` (depends on T032, T029)
- [ ] T034 [US1] Implement Sequencing Agent's mastery-update tool (applies BKT update per answer, writes MasteryState, FR-004/FR-005) in `backend/src/agents/sequencing/mastery_tool.py` (depends on T030, T031)
- [ ] T035 [US1] Implement `POST /api/subjects/{subject_id}/placement/start` endpoint in `backend/src/api/routes/placement.py` (depends on T033)
- [ ] T036 [US1] Implement `POST /api/placement/{placement_session_id}/submit` endpoint, writing `AssessmentEvent` rows per question/update (SC-006) in `backend/src/api/routes/placement.py` (depends on T034, T018, T035)
- [ ] T037 [P] [US1] Implement `GET /api/learners/{learner_id}/mastery-state` endpoint in `backend/src/api/routes/mastery.py` (depends on T011)
- [ ] T038 [P] [US1] Implement placement flow pages/components + API client in `frontend/src/pages/placement/` and `frontend/src/services/api.ts` (depends on T035, T036)
- [ ] T039 [P] [US1] Implement mastery view component in `frontend/src/components/MasteryView.tsx` (depends on T037)

**Checkpoint**: User Story 1 is independently functional and testable -- but see Implementation Strategy: spec.md frames US1+US2 together as Milestone 1's actual demoable slice.

---

## Phase 4: User Story 2 - Get the next question chosen for you, not from a fixed bank (Priority: P1) 🎯 MVP (part 2 of 2)

**Goal**: Given an established mastery state, the learner receives a newly generated, previously-unseen question calibrated to the topic/difficulty the Sequencing Agent selects.

**Independent Test**: With a mastery state already established, request the next question five times in a row for the same topic and confirm no two generated questions are text-identical, while all five remain correctly scoped to the requested topic and difficulty band.

### Tests for User Story 2 ⚠️

- [ ] T040 [P] [US2] Integration test: 5 consecutive next-question requests -- no text-identical/near-duplicate questions, 100% correctly topic-scoped (SC-002) in `backend/tests/integration/test_next_question_variety.py`
- [ ] T041 [P] [US2] Contract test for `GET /api/learners/{id}/next-question`, `POST /api/questions/{id}/answer`, `POST /api/questions/{id}/flag` per contracts/api.md in `backend/tests/contract/test_question_api.py` -- including the always-`200` fallback behavior (no `409` "no eligible topic" case)
- [ ] T042 [P] [US2] Unit test: internal-consistency validation rejects a question whose marked-correct option isn't among its listed options (SC-003) in `backend/tests/unit/test_question_validation.py`
- [ ] T043 [P] [US2] Integration test: next-topic eligibility, deterministic tie-breaking, and difficulty derivation -- an "unknown" topic becomes eligible only once every one of its prerequisites reaches "mastered"; among multiple eligible topics, the lowest-`p_mastery` one is chosen first (`unknown` ranked ahead of any numeric value), ties broken by ascending `Topic.order_index`; the returned `difficulty` is `easy` for a struggling/unknown selection and `medium` for developing (FR-006) in `backend/tests/integration/test_next_topic_eligibility.py`
- [ ] T044 [P] [US2] Integration test: zero-eligible-topics fallback -- when every topic is "mastered" or prerequisite-blocked, `next-question` returns the lowest-`p_mastery` "mastered" topic (ties broken by `Topic.order_index`) at `"hard"` difficulty, instead of an error (FR-006) in `backend/tests/integration/test_next_topic_fallback.py`

### Implementation for User Story 2

- [ ] T045 [P] [US2] Implement near-duplicate detection service (TF-IDF cosine / `difflib` over the learner's last 5 questions per topic, FR-008) in `backend/src/services/dedup/checker.py` per research.md §3
- [ ] T046 [US2] Implement Sequencing Agent's next-topic selection in `backend/src/agents/sequencing/agent.py` (FR-006, data-model.md's Next-topic eligibility rule): eligible topics are "struggling", "developing", or "unknown" with every prerequisite "mastered"; select lowest `p_mastery` first (unknown ranked ahead of any numeric value), tie-break by ascending `Topic.order_index` (same tie-break applies among tied "mastered" topics in the fallback below); if zero topics are eligible, fall back to the lowest-`p_mastery` "mastered" topic. Also derive `difficulty` from the selected topic's band per data-model.md's Difficulty-selection rule: `easy` for struggling/unknown, `medium` for developing, `hard` for a mastered-fallback selection (depends on T030, T009, T010)
- [ ] T047 [US2] Wire Assessment-Generation Agent to accept the `difficulty` value T046 derived and run the dedup check before returning a question (depends on T032, T045, T046)
- [ ] T048 [US2] Implement `GET /api/learners/{learner_id}/next-question` endpoint, always returning `200` (never a "no eligible topic" error) in `backend/src/api/routes/questions.py` (depends on T046, T047)
- [ ] T049 [P] [US2] Implement `POST /api/questions/{question_id}/answer` endpoint, invoking grading + mastery update + `AssessmentEvent` writes in `backend/src/api/routes/questions.py` (depends on T031, T034, T018)
- [ ] T050 [US2] Implement `POST /api/questions/{question_id}/flag` endpoint, excluding flagged questions from future selection (FR-011) in `backend/src/api/routes/questions.py` (depends on T048)
- [ ] T051 [P] [US2] Implement next-question flow pages/components in `frontend/src/pages/practice/` (depends on T048, T049)
- [ ] T052 [P] [US2] Implement flag-question UI affordance in `frontend/src/components/QuestionCard.tsx` (depends on T050)

**Checkpoint**: User Stories 1 AND 2 together form Milestone 1's demoable MVP slice (see Implementation Strategy).

---

## Phase 5: User Story 3 - See the engine work for a second subject with zero engine code changes (Priority: P2)

**Goal**: Prove the engine is genuinely domain-agnostic by adding a second subject's content artifact with zero engine-file changes.

**Independent Test**: Add a second subject's content artifact, with zero edits to any file outside its own content-artifact directory, and confirm placement and question generation both work correctly for it.

### Implementation for User Story 3

- [ ] T053 [P] [US3] Author Biology content artifact (topic graph in intended authoring/tiebreak order, prerequisite edges, skill definitions, three difficulty bands) in `backend/content/biology/` (depends on T016)
- [ ] T054 [P] [US3] Write automated script scanning `backend/src` engine source for subject-id-keyed conditionals (SC-004 hard gate) in `backend/scripts/check_no_subject_conditionals.py`
- [ ] T055 [US3] Integration test running the full placement + next-question flow against `subject_id=biology` in `backend/tests/integration/test_second_subject.py` (depends on T053)

**Checkpoint**: All three user stories independently functional; SC-004 extensibility gate enforced.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements and validation that span multiple user stories

- [ ] T056 [P] Implement persistent "DEMO ACCOUNT" UI badge shown on every screen in `frontend/src/components/DemoBadge.tsx` per tech-stack.md's Demo account strategy (Constitution Principle VIII) (depends on T038, T051)
- [ ] T057 [P] Integration test: full audit-log completeness for a placement-through-first-question session (SC-006) in `backend/tests/integration/test_audit_log_completeness.py`
- [ ] T058 [P] Integration test: Langfuse trace count equals agent-invocation count, no dropped spans (SC-008) in `backend/tests/integration/test_tracing_completeness.py`
- [ ] T059 [P] Implement offline batch-eval script re-validating a sample of previously generated questions for internal-consistency (SC-003 regression testing, distinct from T042's display-time unit test) in `backend/scripts/batch_eval_questions.py` per tech-stack.md's Testing & evaluation table
- [ ] T060 Configure Vercel deployment (combined FastAPI + Next.js Services) in `vercel.json` / project settings per tech-stack.md
- [ ] T061 Playwright deployment smoke test covering the placement-through-first-question flow against the live Vercel URL (SC-007) in `frontend/tests/e2e/smoke.spec.ts` (depends on T060)
- [ ] T062 Run quickstart.md validation end to end against the deployed environment and record results (depends on all prior tasks)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion -- BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion only.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; reuses US1's BKT service (T030), grading (T031), Assessment-Generation Agent (T032), and mastery-update tool (T034) but is a distinct, independently testable increment.
- **User Story 3 (Phase 5)**: Depends on Foundational completion (specifically T016's validator); independent of US1/US2 implementation beyond needing the same engine to exist.
- **Polish (Phase 6)**: Depends on the user stories it validates (T056 needs T038+T051; T059 needs T032/T042's generation+validation to exist; T061 needs T060; T062 needs everything).

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3.
- **US2 (P1)**: No hard dependency on US1's completion (Foundational is sufficient), but in practice needs an established mastery state to be meaningful -- naturally sequenced after US1 for solo implementation.
- **US3 (P2)**: No dependency on US1/US2 implementation; only needs Foundational's content-artifact validator (T016).

### Within Each User Story

- Tests written and failing before implementation.
- Models (Foundational) before services; services before agents; agents before endpoints; endpoints before frontend.

---

## Parallel Example: User Story 1

```bash
# Tests (after Foundational is complete):
Task: "Integration test: placement determinism in backend/tests/integration/test_placement_determinism.py"
Task: "Unit test: BKT update determinism in backend/tests/unit/test_mastery_bkt.py"
Task: "Unit test: degenerate answer pattern (MC + numeric) in backend/tests/unit/test_mastery_degenerate.py"
Task: "Contract test for placement endpoints in backend/tests/contract/test_placement_api.py"
Task: "Unit test: grading tolerance in backend/tests/unit/test_grading_tolerance.py"

# Independent implementation pieces:
Task: "Author Algebra I content artifact in backend/content/algebra-1/"
Task: "Implement BKT mastery model service in backend/src/services/mastery/bkt.py"
Task: "Implement deterministic grading in backend/src/services/mastery/grading.py"
Task: "Implement Assessment-Generation Agent in backend/src/agents/assessment_gen/agent.py"
```

---

## Implementation Strategy

### MVP scope: User Stories 1 AND 2 together

Both US1 and US2 are P1. Per spec.md's own reasoning ("placement without
dynamic follow-up questions wouldn't prove the core claim"), Milestone
1's actual demoable slice is US1 + US2 together, not US1 alone -- stop
after Phase 4, validate both stories' Independent Tests, and that is the
MVP checkpoint.

1. Complete Phase 1 (Setup) + Phase 2 (Foundational) -- Foundation ready.
2. Complete Phase 3 (US1) -- placement + initial mastery works standalone.
3. Complete Phase 4 (US2) -- dynamic next-question works standalone,
   including deterministic tie-breaking and the zero-eligible-topics
   fallback.
4. **STOP and VALIDATE**: run both stories' Independent Tests together
   (a full placement-through-first-follow-up-question session). This is
   Milestone 1's MVP.
5. Complete Phase 5 (US3) -- add Biology, prove zero engine-file changes
   (SC-004).
6. Complete Phase 6 (Polish) -- demo badge, audit/tracing completeness
   checks, Vercel deployment, SC-007 smoke test, full quickstart.md
   validation.

### Incremental delivery

Each phase checkpoint (end of Phase 3, 4, 5, 6) is a point where the
system is in a coherent, testable state -- suitable for a demo or a
deploy, even before Phase 6's formal Vercel/Playwright work lands.

---

## Notes

- `[P]` tasks = different files, no dependency on an incomplete same-phase task.
- `[Story]` label maps a task to its user story for traceability; Setup, Foundational, and Polish tasks carry no `[Story]` label by design.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently before continuing.
- `/speckit-analyze` MUST run before `/speckit-implement` per CLAUDE.md/Constitution Development Workflow -- do not skip it once this task list is approved.

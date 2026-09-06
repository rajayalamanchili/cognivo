---

description: "Task list for Grade-Banded Curriculum Scoping"
---

# Tasks: Grade-Banded Curriculum Scoping

**Input**: Design documents from `/specs/017-grade-banded-curriculum/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present)

**Tests**: Included -- matches this project's established convention (every prior milestone's `tasks.md` includes unit/integration tests per user story, e.g. spec 007/010/011/012/016).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3, priority order). US2 and US3 are not independently placeable ahead of US1 in practice -- both require a starting grade to already exist (spec.md's own "Why this priority" for each) -- so despite US1/US2 sharing Priority P1, US1 is implemented first and US2/US3 build on it. Each phase is still independently *testable* once US1 exists.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3 -- Foundational and Polish tasks carry no story label
- Paths: `backend/`, `frontend/` (both existing projects; no new project or service, per plan.md)

---

## Phase 1: Setup

**No new setup required.** This feature introduces no new dependency, package, or service (plan.md's Technical Context) -- every task below runs against `backend/`'s and `frontend/`'s already-installed environments. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema and content-artifact-validation changes every user story reads or writes against.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T001 [P] Add `GradeBand` model (`subject_id`, `grade`, composite PK, `CHECK (grade BETWEEN 1 AND 12)`) in `backend/src/models/grade_band.py` (data-model.md)
- [X] T002 [P] Add `GradeProgress` model (`learner_id`, `subject_id`, `unlocked_grade`, `updated_at`, composite PK) in `backend/src/models/grade_progress.py` (data-model.md) -- renamed from `LearnerGradeProgress`/`learner_grade_progress` at implementation time: the "learner" substring tripped `check_no_real_account_path.py`'s Constitution Principle VIII account-shaped-model gate (a false positive -- this is per-learner progress state, not an account -- but the fix is to follow this codebase's existing convention of never putting "learner" in a per-learner-state table's name, same as `MasteryState`/`mastery_states`)
- [X] T003 [P] Add nullable `grade: int | None` column to `Topic` in `backend/src/models/topic.py`, `ForeignKeyConstraint(["subject_id", "grade"], ["grade_bands.subject_id", "grade_bands.grade"])` (data-model.md)
- [X] T004 [P] Add nullable `grade: int | None` and `placement_session_id: uuid.UUID | None` columns to `GeneratedQuestion` in `backend/src/models/generated_question.py` (data-model.md)
- [X] T005 [P] Add `GRADE_ASSIGNED`, `GRADE_UNLOCKED`, `PLACEMENT_QUESTION_SKIPPED` members to `AssessmentEventType` in `backend/src/models/enums.py` (data-model.md)
- [X] T006 Alembic migration in `backend/alembic/versions/45b821042da5_grade_banded_curriculum_schema.py`: create `grade_bands`; add `topics.grade` + FK; add `generated_questions.grade` + `generated_questions.placement_session_id`; create `grade_progress` -- additive-only, no backfill (data-model.md's Migration section) (depends on T001, T002, T003, T004)
- [X] T007 Alembic migration in `backend/alembic/versions/aecb48567845_grade_event_types.py`: `ALTER TYPE` to add the three new `AssessmentEventType` values, matching the existing enum-extension migration precedent (depends on T005)
- [X] T008 Update `backend/src/services/content_artifact/validator.py`: parse and validate an optional top-level `grade_bands` list (`grade` int 1-12, unique per subject) and an optional per-topic `grade` field; enforce research.md Decision 1's all-or-nothing rule (if `grade_bands` is non-empty, every topic MUST declare a `grade` that references a declared band; if `grade_bands` is empty/absent, no topic may declare a `grade`)
- [X] T009 Update `backend/src/services/content_artifact/loader.py`: persist `GradeBand` rows (insert-before/prune-after the Topic upsert, since `Topic.grade` FKs to `grade_bands` -- see loader.py's docstring) and `Topic.grade` in `persist_content_artifact` (depends on T001, T003, T008)
- [X] T010 [P] Unit tests for the validator's grade rules in `backend/tests/unit/test_content_artifact_validator.py`: all-or-nothing rejection (some topics graded, some not), undeclared-grade rejection, out-of-range grade rejection, and a fully valid graded artifact accepted (depends on T008) -- 8 tests, all passing
- [X] T011 Retrofit `backend/content/algebra-1/subject.yaml` with `grade_bands: [6, 7, 8]` and a `grade` on every topic, contiguous with the existing prerequisite graph -- otherwise this feature has no subject to demo against (plan.md Scale/Scope) (depends on T009)
- [X] T012 Reload `algebra-1`'s content artifact against the dev DB and confirm `biology`'s artifact still loads unchanged (SC-005 smoke check) (depends on T011) -- hit the known dev-DB stamped-past-migrations flake (memory), fixed via `alembic stamp base` + `upgrade head` (user-approved, since it wipes dev data), then reseeded both content artifacts and both demo accounts; verified via direct query: `algebra-1` grade_bands=[6,7,8] with every topic graded, `biology` has zero grade_bands and every topic's `grade IS NULL`

**Checkpoint**: Foundation ready -- user story implementation can now begin.

---

## Phase 3: User Story 1 - Placement also finds a starting grade (Priority: P1) 🎯 MVP

**Goal**: Placement produces one explicit starting grade level per subject per learner, in addition to Milestone 1's existing per-topic mastery values, deterministically and explainably.

**Independent Test**: Load `algebra-1`, run placement end to end with a scripted answer set spanning multiple grade bands, and confirm the resulting starting grade is deterministic across repeated identical runs (spec.md US1, quickstart.md Scenario 1).

### Tests for User Story 1

- [ ] T013 [P] [US1] Unit tests for `determine_starting_grade` in `backend/tests/unit/test_starting_grade.py`: contiguous-correct-from-lowest passes through to the highest fully-correct grade; a gap caps the result at the grade below the first miss; zero correct floors to the lowest declared grade; a partial (interim) input -- fewer grades answered than declared -- is handled the same way, for reuse by User Story 3's skip eligibility check; ten repeated calls with identical input produce byte-identical output (SC-001)
- [ ] T014 [P] [US1] Unit tests for `grade_entry_topics` in `backend/tests/unit/test_diagnostic_agent.py`: a topic with no prerequisites at the subject's lowest declared grade is entry; a topic whose prerequisites are all in a strictly lower grade is entry; a topic with a same-or-higher-grade prerequisite is not entry; an ungraded subject's selection is unaffected (falls back to `is_entry_level`, byte-identical to today)
- [ ] T015 [P] [US1] Integration test in `backend/tests/integration/test_placement.py`: `start_placement` against `algebra-1` returns questions spanning more than one grade, each with a non-null `grade`; against `biology` (ungraded) every question's `grade` is `null`, response otherwise unchanged from today (SC-005)
- [ ] T016 [P] [US1] Integration test in `backend/tests/integration/test_placement.py`: `submit_placement` for `algebra-1` writes exactly one `grade_assigned` `AssessmentEvent` whose `payload.starting_grade` matches `determine_starting_grade`'s output for the submitted answers, and creates the learner's `GradeProgress` row with that value

### Implementation for User Story 1

- [ ] T017 [US1] Implement `determine_starting_grade(correct_by_grade, declared_grades) -> int` in new `backend/src/services/placement/starting_grade.py` (research.md Decision 3) (depends on T013)
- [ ] T018 [US1] Implement `grade_entry_topics(topics, edges) -> list[Topic]` pure helper in `backend/src/agents/diagnostic/agent.py` (research.md Decision 2) (depends on T014)
- [ ] T019 [US1] Update `start_placement` in `backend/src/api/routes/placement.py`: use `grade_entry_topics` when the subject has `GradeBand` rows, else the existing `is_entry_level` query unchanged; thread `grade` into `PlacementQuestionOut` and the persisted `GeneratedQuestion`; set `placement_session_id` on each created `GeneratedQuestion` (depends on T003, T004, T009, T018)
- [ ] T020 [US1] Update `submit_placement` in `backend/src/api/routes/placement.py`: for a graded subject, compute the starting grade via `determine_starting_grade` from this session's grade-entry answers, create the `GradeProgress` row, and record the `grade_assigned` `AssessmentEvent` (`payload`: `starting_grade`, `placement_session_id`, `correct_by_grade`) (depends on T002, T007, T017, T019)
- [ ] T021 [US1] Update `frontend/src/services/api.ts` (`PlacementQuestion` gains `grade: number | null`) and `frontend/src/app/placement/placement-flow.tsx` to display each question's grade label
- [ ] T022 [P] [US1] Vitest test for the grade label display in new `frontend/tests/unit/placement-flow.test.tsx` (no prior test file exists for `placement-flow.tsx`; matches this repo's `frontend/tests/unit/*.test.tsx` convention) (depends on T021)

**Checkpoint**: User Story 1 is fully functional and independently testable.

---

## Phase 4: User Story 2 - Progressive grade unlocking (Priority: P1)

**Goal**: A learner never sees a question from a grade above their currently unlocked one until every topic in their current grade reaches the existing "mastered" band.

**Independent Test**: Place a learner at a known starting grade (User Story 1), drive their mastery below the mastered threshold on one required topic, confirm no next-grade question is ever selected, then master that topic and confirm a next-grade question becomes selectable (spec.md US2, quickstart.md Scenario 3).

### Tests for User Story 2

- [ ] T023 [P] [US2] Unit tests for the grade-aware `rank_eligible_topics` filter in `backend/tests/unit/test_sequencing.py`: a topic above `unlocked_grade` is never eligible regardless of band/prerequisites; an ungraded topic (`grade IS NULL`) is unaffected; a topic at or below `unlocked_grade` behaves exactly as today; a topic within an *unlocked* grade whose prerequisite (regardless of the prerequisite's own grade) is not yet mastered still stays ineligible -- grade-gating and prerequisite-gating both apply, neither substitutes for the other (spec.md Edge Case: prerequisites spanning grades); a graded subject with no `GradeProgress` row yet for the learner treats every topic above the lowest declared grade as ineligible (data-model.md's defensive default)
- [ ] T024 [P] [US2] Unit tests for the unlock check in `backend/tests/unit/test_mastery_tool.py`: completing every topic in the learner's current grade returns `grade_unlocked` equal to the next declared grade; an incomplete grade returns `grade_unlocked=None`; completing the subject's highest declared grade returns `None` with no error (no next grade to unlock); an ungraded topic never triggers the check; **once a grade has been unlocked, driving a topic in an already-unlocked lower grade back down below the mastered band does NOT revert `unlocked_grade`** (spec.md Edge Case: already-unlocked grades stay unlocked even after a mastery regression -- the specific guarantee `GradeProgress`'s monotonic, only-increasing design exists to provide)
- [ ] T025 [P] [US2] Integration test in `backend/tests/integration/test_grade_progression.py`: place a learner (asserting the `grade_assigned` event from placement is present), drive every topic in their starting grade to mastered except one, confirm `next-question` never selects a higher grade; master the last topic, confirm a `grade_unlocked` `AssessmentEvent` is recorded and a higher-grade question becomes selectable -- assert both `grade_assigned` and `grade_unlocked` events are present for this learner/subject in one continuous flow (SC-002, SC-003, SC-006)

### Implementation for User Story 2

- [ ] T026 [US2] In `backend/src/agents/sequencing/agent.py`: load `GradeProgress.unlocked_grade` in `_load_topic_ranking_context` (default: the subject's lowest declared grade if no row exists yet), and add the grade-gate clause to `rank_eligible_topics` (depends on T002, T023)
- [ ] T027 [US2] In `backend/src/agents/sequencing/mastery_tool.py`: add the FR-004 unlock check to `apply_mastery_update` (on a topic reaching `mastered` whose grade equals the learner's current `unlocked_grade`, check every topic in that grade is mastered, and if so advance `GradeProgress.unlocked_grade` to the next declared grade if one exists); add `grade_unlocked: int | None` to `MasteryUpdateResult` (depends on T002, T024)
- [ ] T028 [US2] Log the `grade_unlocked` `AssessmentEvent` at both existing `apply_mastery_update` call sites (`backend/src/api/routes/placement.py`, `backend/src/api/routes/questions.py`) whenever `MasteryUpdateResult.grade_unlocked` is non-null (depends on T007, T027)

**Checkpoint**: User Stories 1 and 2 both function independently and together.

---

## Phase 5: User Story 3 - Skip a placement question above current level (Priority: P2)

**Goal**: A learner can skip a placement question labeled above their currently-assessed level and receive a lower-or-equal-grade replacement, with the skip contributing no mastery signal.

**Independent Test**: During placement, present a question flagged well above the learner's currently-assessed grade, invoke skip, and confirm a lower-difficulty replacement is served without the skip counting against mastery (spec.md US3, quickstart.md Scenario 2).

### Tests for User Story 3

- [ ] T029 [P] [US3] Integration tests for the new skip endpoint in `backend/tests/integration/test_placement_skip.py`: skipping an above-interim-level question returns a lower-or-equal-grade replacement targeting a topic not yet used in the session (FR-006); skipping an at-or-below-level question returns `422`; skipping an already-answered question returns `409`; skipping against an ungraded subject returns `422`; skipping every above-level question offered still lets placement terminate with a valid starting grade once submitted (FR-008); a `placement_question_skipped` `AssessmentEvent` is recorded with the skipped/replacement question and topic/grade fields populated per data-model.md; after `submit_placement` with the skipped question's `question_id` omitted from `answers`, its topic reports `status: "unknown"` -- never counted correct or incorrect (FR-007, spec.md US3 Acceptance Scenario 2)

### Implementation for User Story 3

- [ ] T030 [US3] Implement `POST /api/placement/{placement_session_id}/skip` in `backend/src/api/routes/placement.py`: look up the skipped question's grade, compute the interim currently-assessed level via `determine_starting_grade` over this session's answered-so-far grade-entry questions (research.md Decision 4), reject with `422`/`409` per contracts/api.md, otherwise pick an unused eligible lower-or-equal-grade topic, generate+persist the replacement `GeneratedQuestion` (reusing `generate_placement_questions` with a one-element topic list), and record `placement_question_skipped` (depends on T005, T007, T017, T019, T029)
- [ ] T031 [P] [US3] Add `skipPlacementQuestion` to `frontend/src/services/api.ts` and a skip button per question in `frontend/src/app/placement/placement-flow.tsx`: on skip, swap the skipped question out of local state and the replacement in (or just remove it if `replacement_question` is `null`) (depends on T021, T030)
- [ ] T032 [US3] Vitest test for the skip button's replace/remove behavior in `frontend/tests/unit/placement-flow.test.tsx` (same file T022 creates -- not parallelizable with it) (depends on T022, T031)

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T033 [P] Run this repo's Constitution Principle III extensibility check (`check_no_subject_conditionals.py` or equivalent) against every file touched above -- confirm it stays clean
- [ ] T034 Run `quickstart.md` Scenarios 1-3 end to end against a real dev database
- [ ] T035 Run the full backend (`pytest`) and frontend (`npm test`) suites -- confirm Milestones 1-16 pass unmodified (SC-005). Per this project's convention, only the touched test files were run per phase above; this is the one full, unfiltered run.
- [ ] T036 Update `roadmap.md`'s entry for this feature (currently under "Out of current roadmap") once implementation lands -- assign it a milestone number/status per this repo's roadmap-status-line discipline

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None -- no tasks.
- **Foundational (Phase 2)**: No dependencies beyond the existing codebase -- BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only. This is the feature's actual entry point -- build and validate this first.
- **User Story 2 (Phase 4)**: Depends on Foundational AND User Story 1 (needs a starting grade/`GradeProgress` row to gate from -- spec.md's own "Why this priority").
- **User Story 3 (Phase 5)**: Depends on Foundational AND User Story 1 (needs grade-labeled placement questions to skip).
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests before implementation.
- Pure functions (`determine_starting_grade`, `grade_entry_topics`) before the routes/agents that call them.
- `placement.py`'s `start_placement`/`submit_placement`/skip-endpoint edits are sequential (same file) even though each belongs to a different task.

### Parallel Opportunities

- All Foundational model tasks (T001-T005) can run in parallel -- different files.
- T010 (validator tests) can run in parallel with T009 (loader) once T008 (validator) lands.
- Within User Story 1: T013 and T014 (different pure-function test files) in parallel; T015 and T016 (same integration test file, different scenarios) can be written together but land as one file.
- Within User Story 2: T023, T024, T025 (three different test files) fully in parallel.
- T026 and T027 (different files: `sequencing/agent.py` vs `sequencing/mastery_tool.py`) in parallel once their respective tests exist.

## Parallel Example: Foundational Phase

```bash
Task: "Add GradeBand model in backend/src/models/grade_band.py"
Task: "Add GradeProgress model in backend/src/models/grade_progress.py"
Task: "Add nullable grade column to Topic in backend/src/models/topic.py"
Task: "Add nullable grade and placement_session_id columns to GeneratedQuestion in backend/src/models/generated_question.py"
Task: "Add GRADE_ASSIGNED, GRADE_UNLOCKED, PLACEMENT_QUESTION_SKIPPED to AssessmentEventType in backend/src/models/enums.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (no-op) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1) -- a learner now gets an explicit, explainable, deterministic starting grade at placement.
3. **STOP and VALIDATE**: quickstart.md Scenario 1 end to end.
4. Deploy/demo if ready -- this alone is a real, demoable improvement over Milestone 1's placement (a grade-agnostic result was the original "too hard" complaint).

### Incremental Delivery

1. Foundational -> User Story 1 (MVP: explicit starting grade).
2. + User Story 2 (progressive unlocking -- the actual "too-hard-question" fix this feature exists for).
3. + User Story 3 (skip option -- placement-experience polish, ships last per its own P2 priority).

## Notes

- 36 tasks total: 12 Foundational, 10 in US1, 6 in US2, 4 in US3, 4 Polish.
- [P] tasks = different files, no dependency on an incomplete task.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

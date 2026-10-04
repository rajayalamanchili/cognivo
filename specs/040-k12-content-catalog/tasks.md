---

description: "Task list for Full K-12 Content Catalog (Algebra II/Physics pilot)"
---

# Tasks: Full K-12 Content Catalog

**Input**: Design documents from `/specs/040-k12-content-catalog/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (all present). `contracts/README.md` documents that zero contract changes apply (research.md Decision 4).

**Tests**: Included, matching this project's established convention (every Success Criteria in this repo's specs ships with an automated check, not verified by inspection alone -- see CLAUDE.md and every prior milestone's Definition of Done in `roadmap.md`).

**Organization**: Tasks are grouped by user story (spec.md priorities). **Note on ordering**: spec.md lists User Story 1 (P1) before User Story 3 (P1), but US1's own Independent Test literally requires "a newly authored and loaded subject content artifact" to exist first -- i.e. US3's output. Phases below run US3 before US1 despite spec.md's listed order, the same honesty-over-listed-order precedent this project applied in Milestone 23 (quiz/placement corrections) and Milestone 11 (reordering train/eval). Both remain P1; this is a dependency ordering, not a priority demotion.

**Note on FR-004**: FR-004 (new subject content is authored as an LLM-assisted draft with mandatory human review before load) has no dedicated task below. It is satisfied structurally by this feature's own pull request going through this repository's existing review gate (Constitution Principle X) -- the same way Setup/Foundational phases are skipped rather than padded with inapplicable work. No new review-queue UI or workflow state exists to task against.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)

## Path Conventions

Web app split per plan.md: `backend/content/`, `backend/src/`, `backend/tests/`, `backend/scripts/`. No frontend path appears below -- plan.md/research.md Decision 4 confirm zero frontend changes (the subject picker and every flow it feeds already render generically off whatever `Subject` rows exist).

---

## Phase 1: Setup

**Skipped.** No project initialization applies: zero new dependency, framework, or directory scaffold beyond the content files Phase 3 creates directly (writing a file creates its parent directory).

## Phase 2: Foundational (Blocking Prerequisites)

**Skipped.** plan.md's Constitution Check confirms zero schema, validator, or engine change (Principle III is this feature's own proof, not a prerequisite to build). Nothing blocks User Story 3 from starting immediately.

---

## Phase 3: User Story 3 - Content author adds a new subject that passes existing validation (Priority: P1)

**Goal**: Algebra II and Physics each get a complete content artifact (topic graph, skill definitions, difficulty calibration, real standards tags, career connections) that loads and validates through the exact same gate Algebra I and Biology already pass, with zero validator code changed.

**Independent Test**: Run `scripts/load_content_artifact.py` against each new `subject.yaml` with zero changes to validator code; confirm both are accepted, and confirm a deliberately broken scratch copy is rejected with an existing error class.

### Tests for User Story 3

- [ ] T001 [P] [US3] Integration test covering: (a) `content/algebra-2/subject.yaml` and `content/physics/subject.yaml` each load successfully with 8 topics, every topic carrying a complete `skill_definition`/`difficulty_calibration`/`standards`/`career_connection`, `grade` values matching their subject's declared `grade_bands` (9-10 for algebra-2, 9-11 for physics), and at least one topic per subject declaring `free_text` or `multi_step` in `preferred_question_types`; (b) a scratch copy missing a required field on one topic is rejected with `ContentArtifactValidationError`, the same class an incomplete Algebra I/Biology artifact would raise; (c) a scratch copy where a topic's `prerequisites` names a topic from the *other* new subject is rejected as an unknown prerequisite (research.md Decision 2) -- in `backend/tests/integration/test_content_artifact_load_k12_pilot.py`. Write first; (a) fails until T002/T003 exist, (b)/(c) pass immediately since they assert existing validator behavior.

### Implementation for User Story 3

- [ ] T002 [P] [US3] Author `backend/content/algebra-2/subject.yaml`: 8 topics per research.md Decision 1 (`quadratic-equations-and-functions` through `sequences-and-series`), `grade_bands: [9, 10]`, each topic with a real `skill_definition`, three-tier `difficulty_calibration`, at least one real Common Core Math high-school-strand standards tag (research.md Decision 3), a real `career_connection`, and same-subject-only `prerequisites`. At least one topic MUST declare `free_text` and at least one MUST declare `multi_step` in `preferred_question_types` (not every topic `multiple_choice`/`numeric`-only) so the grading/misconception/caching reuse claim (FR-007) is actually exercised by this subject, mirroring `algebra-1/subject.yaml`'s own mix -- following `content/algebra-1/subject.yaml`'s exact file shape and header-comment convention (depends on T001)
- [ ] T003 [P] [US3] Author `backend/content/physics/subject.yaml`: 8 topics per research.md Decision 1 (`kinematics-motion-in-one-dimension` through `thermodynamics`), `grade_bands: [9, 10, 11]`, each topic with a real `skill_definition`, three-tier `difficulty_calibration`, at least one real NGSS high-school-Physical-Science standards tag (research.md Decision 3), a real `career_connection`, and same-subject-only `prerequisites`. At least one topic MUST declare `free_text` and at least one MUST declare `multi_step` in `preferred_question_types`, same reasoning as T002 -- following `content/biology/subject.yaml`'s exact file shape and header-comment convention (depends on T001)
- [ ] T004 [P] [US3] Run `python scripts/check_no_subject_conditionals.py` from `backend/`; confirm zero violations now that `algebra-2`/`physics` literals exist in `backend/content/` (FR-007) -- static source scan, no DB required (depends on T002, T003)
- [ ] T005 [US3] Run `python scripts/load_content_artifact.py content/algebra-2/subject.yaml` and `python scripts/load_content_artifact.py content/physics/subject.yaml` against the local dev database from `backend/`; confirm both exit `0` and `validated_at` is set on both `Subject` rows (quickstart.md Setup) (depends on T002, T003)

**Checkpoint**: Both subjects are authored, pass the existing validation gate, and are loaded into the dev database. User Story 1 can now proceed.

---

## Phase 4: User Story 1 - Learner picks from the full subject catalog (Priority: P1) 🎯 MVP (with US3)

**Goal**: A learner can select Algebra II or Physics at placement/practice start and have the full placement → practice → mastery-update loop behave identically to Algebra I/Biology, correctly gated by grade band, with graceful behavior for a subject that has no history yet.

**Independent Test**: Start placement as the demo learner against `algebra-2` (and `physics`), answer a question, and confirm mastery updates via the same deterministic Sequencing Agent path used for every existing subject.

### Tests for User Story 1

- [ ] T006 [P] [US1] Add `algebra_2_subject`/`physics_subject` fixtures to `backend/tests/conftest.py`, mirroring `algebra_subject`/`biology_subject` exactly (`load_content_artifact(db_session, "content/algebra-2/subject.yaml")` / `"content/physics/subject.yaml"`) -- new fixtures only, no edit to the two existing ones (depends on T002, T003)
- [ ] T007 [US1] Integration test: placement-start AND practice-start → answer-a-question → mastery-state-read for both `algebra-2` and `physics` (FR-005 covers both entry points, not placement alone), asserting response shape and Sequencing Agent BKT-update behavior identical to the existing `algebra-1` flow, using the new fixtures, in `backend/tests/integration/test_placement_new_subjects.py` (depends on T006)
- [ ] T008 [P] [US1] Integration test (FR-009, grade-banding): a grade-8-only learner/roster does NOT see `algebra-2` or `physics` as selectable subjects (the Algebra-I-ceiling/Algebra-II-floor edge case); a grade-9 or grade-10 learner/roster sees BOTH `algebra-2` AND `physics` as distinct, independently selectable subjects at their shared grade overlap (the grade-range-overlap edge case) -- in `backend/tests/integration/test_subject_selection_grade_filtering.py` (depends on T006)
- [ ] T009 [P] [US1] Integration test (FR-008, cold-start degradation): answering a question in `algebra-2` or `physics` with zero prior `AssessmentEvent` history produces no misconception classification and a guaranteed cache miss on first call, without raising an error -- mirroring Milestone 11's existing graceful-degradation test pattern -- in `backend/tests/integration/test_new_subject_cold_start_degradation.py` (depends on T006)

### Implementation for User Story 1

No production code changes -- plan.md/research.md Decision 4 confirm placement, practice, and mastery-update already resolve against whatever `Subject` rows exist, with no subject-id allow-list anywhere; Milestone 17's grade-banding and Milestone 11's degradation guarantee are likewise already generic. T007/T008/T009 passing *is* the implementation proof.

**Checkpoint**: Both new subjects are independently confirmed to run the full learner loop identically to Algebra I/Biology, correctly grade-gated, and safe with zero history.

---

## Phase 5: User Story 2 - Instructor rosters and assigns across the full catalog (Priority: P2)

**Goal**: An instructor can assign a quiz against Algebra II or Physics topics, and a completed attempt reports per-learner in the instructor dashboard identically to an existing-subject assignment.

**Independent Test**: Create a quiz assignment against `physics` topics for a roster, complete it as a guardian on a targeted learner's behalf, and confirm the per-learner report renders identically to an Algebra I/Biology assignment.

### Tests for User Story 2

- [ ] T010 [US2] Integration test: quiz-assignment creation against `physics` topics → guardian completes the targeted learner's attempt → instructor per-learner report, asserting response shape identical to an existing-subject assignment, using the fixtures from T006, in `backend/tests/integration/test_quiz_assignment_new_subjects.py`. Exercises `physics` only (spec.md's US2 Acceptance Scenarios name "a new subject" singular, not both) -- deliberate scope choice, not a gap (depends on T006)

### Implementation for User Story 2

No production code changes -- plan.md/research.md Decision 4 confirm quiz-assignment creation and the instructor dashboard's per-learner report already resolve against whatever `Subject`/`Topic` rows exist. T010 passing *is* the implementation proof.

**Checkpoint**: All three user stories are independently proven. The catalog has grown from 2 to 4 subjects with zero engine code touched.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T011 [P] Run the full regression suite (`backend` pytest, `grading-agent` pytest, `tutor-agent` pytest, `frontend` npm test); confirm all pass and zero existing test file was edited, only new files added (SC-005)
- [ ] T012 Run `quickstart.md`'s three scenarios end to end against a real, freshly loaded dev database (SC-001, SC-002, SC-003, SC-004)
- [ ] T013 [P] Update `roadmap.md`'s "Out of current roadmap" section: strike through the "Full K-12 STEM content catalog" bullet, noting this feature as a deliberate two-subject pilot (Algebra II, Physics) with the remaining six subjects (Pre-Algebra, Geometry, Chemistry, Earth Science, Elementary Math, Elementary Science) still explicitly deferred to a follow-up feature -- matching the strike-through promotion pattern already used for Milestones 14, 16, 17, 20, 21, 22; also note this feature in `CLAUDE.md`'s "Useful context for any session" section alongside the Standards Alignment/STEM-Career Connections entries

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: Both skipped -- no blocking prerequisite work exists for this feature.
- **User Story 3 (Phase 3)**: No dependency on any other story. Must complete before User Story 1 and User Story 2 can be tested (they need loaded content/fixtures), even though US1/US3 share priority P1.
- **User Story 1 (Phase 4)**: Depends on User Story 3's T002/T003 (content files must exist for the conftest fixtures in T006).
- **User Story 2 (Phase 5)**: Depends on T006 (same fixtures as US1); does not depend on US1's T007/T008/T009 tests themselves.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Parallel Opportunities

- T001 (test) can be written in parallel with nothing -- it's the first task, but is marked [P] since it touches a file no other task touches.
- T002 and T003 (the two subject.yaml files) are fully independent and can run in parallel.
- T004 (static conditional scan) can run in parallel with T005 (DB load) once T002/T003 exist.
- T007, T008, and T009 all depend only on T006 and write to three different files -- T008 and T009 can run in parallel with each other; T007 can run alongside both, though it is listed without [P] since it is the primary US1 flow test to review first.
- T011 and T013 in Polish are independent and can run in parallel.

---

## Parallel Example: Phase 3 (User Story 3)

```bash
# After T001 is written:
Task: "Author backend/content/algebra-2/subject.yaml per research.md Decision 1/3"
Task: "Author backend/content/physics/subject.yaml per research.md Decision 1/3"

# After both subject.yaml files exist:
Task: "Run scripts/check_no_subject_conditionals.py"
Task: "Run scripts/load_content_artifact.py against both new files"
```

## Parallel Example: Phase 4 (User Story 1)

```bash
# After T006's fixtures exist:
Task: "Grade-filtering and overlap test in test_subject_selection_grade_filtering.py"
Task: "Cold-start degradation test in test_new_subject_cold_start_degradation.py"
```

---

## Implementation Strategy

### MVP First (User Story 3 + User Story 1)

1. Complete Phase 3 (User Story 3): author and validate both new subjects.
2. Complete Phase 4 (User Story 1): confirm the full learner loop works identically for both, including grade-gating and cold-start safety.
3. **STOP and VALIDATE**: this alone proves the catalog-expansion claim for a solo learner -- a demoable increment even before instructor-assignment support is checked.

### Incremental Delivery

1. User Story 3 → both subjects exist, validated, loaded.
2. User Story 1 → learner flow proven identical to existing subjects, grade-gated correctly, safe with zero history (MVP complete).
3. User Story 2 → instructor flow proven identical to existing subjects.
4. Polish → full regression, live quickstart validation, roadmap/CLAUDE.md status update.

### Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Commit after each task or logical group, per this repo's `commit-smart-message` convention.
- Verify T001/T006/T007/T008/T009/T010 fail (or are inapplicable) before their corresponding implementation tasks land, where applicable.

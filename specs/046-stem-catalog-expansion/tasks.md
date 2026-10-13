---

description: "Task list for STEM Catalog Expansion (remaining six subjects)"
---

# Tasks: STEM Catalog Expansion (Remaining Six Subjects)

**Input**: Design documents from `/specs/046-stem-catalog-expansion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (all present). `contracts/README.md` documents zero wire-format change -- unlike Milestone 040's pilot, FR-009's roster-grade mechanism already exists and is reused unchanged.

**Tests**: Included, matching this project's established convention (every Success Criteria in this repo's specs ships with an automated check, not verified by inspection alone -- see CLAUDE.md and every prior milestone's Definition of Done in `roadmap.md`).

**Organization**: Tasks are grouped by user story (spec.md priorities). **Note on ordering**: spec.md lists User Story 1 (P1) before User Story 3 (P1), but US1's own Independent Test literally requires "a newly authored and loaded subject content artifact" to exist first -- i.e. US3's output. Phases below run US3 before US1 despite spec.md's listed order, the exact same dependency-ordering precedent Milestone 040 applied in its own tasks.md. Both remain P1; this is a dependency ordering, not a priority demotion.

**Note on FR-004**: FR-004 (new subject content is authored as an LLM-assisted draft with mandatory human review before load) has no dedicated task below -- satisfied structurally by this feature's own pull request going through this repository's existing review gate (Constitution Principle X), same as Milestone 040.

**Note on FR-009**: unlike Milestone 040 (which found this mechanism didn't exist and built it mid-implementation), this feature's FR-009 is pure reuse -- `ClassroomRoster.grade` and `_check_grade_matches_subject` already exist. Tasks below only test against the six new subjects' `grade_bands`; no model, migration, or service code is touched.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)

## Path Conventions

Web app split per plan.md: `backend/content/`, `backend/tests/`. No frontend path appears below -- plan.md/research.md Decision 4 confirm zero frontend changes (the subject picker and every flow it feeds already render generically off whatever `Subject` rows exist). No `backend/src/` or `backend/alembic/versions/` path appears either -- unlike Milestone 040, this feature touches zero engine/schema code.

---

## Phase 1: Setup

**Skipped.** No project initialization applies: zero new dependency or framework.

## Phase 2: Foundational (Blocking Prerequisites)

**Skipped.** Nothing blocks User Story 3 from starting immediately.

---

## Phase 3: User Story 3 - Content author adds the remaining six subjects, each passing existing validation (Priority: P1)

**Goal**: Pre-Algebra, Geometry, Chemistry, Earth Science, Elementary Math, and Elementary Science each get a complete content artifact (topic graph, skill definitions, difficulty calibration, real standards tags, career connections) that loads and validates through the exact same gate the four existing subjects already pass, with zero validator code changed.

**Independent Test**: Run `scripts/load_content_artifact.py` against each new `subject.yaml` with zero changes to validator code; confirm all six are accepted, and confirm a deliberately broken scratch copy is rejected with an existing error class.

### Tests for User Story 3

- [X] T001 [P] [US3] Integration test covering: (a) all six new `subject.yaml` files each load successfully with 8 topics, every topic carrying a complete `skill_definition`/`difficulty_calibration`/`standards`/`career_connection`, `grade` values matching that subject's declared `grade_bands` (research.md Decision 1 -- Pre-Algebra 6-7, Geometry 9-10, Chemistry 9-10, Earth Science 6, Elementary Math 1-5, Elementary Science 1-5); (a1) Pre-Algebra, Geometry, Chemistry, and Earth Science each have at least one topic declaring `free_text` and one declaring `multi_step` in `preferred_question_types`; (a2) Elementary Math and Elementary Science have **zero** topics declaring `free_text` or `multi_step` -- confirming the Edge Case ("a new subject has no free-text-capable topics at all") is real for this feature, not hypothetical; (b) a scratch copy missing a required field on one topic is rejected with `ContentArtifactValidationError`, the same class an incomplete existing-subject artifact would raise; (c) a scratch copy where a topic's `prerequisites` names a topic from a *different* subject (e.g. Geometry referencing Pre-Algebra) is rejected as an unknown prerequisite (research.md Decision 2); (d) a scratch copy where one subject's own topics form a same-subject `prerequisites` cycle is rejected before load, the same error class every existing subject's cycle-check already produces (spec.md US3 Acceptance Scenario 2) -- in `backend/tests/integration/test_content_artifact_load_stem_catalog_expansion.py`.

### Implementation for User Story 3

- [X] T002 [P] [US3] Author `backend/content/pre-algebra/subject.yaml`: 8 topics per research.md Decision 1, `grade_bands: [6, 7]`, each topic complete, at least one `free_text` and one `multi_step` topic (FR-007 exercise requirement), real Common Core grade-numbered standards codes (research.md Decision 3).
- [X] T003 [P] [US3] Author `backend/content/geometry/subject.yaml`: 8 topics per research.md Decision 1, `grade_bands: [9, 10]`, same completeness/free_text/multi_step requirement, real Common Core high-school Geometry strand codes.
- [X] T004 [P] [US3] Author `backend/content/chemistry/subject.yaml`: 8 topics per research.md Decision 1, `grade_bands: [9, 10]`, same completeness/free_text/multi_step requirement, real NGSS high-school Physical Science codes.
- [X] T005 [P] [US3] Author `backend/content/earth-science/subject.yaml`: 8 topics per research.md Decision 1, `grade_bands: [6]`, same completeness/free_text/multi_step requirement, real NGSS middle-school Earth and Space Science codes.
- [X] T006 [P] [US3] Author `backend/content/elementary-math/subject.yaml`: 8 topics per research.md Decision 1, `grade_bands: [1, 2, 3, 4, 5]` (FR-010, a hard requirement -- not a default), each topic complete (FR-002), real Common Core grade-numbered codes (the first subject in this catalog to declare grades below 6). **Every topic's `preferred_question_types` MUST exclude `free_text`/`multi_step`** (spec.md Edge Cases, Assumptions) -- multiple-choice/numeric only, deliberately exercising the zero-free-text Edge Case for real.
- [X] T007 [P] [US3] Author `backend/content/elementary-science/subject.yaml`: 8 topics per research.md Decision 1, `grade_bands: [1, 2, 3, 4, 5]` (FR-010, a hard requirement -- not a default), each topic complete (FR-002), real NGSS elementary codes. **Every topic's `preferred_question_types` MUST exclude `free_text`/`multi_step`** (spec.md Edge Cases, Assumptions) -- multiple-choice/numeric only, same as T006.
- [X] T008 [US3] Run `python scripts/check_no_subject_conditionals.py` from `backend/`; confirm zero violations now that all six new `subject_id` literals exist in `backend/content/` (FR-007). Depends on T002-T007.
- [X] T009 [US3] Run `python scripts/load_content_artifact.py content/<subject>/subject.yaml` for each of the six new subjects against the local dev database from `backend/`; confirm all six exit `0` and `validated_at` is set on all six `Subject` rows (quickstart.md Setup). **Requires a reachable `DATABASE_URL`** -- run as part of live quickstart validation (T017) if unavailable now. Depends on T002-T007.

**Checkpoint**: All six subjects are authored, pass the existing validation gate. User Story 1 can now proceed.

---

## Phase 4: User Story 1 - Learner picks from the complete subject catalog (Priority: P1) 🎯 MVP (with US3)

**Goal**: A learner can select any of the six new subjects at placement/practice start and have the full placement → practice → mastery-update loop behave identically to the four existing subjects, with graceful behavior for a subject that has no history yet -- including, for the first time, Elementary Math/Science's grades 1-5 correctly resolving a real mediation tier.

**Independent Test**: Start placement as the demo learner against each new subject, answer a question, and confirm mastery updates via the same deterministic Sequencing Agent path used for every existing subject.

### Tests for User Story 1

- [X] T010 [P] [US1] Add six new subject fixtures to `backend/tests/conftest.py` (`pre_algebra_subject`, `geometry_subject`, `chemistry_subject`, `earth_science_subject`, `elementary_math_subject`, `elementary_science_subject`), mirroring the existing `algebra_subject`/`biology_subject`/`algebra_2_subject`/`physics_subject` pattern exactly -- new fixtures only, no edit to any existing one.
- [X] T011 [US1] Integration test: placement-start AND practice-start (`next-question`) → answer-a-question → mastery-state-read for each of the six new subjects (FR-005 covers both entry points), asserting response shape and Sequencing Agent BKT-update behavior identical to the existing `algebra-1` flow, using the new fixtures. For `elementary-math` and `elementary-science` specifically, additionally assert `MasteryStateResponse.unlocked_grade` resolves to a value in `1`-`5` and that feeding it into `determine_mediation_tier` yields `CO_PRESENT` or `CHECK_IN` (FR-010, research.md Decision 6) -- in `backend/tests/integration/test_placement_new_subjects_catalog_expansion.py`.
- [X] T012 [P] [US1] Integration test (FR-008, cold-start degradation): answering a question in `chemistry` with zero prior `AssessmentEvent` history produces no misconception classification, without raising an error -- mirroring Milestone 11's existing graceful-degradation test pattern and Milestone 040's own dedicated-new-file precedent (scoped to one representative subject, since `_load_classifier`'s check does not special-case any subject). `elementary-math`/`elementary-science` are excluded here by construction (zero free-text topics, asserted separately in T001) -- in `backend/tests/integration/test_new_subject_cold_start_degradation_catalog_expansion.py`.

### Implementation for User Story 1

No production code changes -- plan.md/research.md Decision 4 confirm placement, practice, and mastery-update already resolve against whatever `Subject` rows exist, with no subject-id allow-list anywhere; Milestone 11's degradation guarantee and Milestone 19's mediation-tier logic are likewise already generic down to grade 1 (research.md Decision 6). T011/T012 passing *is* the implementation proof.

**Checkpoint**: All six new subjects are independently confirmed to run the full learner loop identically to existing subjects, safe with zero history, and (for the two elementary subjects) correctly age-adapted.

---

## Phase 5: User Story 2 - Instructor rosters and assigns across the complete catalog (Priority: P2)

**Goal**: An instructor can assign a quiz against any new subject's topics, and a completed attempt reports per-learner in the instructor dashboard identically to an existing-subject assignment. Separately: Milestone 040's existing roster-grade validation (FR-009, reused unchanged) correctly rejects a roster grade that doesn't overlap a new subject's `grade_bands`, including for the first time at the low end of the grade range (Elementary Math/Science).

**Independent Test**: Create a quiz assignment against a new subject's topics for a roster, complete it as a guardian on a targeted learner's behalf, and confirm the per-learner report renders identically to an existing-subject assignment. Separately: attempt to create a mismatched-grade roster against a new subject and confirm it's rejected; create a matching-grade roster and confirm it succeeds.

### Tests for User Story 2

- [X] T013 [US2] Integration test: quiz-assignment creation against `chemistry` topics → guardian completes the targeted learner's attempt → instructor per-learner report, asserting response shape identical to an existing-subject assignment, using the fixtures from T010, in `backend/tests/integration/test_quiz_assignment_new_subjects_catalog_expansion.py`. Exercises `chemistry` only (spec.md's US2 Acceptance Scenarios name "a new subject" singular) -- deliberate scope choice matching Milestone 040's own precedent, not a gap.
- [X] T014 [P] [US2] Integration test reusing Milestone 040's existing FR-009 mechanism unchanged: `POST /api/rosters` with a grade outside each new subject's declared `grade_bands` is rejected `422` (one case per subject, e.g. `grade: 8` against `geometry`'s `[9,10]`), and a grade within band succeeds, for all six new subjects -- including `grade: 6` against `elementary-math`'s `[1,2,3,4,5]` (rejected) and `grade: 3` (succeeds), the first exercise of FR-009 at the low end of the grade range -- in `backend/tests/integration/test_roster_grade_validation_catalog_expansion.py`. Depends on T002-T007/T010 (each subject's `GradeBand` rows must exist via fixtures).

### Implementation for User Story 2

No production code changes -- FR-009's mechanism (`ClassroomRoster.grade`, `_check_grade_matches_subject`) is Milestone 040's existing, unmodified code. T013/T014 passing *is* the implementation proof.

**Checkpoint**: All three user stories are independently proven. The catalog has grown from 4 to 10 subjects; roster creation is correctly grade-gated across the full grade 1-12 range.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T015 [P] Run the full regression suite (`backend` pytest, `grading-agent` pytest, `tutor-agent` pytest, `frontend` npm test); confirm all pass and zero existing test file was edited beyond the additive `conftest.py` fixtures (T010), only new files added (SC-005).
- [X] T016 Run `quickstart.md`'s scenarios end to end against a real, freshly migrated and loaded dev database (SC-001, SC-002, SC-003, SC-004), including T009's live content load if not already run.
- [X] T017 [P] Update `roadmap.md`'s "Out of current roadmap" section: strike through the "Full K-12 STEM content catalog" bullet for good, noting this feature as the follow-up that closed the remaining six subjects (Pre-Algebra, Geometry, Chemistry, Earth Science, Elementary Math, Elementary Science) named in Milestone 040's own deferral -- matching the strike-through promotion pattern already used for Milestones 14, 16, 17, 20, 21, 22, and Milestone 040 itself. Also add this feature to `CLAUDE.md`'s "Useful context for any session" section, in the same "shipped outside the milestone sequence" bullet style as Standards Alignment/STEM-Career Connections/the Milestone 040 pilot, noting the catalog now totals ten subjects and that it required zero engine changes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: Both skipped -- no blocking prerequisite work exists for this feature as a whole.
- **User Story 3 (Phase 3)**: No dependency on any other story. Must complete before User Story 1 and most of User Story 2 (they need loaded content/fixtures), even though US1/US3 share priority P1.
- **User Story 1 (Phase 4)**: Depends on User Story 3's T002-T007 (content files must exist for the conftest fixtures in T010).
- **User Story 2 (Phase 5)**: T013/T014 both depend on T002-T007/T010 (content files and fixtures must exist).
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Parallel Opportunities

- T002-T007 (all six `subject.yaml` files) are fully independent and can run in parallel.
- T008 (static conditional scan) and T009 (DB load) both depend on T002-T007 but can otherwise proceed as soon as those are done.
- T012 can run in parallel with T011 (different files, both depend only on T010).
- T014 can run in parallel with T013 (different files, both depend only on T002-T007/T010).
- T015 and T017 in Polish are independent and can run in parallel.

---

## Parallel Example: Phase 3 (User Story 3)

```bash
# After T001 is written:
Task: "Author backend/content/pre-algebra/subject.yaml per research.md Decision 1/3"
Task: "Author backend/content/geometry/subject.yaml per research.md Decision 1/3"
Task: "Author backend/content/chemistry/subject.yaml per research.md Decision 1/3"
Task: "Author backend/content/earth-science/subject.yaml per research.md Decision 1/3"
Task: "Author backend/content/elementary-math/subject.yaml per research.md Decision 1/3"
Task: "Author backend/content/elementary-science/subject.yaml per research.md Decision 1/3"
```

## Parallel Example: Phase 5 (User Story 2)

```bash
# Once T002-T007/T010 exist, both run independently:
Task: "Quiz-assignment integration test against chemistry"
Task: "Roster-grade validation integration test against all six new subjects"
```

---

## Implementation Strategy

### MVP First (User Story 3 + User Story 1)

1. Complete Phase 3 (User Story 3): author and validate all six new subjects.
2. Complete Phase 4 (User Story 1): confirm the full learner loop works identically for all six, including cold-start safety and elementary-grade mediation tiers.
3. **STOP and VALIDATE**: this alone proves the catalog-expansion claim for a solo learner -- a demoable increment even before instructor-assignment support is checked.

### Incremental Delivery

1. User Story 3 → all six subjects exist, validated.
2. User Story 1 → learner flow proven identical to existing subjects, safe with zero history, elementary grades correctly age-adapted (MVP complete).
3. User Story 2 → instructor flow proven identical to existing subjects; FR-009's existing roster-grade validation correctly gates mismatched combinations across the full grade 1-12 range.
4. Polish → full regression, live quickstart validation (including the actual DB content load), roadmap/CLAUDE.md status update closing the backlog item.

### Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Commit after each task or logical group, per this repo's `commit-smart-message` convention.
- Unlike Milestone 040, this feature found no engine gap during planning -- FR-009's mechanism, the `grade BETWEEN 1 AND 12` constraint, and Milestone 19's mediation tiers were all confirmed sufficient by reading the actual code (research.md Decisions 4 and 6) before any task was written, not discovered mid-implementation.

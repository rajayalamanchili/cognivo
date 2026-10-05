---

description: "Task list for Full K-12 Content Catalog (Algebra II/Physics pilot)"
---

# Tasks: Full K-12 Content Catalog

**Input**: Design documents from `/specs/040-k12-content-catalog/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (all present). `contracts/README.md` documents the one real wire-format change (FR-009's `POST /api/rosters` `grade` field, found during implement).

**Tests**: Included, matching this project's established convention (every Success Criteria in this repo's specs ships with an automated check, not verified by inspection alone -- see CLAUDE.md and every prior milestone's Definition of Done in `roadmap.md`).

**Organization**: Tasks are grouped by user story (spec.md priorities). **Note on ordering**: spec.md lists User Story 1 (P1) before User Story 3 (P1), but US1's own Independent Test literally requires "a newly authored and loaded subject content artifact" to exist first -- i.e. US3's output. Phases below run US3 before US1 despite spec.md's listed order, the same honesty-over-listed-order precedent this project applied in Milestone 23 (quiz/placement corrections) and Milestone 11 (reordering train/eval). Both remain P1; this is a dependency ordering, not a priority demotion.

**Note on FR-004**: FR-004 (new subject content is authored as an LLM-assisted draft with mandatory human review before load) has no dedicated task below. It is satisfied structurally by this feature's own pull request going through this repository's existing review gate (Constitution Principle X) -- the same way the Setup phase is skipped rather than padded with inapplicable work. No new review-queue UI or workflow state exists to task against.

**Note on FR-009 (found during `/speckit-implement`)**: the original task list (post-`/speckit-analyze`) had a T008 here testing a learner/roster grade-filtered "subject-selection surface" modeled on Milestone 17. Reading the actual code found no such mechanism exists -- Milestone 17's grade-banding only gates topics *within* an already-chosen subject, `ClassroomRoster`/`LearnerProfile` had no grade field at all, and placement is hardcoded to the single shared demo learner (which must stay unrestricted). Confirmed with the user before building anything (Clarifications, research.md Decision 6): FR-009 is now real, narrowly-scoped new engine work on **roster creation only** -- tasks T009-T012 below replace the old T008 entirely, moved from US1 into US2 (instructor-facing) since that's the only surface it actually touches.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)

## Path Conventions

Web app split per plan.md: `backend/content/`, `backend/src/`, `backend/tests/`, `backend/scripts/`, `backend/alembic/versions/`. No frontend path appears below -- plan.md/research.md Decision 4 confirm zero frontend changes (the subject picker and every flow it feeds already render generically off whatever `Subject` rows exist); FR-009's one new `grade` field is consumed via the existing roster-creation form with no new frontend component.

---

## Phase 1: Setup

**Skipped.** No project initialization applies: zero new dependency or framework.

## Phase 2: Foundational (Blocking Prerequisites)

**Skipped.** Nothing blocks User Story 3 from starting immediately. (FR-009's schema/service work is scoped entirely to User Story 2 below, not a cross-story blocker.)

---

## Phase 3: User Story 3 - Content author adds a new subject that passes existing validation (Priority: P1)

**Goal**: Algebra II and Physics each get a complete content artifact (topic graph, skill definitions, difficulty calibration, real standards tags, career connections) that loads and validates through the exact same gate Algebra I and Biology already pass, with zero validator code changed.

**Independent Test**: Run `scripts/load_content_artifact.py` against each new `subject.yaml` with zero changes to validator code; confirm both are accepted, and confirm a deliberately broken scratch copy is rejected with an existing error class.

### Tests for User Story 3

- [X] T001 [P] [US3] Integration test covering: (a) `content/algebra-2/subject.yaml` and `content/physics/subject.yaml` each load successfully with 8 topics, every topic carrying a complete `skill_definition`/`difficulty_calibration`/`standards`/`career_connection`, `grade` values matching their subject's declared `grade_bands` (9-10 for algebra-2, 9-11 for physics), and at least one topic per subject declaring `free_text` or `multi_step` in `preferred_question_types`; (b) a scratch copy missing a required field on one topic is rejected with `ContentArtifactValidationError`, the same class an incomplete Algebra I/Biology artifact would raise; (c) a scratch copy where a topic's `prerequisites` names a topic from the *other* new subject is rejected as an unknown prerequisite (research.md Decision 2) -- in `backend/tests/integration/test_content_artifact_load_k12_pilot.py`.

### Implementation for User Story 3

- [X] T002 [P] [US3] Author `backend/content/algebra-2/subject.yaml`: 8 topics per research.md Decision 1, `grade_bands: [9, 10]`, each topic complete, at least one `free_text` and one `multi_step` topic (FR-007 exercise requirement).
- [X] T003 [P] [US3] Author `backend/content/physics/subject.yaml`: 8 topics per research.md Decision 1, `grade_bands: [9, 10, 11]`, same completeness/free_text/multi_step requirement.
- [X] T004 [P] [US3] Run `python scripts/check_no_subject_conditionals.py` from `backend/`; confirm zero violations now that `algebra-2`/`physics` literals exist in `backend/content/` (FR-007).
- [X] T005 [US3] Run `python scripts/load_content_artifact.py content/algebra-2/subject.yaml` and `python scripts/load_content_artifact.py content/physics/subject.yaml` against the local dev database from `backend/`; confirm both exit `0` and `validated_at` is set on both `Subject` rows (quickstart.md Setup). **Requires a reachable `DATABASE_URL`** -- run as part of live quickstart validation (T015) if unavailable now.

**Checkpoint**: Both subjects are authored, pass the existing validation gate. User Story 1 can now proceed.

---

## Phase 4: User Story 1 - Learner picks from the full subject catalog (Priority: P1) 🎯 MVP (with US3)

**Goal**: A learner can select Algebra II or Physics at placement/practice start and have the full placement → practice → mastery-update loop behave identically to Algebra I/Biology, with graceful behavior for a subject that has no history yet.

**Independent Test**: Start placement as the demo learner against `algebra-2` (and `physics`), answer a question, and confirm mastery updates via the same deterministic Sequencing Agent path used for every existing subject.

### Tests for User Story 1

- [X] T006 [P] [US1] Add `algebra_2_subject`/`physics_subject` fixtures to `backend/tests/conftest.py`, mirroring `algebra_subject`/`biology_subject` exactly -- new fixtures only, no edit to the two existing ones.
- [X] T007 [US1] Integration test: placement-start AND practice-start (`next-question`) → answer-a-question → mastery-state-read for both `algebra-2` and `physics` (FR-005 covers both entry points), asserting response shape and Sequencing Agent BKT-update behavior identical to the existing `algebra-1` flow, using the new fixtures, in `backend/tests/integration/test_placement_new_subjects.py`.
- [X] T008 [P] [US1] Integration test (FR-008, cold-start degradation): answering a question in `algebra-2` or `physics` with zero prior `AssessmentEvent` history produces no misconception classification and a guaranteed cache miss on first call, without raising an error -- mirroring Milestone 11's existing graceful-degradation test pattern -- in `backend/tests/integration/test_new_subject_cold_start_degradation.py`.

### Implementation for User Story 1

No production code changes -- plan.md/research.md Decision 4 confirm placement, practice, and mastery-update already resolve against whatever `Subject` rows exist, with no subject-id allow-list anywhere; Milestone 11's degradation guarantee is likewise already generic. T007/T008 passing *is* the implementation proof.

**Checkpoint**: Both new subjects are independently confirmed to run the full learner loop identically to Algebra I/Biology, and safe with zero history.

---

## Phase 5: User Story 2 - Instructor rosters and assigns across the full catalog (Priority: P2)

**Goal**: An instructor can assign a quiz against Algebra II or Physics topics, and a completed attempt reports per-learner in the instructor dashboard identically to an existing-subject assignment. Separately (FR-009, found during implement): an instructor can optionally declare a roster's grade at creation time, and creation is rejected if that grade doesn't overlap the chosen subject's own `grade_bands`.

**Independent Test**: Create a quiz assignment against `physics` topics for a roster, complete it as a guardian on a targeted learner's behalf, and confirm the per-learner report renders identically to an Algebra I/Biology assignment. Separately: attempt to create a grade-8 roster against `physics` and confirm it's rejected; create a grade-9 roster against `physics` and confirm it succeeds.

### FR-009: Roster-grade validation (new engine work, found during implement)

- [X] T009 [US2] Add nullable `grade: int | None` column (with a `CheckConstraint` guarding 1-12) to `ClassroomRoster` in `backend/src/models/classroom_roster.py` (data-model.md).
- [X] T010 [US2] Alembic migration adding `classroom_rosters.grade` + its check constraint, mirroring `824e2c5a0678`'s add-column shape, in `backend/alembic/versions/` (depends on T009).
- [X] T011 [P] [US2] Integration test: `POST /api/rosters` with `grade: 8` against `physics` (grade_bands `[9,10,11]`) is rejected `422`; `grade: 9` against `physics` succeeds; `grade: 10` against `algebra-2` (grade_bands `[9,10]`) also succeeds independently at the same grade (the overlap edge case); `grade: 3` against `biology` (no `grade_bands`) always succeeds (opt-in-per-subject precedent) -- in `backend/tests/integration/test_roster_grade_validation.py`. Write first; fails until T012. Depends on T002/T003/T006 (algebra-2/physics `GradeBand` rows must exist).
- [X] T012 [US2] Add `_check_grade_matches_subject` and a `grade: int | None = None` parameter to `create_roster()` in `backend/src/services/roster/enrollment.py`; thread `grade` through `CreateRosterIn`/`RosterOut`/`RosterSummaryOut`/`create_roster_route`/`list_rosters_route` in `backend/src/api/routes/rosters.py` (contracts/README.md) (depends on T009, T010, T011).

### Tests for User Story 2 (quiz-assignment flow)

- [X] T013 [US2] Integration test: quiz-assignment creation against `physics` topics → guardian completes the targeted learner's attempt → instructor per-learner report, asserting response shape identical to an existing-subject assignment, using the fixtures from T006, in `backend/tests/integration/test_quiz_assignment_new_subjects.py`. Exercises `physics` only (spec.md's US2 Acceptance Scenarios name "a new subject" singular, not both) -- deliberate scope choice, not a gap.

**Checkpoint**: All three user stories are independently proven. The catalog has grown from 2 to 4 subjects; roster creation is correctly grade-gated where declared.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T014 [P] Run the full regression suite (`backend` pytest, `grading-agent` pytest, `tutor-agent` pytest, `frontend` npm test); confirm all pass and zero existing test file was edited beyond the additive `conftest.py` fixtures (T006), only new files/columns added (SC-005).
- [X] T015 Run `quickstart.md`'s scenarios end to end against a real, freshly migrated and loaded dev database (SC-001, SC-002, SC-003, SC-004), including T005's live content load if not already run.
- [X] T016 [P] Update `roadmap.md`'s "Out of current roadmap" section: strike through the "Full K-12 STEM content catalog" bullet, noting this feature as a deliberate two-subject pilot (Algebra II, Physics) plus the real FR-009 roster-grade correction found during implementation, with the remaining six subjects still explicitly deferred to a follow-up feature -- matching the strike-through promotion pattern already used for Milestones 14, 16, 17, 20, 21, 22; also note this feature in `CLAUDE.md`'s "Useful context for any session" section alongside the Standards Alignment/STEM-Career Connections entries.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: Both skipped -- no blocking prerequisite work exists for this feature as a whole (FR-009's new work is scoped to US2 alone).
- **User Story 3 (Phase 3)**: No dependency on any other story. Must complete before User Story 1 and most of User Story 2 (they need loaded content/fixtures), even though US1/US3 share priority P1.
- **User Story 1 (Phase 4)**: Depends on User Story 3's T002/T003 (content files must exist for the conftest fixtures in T006).
- **User Story 2 (Phase 5)**: T009/T010 (schema) have no dependency and could run before US3; T011 depends on T002/T003/T006 (GradeBand rows); T013 depends on T006 only.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Parallel Opportunities

- T002 and T003 (the two subject.yaml files) are fully independent and can run in parallel.
- T004 (static conditional scan) can run in parallel with T005 (DB load) once T002/T003 exist.
- T008 can run in parallel with T007 (different files, both depend only on T006).
- T009/T010 (roster schema) can run any time, independent of the US3/US1 phases entirely.
- T014 and T016 in Polish are independent and can run in parallel.

---

## Parallel Example: Phase 3 (User Story 3)

```bash
# After T001 is written:
Task: "Author backend/content/algebra-2/subject.yaml per research.md Decision 1/3"
Task: "Author backend/content/physics/subject.yaml per research.md Decision 1/3"
```

## Parallel Example: Phase 5 (User Story 2)

```bash
# T009/T010 (schema) can start immediately, independent of US3:
Task: "Add grade column to ClassroomRoster + migration"

# Once T002/T003/T006 and T009/T010 both exist:
Task: "Roster-grade validation integration test"
```

---

## Implementation Strategy

### MVP First (User Story 3 + User Story 1)

1. Complete Phase 3 (User Story 3): author and validate both new subjects.
2. Complete Phase 4 (User Story 1): confirm the full learner loop works identically for both, including cold-start safety.
3. **STOP and VALIDATE**: this alone proves the catalog-expansion claim for a solo learner -- a demoable increment even before instructor-assignment support is checked.

### Incremental Delivery

1. User Story 3 → both subjects exist, validated.
2. User Story 1 → learner flow proven identical to existing subjects, safe with zero history (MVP complete).
3. User Story 2 → instructor flow proven identical to existing subjects; roster-grade validation (FR-009) correctly gates mismatched combinations.
4. Polish → full regression, live quickstart validation (including the actual DB content load), roadmap/CLAUDE.md status update.

### Notes

- [P] tasks = different files, no dependency on an incomplete task.
- Commit after each task or logical group, per this repo's `commit-smart-message` convention.
- FR-009's roster-grade mechanism (T009-T012) was a real correction found only once the actual code was read during implementation -- confirmed with the user before building anything, the same "confirm before building" precedent Milestone 23 set.

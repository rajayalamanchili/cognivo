---

description: "Task list for Standards Alignment"
---

# Tasks: Standards Alignment

**Input**: Design documents from `/specs/038-standards-alignment/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md (all present)

**Tests**: Included, matching this project's established convention (every Success Criteria in this repo's specs ships with an automated check, not verified by inspection alone -- see CLAUDE.md and every prior milestone's Definition of Done in `roadmap.md`).

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) to enable independent implementation and testing of each story. One new table, one new migration -- see plan.md's Technical Context.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)

## Path Conventions

Web app split per plan.md: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: The schema, validation, and shared coverage-computation primitive every user story depends on. No user story's implementation tasks can begin until this phase is complete.

**⚠️ CRITICAL**: T001-T005 block all three user stories; T006-T007 (the shared `coverage.py` function) block US1 and US2 specifically.

- [ ] T001 [P] Unit test for `StandardsTag` content-artifact validation: rejects a `standards` entry on an ungraded topic (FR-003), rejects a missing `framework`/`code` (US3 Acceptance Scenario 3), accepts a valid entry on a graded topic, accepts the same `(framework, code)` pair repeated across two different topics when their `title` matches exactly (research.md Decision 2), and rejects it when their `title` text differs (data-model.md's title-consistency rule) in `backend/tests/unit/test_content_artifact_standards_validation.py`
- [ ] T002 Add `_validate_standards(subject_id, topic_id, standards, grade, seen_titles_by_code)` to `backend/src/services/content_artifact/validator.py`, following `_validate_misconceptions`'s shape exactly (including the cross-topic `seen_titles_by_code` dict threaded through the caller's loop, mirroring `seen_misconception_ids`); add `standards: tuple[dict, ...]` to `ValidatedTopic` (depends on T001)
- [ ] T003 [P] Create `StandardsTag` model in `backend/src/models/standards_tag.py`, mirroring `grade_band.py`'s minimal-table shape: composite PK `(subject_id, topic_id, framework, code)`, FK to `topics`, plus a non-key `title` column (data-model.md)
- [ ] T004 Generate the Alembic migration for the new `standards_tags` table in `backend/alembic/versions/` (depends on T003)
- [ ] T005 Extend `persist_content_artifact` in `backend/src/services/content_artifact/loader.py` to delete-and-recreate a subject's `StandardsTag` rows on every reload, matching `PrerequisiteEdge`'s existing pattern (data-model.md) (depends on T002, T003, T004) -- extends T001's test file with a round-trip assertion (load an artifact with a `standards` entry, query `standards_tags`, confirm it matches)
- [ ] T006 [P] Unit test for `compute_standards_coverage`: `met` only when every tagged topic is `mastered` (Clarifications), `not_yet_reached` when no tagged topic has any `MasteryState` row, `in_progress` otherwise, and an empty result for a subject with zero `StandardsTag` rows (FR-006) in `backend/tests/unit/test_standards_coverage.py`
- [ ] T007 Create `compute_standards_coverage(db, *, learner_id, subject_id) -> list[StandardCoverageEntry]` in `backend/src/services/standards/coverage.py` (data-model.md) (depends on T006, T003)

**Checkpoint**: Schema, validation, and the shared coverage primitive are ready. US1 and US2 can now be implemented; US3's content-population work can proceed in parallel (it only depends on T002).

---

## Phase 2: User Story 1 - Instructor or guardian sees a learner's standards coverage (Priority: P1) 🎯 MVP

**Goal**: Both the instructor's per-learner dashboard view and the owning guardian's own view of their real learner show, per standards-tagged topic, whether that standard is met / in progress / not yet reached -- identical in shape and derivation across both surfaces (FR-004).

**Independent Test**: Tag a graded topic with a standards code, have a learner cross that topic into `mastered`, then confirm both the instructor's roster-dashboard entry for that learner and the owning guardian's own view show the standard as met, naming its real code -- independent of the roster-aggregate view (US2).

### Tests for User Story 1

- [ ] T008 [P] [US1] Contract test: `GET /api/learners/{learner_id}/mastery-state` response includes a `standards` field with correct met/in-progress/not-yet-reached status for the owning guardian, and still `403`s for a non-owning guardian (`require_learner_ownership_if_real()` unchanged) in `backend/tests/contract/test_mastery_state_standards.py`
- [ ] T009 [P] [US1] Integration test: `GET /api/rosters/{roster_id}/dashboard` response's `DashboardLearnerOut.standards` matches `compute_standards_coverage`'s output exactly for each enrolled learner, scoped by the existing roster-ownership check, in `backend/tests/integration/test_dashboard_standards_coverage.py`
- [ ] T010 [P] [US1] Component test: `StandardsCoverage` renders met/in-progress/not-yet-reached with a visible text label always paired with color (never color alone, FR-011), and omits a topic with zero tags entirely (FR-006) in `frontend/tests/unit/standards-coverage.test.tsx`

### Implementation for User Story 1

- [ ] T011 [US1] Add `standards: list[StandardCoverageOut]` to `MasteryStateResponse`, computed via `compute_standards_coverage`, in `backend/src/api/routes/mastery.py` (depends on T007, T008)
- [ ] T012 [US1] Add `standards: tuple[StandardCoverageEntry, ...]` to `LearnerDashboardEntry` in `backend/src/services/dashboard/aggregation.py`, computed via `compute_standards_coverage` per enrolled learner, and expose it as `DashboardLearnerOut.standards` in `backend/src/api/routes/instructor_dashboard.py` (depends on T007, T009)
- [ ] T013 [P] [US1] Create `StandardsCoverage` component (framework/code/title/status, color+text label per FR-011) in `frontend/src/components/StandardsCoverage.tsx` (depends on T010)
- [ ] T014 [US1] Add a standards-coverage section to the guardian's own learner view in `frontend/src/app/(auth)/guardian/learners/page.tsx` -- this page currently renders only `JoinRosterForm`/`LearnerAssignments` (research.md Decision 4); fetch `mastery-state` for the added learner and render `StandardsCoverage` (depends on T011, T013)
- [ ] T015 [US1] Wire `StandardsCoverage` into each learner's row in `frontend/src/app/instructor/dashboard/instructor-dashboard-flow.tsx` (depends on T012, T013)

**Checkpoint**: User Story 1 is fully functional and independently testable/demoable, across both the instructor and guardian surfaces.

---

## Phase 3: User Story 2 - Instructor sees class-wide standards coverage (Priority: P2)

**Goal**: The roster dashboard shows, per standard, how many enrolled learners have met it out of the roster's total.

**Independent Test**: With User Story 1's per-learner coverage already working for multiple enrolled learners, confirm the roster view's per-standard count matches a manual tally across those learners' individual views.

### Tests for User Story 2

- [ ] T016 [P] [US2] Integration test: `DashboardOut.standards_summary` reports correct `met_count`/`total_count` per `(framework, code)` across a roster's enrolled learners, and is an empty list for a subject with zero `StandardsTag` rows (US2 Acceptance Scenario 2) in `backend/tests/integration/test_dashboard_standards_summary.py`

### Implementation for User Story 2

- [ ] T017 [US2] Compute `standards_summary` (one entry per distinct `(framework, code)`, `met_count`/`total_count`) from the roster's already-computed per-learner `standards` results in `backend/src/services/dashboard/aggregation.py`, exposed as `DashboardOut.standards_summary` in `backend/src/api/routes/instructor_dashboard.py` (depends on T012, T016)
- [ ] T018 [US2] Render the roster-wide standards summary (absent entirely when empty, not an empty table) in `frontend/src/app/instructor/dashboard/instructor-dashboard-flow.tsx` (depends on T017)

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 4: User Story 3 - Content author tags a topic with real standards codes (Priority: P3)

**Goal**: This project's existing graded topics (`algebra-1`'s 8 topics -- `biology` has no `grade_bands` at all and cannot be tagged, research.md Decision 1) carry real, verified Common Core Math codes, not placeholders.

**Independent Test**: Add a standards tag to a topic in a graded subject's content artifact and confirm it validates, loads, and is queryable afterward -- independent of any dashboard view (US1/US2).

**Note**: This phase's schema/validation work already landed in Foundational (T001/T002), since US1 and US2 need it to exist before their own tests are meaningful. This phase is the actual content-authoring deliverable (FR-010) plus its own verification.

- [ ] T019 [US3] Research and add a real, verified Common Core Math `standards:` entry (framework, code, title) to each of `backend/content/algebra-1/subject.yaml`'s 8 topics that has a genuinely corresponding published standard; leave any topic without a genuine match untagged rather than assign an inaccurate code (FR-010) (depends on T002)
- [ ] T020 [US3] Reload the content artifact (`python backend/scripts/load_content_artifact.py content/algebra-1/subject.yaml`) and verify via `SELECT * FROM standards_tags WHERE subject_id = 'algebra-1'` that the persisted rows match the file exactly (depends on T019, T005)

**Checkpoint**: All three user stories are independently functional, and real data exists for US1/US2's demos.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Confirm zero regression and zero constitutional drift across the whole feature.

- [ ] T021 [P] Run `backend/scripts/check_no_subject_conditionals.py`, confirm clean (Constitution Principle III)
- [ ] T022 [P] Create `backend/scripts/check_no_standards_literals.py` (mirrors `check_no_subject_conditionals.py` exactly, scoped to `standards:` framework/code literals from `backend/content/*/subject.yaml`) and run it, confirm clean -- this is SC-002/FR-002's actual verification (`check_no_subject_conditionals.py` alone only covers subject-id literals, not framework/code) (depends on T020)
- [ ] T023 [P] Run `backend/scripts/check_deletion_cascade_coverage.py`, confirm it passes with no new allowlist entry needed -- `StandardsTag` has no FK to `learner_profiles`/`real_guardian_accounts`/`real_instructor_accounts` (Constitution Principle VIII)
- [ ] T024 Run the full backend regression suite (`pytest`), confirm no regressions against Milestones 1-24 and the Learner UI Redesign
- [ ] T025 Run the full frontend regression suite (`npx vitest run`), confirm no regressions
- [ ] T026 Execute `quickstart.md`'s 3 scenarios plus its accessibility check against a real dev database and record the results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies -- start immediately. T001-T005 (schema/validation) block every user story's data from existing at all. T006-T007 (`coverage.py`) specifically block US1 (T011/T012) and US2 (T017).
- **User Stories (Phase 2-4)**: US1 and US2 depend on Foundational's T007. US2 additionally depends on US1's T012 (it reuses the per-learner `standards` results already computed there, rather than re-querying). US3 depends only on Foundational's T002 -- it has no dependency on US1 or US2's code, and may run in parallel with either (spec.md's own framing: US3 "enables" US1/US2 but is not itself instructor- or learner-visible).
- **Polish (Phase 5)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests are written first and MUST fail before the corresponding implementation task.
- Backend response-model/route changes before the frontend components that consume them.
- Story complete and checkpointed before moving to the next priority.

### Parallel Opportunities

- T001 and T003 (Foundational, different files) can run in parallel; T006 can run in parallel with T001-T005 (different files, no shared dependency until T007).
- Within US1: T008, T009, T010 in parallel; T013 in parallel with T011/T012.
- Within US2: T016 has no parallel sibling in this story.
- US3 (T019-T020) can run in parallel with all of US1/US2 once T002 lands.
- Within Polish: T021, T022, T023 in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all three tests for User Story 1 together:
Task: "Contract test for MasteryStateResponse.standards in backend/tests/contract/test_mastery_state_standards.py"
Task: "Integration test for DashboardLearnerOut.standards in backend/tests/integration/test_dashboard_standards_coverage.py"
Task: "Component test for StandardsCoverage in frontend/tests/unit/standards-coverage.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Foundational (schema, validation, `coverage.py`).
2. Complete Phase 4's T019-T020 alongside Foundational (real content data; no code dependency on US1/US2) so US1 has something real to demo.
3. Complete Phase 2: User Story 1.
4. **STOP and VALIDATE**: run `quickstart.md`'s Scenario 1 independently.
5. This alone is a demoable increment: both instructor and guardian can see one learner's real standards coverage.

### Incremental Delivery

1. Foundational + US3's content population → real tagged data ready.
2. User Story 1 → validate → demo (MVP).
3. User Story 2 → validate → demo.
4. Polish → full regression + `quickstart.md`.

## Notes

- No contract-test directory changes beyond the one new file listed above; `contracts/api-changes.md` documents the exact shapes.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

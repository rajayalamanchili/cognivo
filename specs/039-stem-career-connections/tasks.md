---

description: "Task list for STEM-Career Connections"
---

# Tasks: STEM-Career Connections

**Input**: Design documents from `/specs/039-stem-career-connections/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md (all present)

**Tests**: Included, matching this project's established convention (every Success Criteria in this repo's specs ships with an automated check, not verified by inspection alone -- see CLAUDE.md and every prior milestone's Definition of Done in `roadmap.md`).

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) to enable independent implementation and testing of each story. No new tables, two new columns on existing tables -- see plan.md's Technical Context.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)

## Path Conventions

Web app split per plan.md: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: The schema, validation, and loader support every user story depends on. No user story's implementation tasks can begin until this phase is complete.

**⚠️ CRITICAL**: T001-T006 block all three user stories.

- [ ] T001 [P] Unit test for `Topic` content-artifact validation of `career_connection`: rejects a mapping missing `career` or `description`, accepts a valid mapping on a topic regardless of `grade` (including an ungraded, `biology`-shaped topic -- research.md Decision 2), accepts `None`/absent, in `backend/tests/unit/test_content_artifact_career_connection_validation.py`
- [ ] T002 Add `_validate_career_connection(subject_id, topic_id, career_connection)` to `backend/src/services/content_artifact/validator.py`, following `_validate_image_asset`'s shape exactly -- no grade-gate, unlike `_validate_standards`; add `career_connection: dict | None` to `ValidatedTopic` (depends on T001)
- [ ] T003 [P] Add `career_connection: Mapped[dict | None]` JSON column to `Topic` in `backend/src/models/topic.py`, mirroring the existing `image_asset` column exactly (data-model.md)
- [ ] T004 [P] Add `career_connections_enabled: Mapped[bool]` column (`server_default=sa.true()`, not null) to `LearnerProfile` in `backend/src/models/learner_profile.py` (data-model.md)
- [ ] T005 Generate the Alembic migration adding both columns (`topics.career_connection` JSON nullable; `learner_profiles.career_connections_enabled` boolean, `server_default=sa.true()`, not null) in `backend/alembic/versions/`, mirroring `824e2c5a0678_mastery_state_has_been_mastered_column.py`'s add-column shape (depends on T003, T004)
- [ ] T006 Extend `persist_content_artifact` in `backend/src/services/content_artifact/loader.py` to upsert `Topic.career_connection` in place, the same way it already sets `image_asset` (depends on T002, T003, T005) -- extends T001's test file with a round-trip assertion (load an artifact with a `career_connection` entry, query `topics`, confirm it matches)

**Checkpoint**: Schema, validation, and the loader are ready. US1 can now be implemented; US3's content-population work can proceed in parallel (it only depends on T002/T006).

---

## Phase 2: User Story 1 - See a real-world career tied to a topic (Priority: P1) 🎯 MVP

**Goal**: Wherever a topic's progress is currently shown -- the demo learner's own dashboard, or a guardian's view of a real learner they manage -- a topic's authored career connection displays alongside it, for any learner whose preference is enabled (default on).

**Independent Test**: Author a career connection on a topic, confirm it displays on both the demo learner's dashboard and a guardian's view of a real learner (both default to the preference being on); confirm a topic with no authored connection shows nothing, not an error.

### Tests for User Story 1

- [ ] T007 [P] [US1] Contract test: `GET /api/learners/{learner_id}/mastery-state` response's `career_connections` field is populated correctly from `Topic.career_connection` rows for the requested subject, is an empty list when the learner's `career_connections_enabled` is `false`, and still `403`s for a non-owning guardian (`require_learner_ownership_if_real()` unchanged) in `backend/tests/contract/test_mastery_state_career_connections.py`
- [ ] T008 [P] [US1] Component test: `CareerConnectionsList` renders each matched `(topic_id, career, description)` entry, and omits a topic with no matching entry entirely -- never an error, empty box, or placeholder text (FR-007) -- in `frontend/tests/unit/career-connections-list.test.tsx`

### Implementation for User Story 1

- [ ] T009 [US1] Add `CareerConnectionOut` and `career_connections: list[CareerConnectionOut] = []` to `MasteryStateResponse` in `backend/src/api/routes/mastery.py`, computed inline from the already-loaded `Topic` rows for the subject plus the learner's `career_connections_enabled` flag (empty list when `false`) (depends on T006, T007)
- [ ] T010 [P] [US1] Create `CareerConnectionsList` (presentational, takes matched `career_connections` entries plus the topic list) in `frontend/src/components/CareerConnectionsList.tsx` (depends on T008)
- [ ] T011 [US1] Wire `CareerConnectionsList` into `frontend/src/components/DashboardSubjectSection.tsx`, using the `career_connections` field off its already-fetched `getMasteryState` call -- no new fetch (depends on T009, T010)
- [ ] T012 [US1] Create `GuardianLearnerCareerConnections.tsx` (sibling to `GuardianLearnerStandards.tsx`: same `listLearnerEnrollments` + per-subject `getMasteryState` fetch shape, extracting `.career_connections` instead of `.standards`) in `frontend/src/components/GuardianLearnerCareerConnections.tsx`, and render it inside the existing per-added-learner `<li>` block in `frontend/src/app/(auth)/guardian/learners/page.tsx` (depends on T009, T010)

**Checkpoint**: User Story 1 is fully functional and independently testable/demoable on both surfaces, using the default-on preference (the write path for turning it off is US2).

---

## Phase 3: User Story 2 - Turn the feature on or off (Priority: P2)

**Goal**: The demo learner can turn the feature on/off for itself via a new settings page off its existing avatar menu; a real learner's owning guardian can turn it on/off on that learner's behalf from "My Learners." Both are enforced server-side (FR-006).

**Independent Test**: Turn the preference off for the demo learner via `/settings` and confirm `career_connections` is empty on the next dashboard load; turn it off for a real learner via the guardian's "My Learners" page and confirm the same in the guardian's own view; confirm a non-owning guardian cannot read or change a real learner's preference.

### Tests for User Story 2

- [ ] T013 [P] [US2] Contract test: `GET`/`PATCH /api/learners/{learner_id}/career-connections-preference` -- a demo (or nonexistent) `learner_id` round-trips with no session required; a real learner's preference requires the owning guardian's session (`401` with no session, `403` for a non-owning guardian); an unset real learner's `GET` returns `{"enabled": true}` (the column default); two distinct real learners owned by the same guardian have independent preference values (toggling one does not affect the other, Edge Cases) in `backend/tests/contract/test_career_connections_preference.py`
- [ ] T014 [P] [US2] Component test: `CareerConnectionsToggle` renders the fetched state, calls `PATCH` with the new value on change, and reflects the server's response (not an optimistic local flip that could drift from what was actually saved) in `frontend/tests/unit/career-connections-toggle.test.tsx`

### Implementation for User Story 2

- [ ] T015 [US2] Add `GET`/`PATCH /api/learners/{learner_id}/career-connections-preference` to `backend/src/api/routes/mastery.py`, reusing `require_learner_ownership_if_real()` verbatim for both (depends on T004, T005, T013)
- [ ] T016 [P] [US2] Create `CareerConnectionsToggle` (takes a `learnerId`, `GET`s on mount, `PATCH`es on change) in `frontend/src/components/CareerConnectionsToggle.tsx` (depends on T014)
- [ ] T017 [US2] Add a new demo-learner settings page (resolves the demo learner's id via the existing `getDemoLearner()` call, renders `CareerConnectionsToggle`) at `frontend/src/app/settings/page.tsx` (depends on T016)
- [ ] T018 [US2] Add a "Settings" link to the demo-learner avatar-menu dropdown, pointing to `/settings`, alongside the existing "Exit Demo"/"Sign In" items in `frontend/src/components/Nav.tsx` (depends on T017)
- [ ] T019 [US2] Render `CareerConnectionsToggle` inside the existing per-added-learner `<li>` block, alongside `JoinRosterForm`/`GuardianLearnerStandards`/`LearnerAssignments`, in `frontend/src/app/(auth)/guardian/learners/page.tsx` (depends on T016)

**Checkpoint**: User Stories 1 and 2 both work independently, for both actors.

---

## Phase 4: User Story 3 - Real coverage across existing content (Priority: P3)

**Goal**: Every one of the 16 topics across both existing content artifacts (`algebra-1`, `biology`) carries a real, accurate authored career connection -- not placeholder text.

**Independent Test**: Enumerate every topic across both subjects and confirm each has a real, non-fabricated career connection; validate and reload both artifacts successfully.

**Note**: Schema/validation/loader support already landed in Foundational (T002/T006), since US1 needs it to exist before its own tests are meaningful. This phase is the actual content-authoring deliverable (FR-010) plus its own verification.

- [ ] T020 [US3] Research and add a real, accurate `career_connection: {career, description}` mapping to each of `backend/content/algebra-1/subject.yaml`'s 8 topics (depends on T002)
- [ ] T021 [US3] Research and add a real, accurate `career_connection` mapping to each of `backend/content/biology/subject.yaml`'s 8 topics -- not grade-gated, unlike Standards Alignment's equivalent (research.md Decision 2), since `biology` has no `grade_bands` at all (depends on T002)
- [ ] T022 [US3] Reload both content artifacts and verify via `SELECT subject_id, topic_id, career_connection FROM topics WHERE career_connection IS NOT NULL` that all 16 rows persisted and match the files exactly (depends on T020, T021, T006)

**Checkpoint**: All three user stories are independently functional, and real data exists for US1/US2's demos.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Confirm zero regression and zero constitutional drift across the whole feature.

- [ ] T023 [P] Run `backend/scripts/check_no_subject_conditionals.py`, confirm clean (Constitution Principle III -- `career`/`description` stay opaque authored strings)
- [ ] T024 [P] Run `backend/scripts/check_deletion_cascade_coverage.py`, confirm it passes with no new allowlist entry needed -- `career_connections_enabled` is a column on the already-covered `learner_profiles` table, not a new FK target (Constitution Principle VIII)
- [ ] T025 Run the full backend regression suite (`pytest`), confirm no regressions against Milestones 1-24, the Learner UI Redesign, and Standards Alignment
- [ ] T026 Run the full frontend regression suite (`npx vitest run`), confirm no regressions
- [ ] T027 Execute `quickstart.md`'s 3 scenarios against a real dev database and record the results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies -- start immediately. T001-T006 block every user story's data from existing at all.
- **User Stories (Phase 2-4)**: US1 depends on Foundational's T006. US2 depends on Foundational's T004/T005 (the preference column) -- it does not depend on US1's code, since the toggle's `GET`/`PATCH` pair is independent of how `career_connections` is rendered. US3 depends only on Foundational's T002 -- it has no dependency on US1 or US2's code, and may run in parallel with either, matching spec.md's own framing that US3 "enables" US1/US2's demo value but is not itself a display or control mechanism.
- **Polish (Phase 5)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests are written first and MUST fail before the corresponding implementation task.
- Backend response-model/route changes before the frontend components that consume them.
- Story complete and checkpointed before moving to the next priority.

### Parallel Opportunities

- T001, T003, T004 (Foundational, different files) can run in parallel.
- Within US1: T007 and T008 in parallel; T010 in parallel with T009.
- Within US2: T013 and T014 in parallel; T016 has no code dependency on T015 (different layers) but needs T014 (its own test) first.
- US3 (T020-T022) can run in parallel with all of US1/US2 once T002 lands.
- Within Polish: T023 and T024 in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch both tests for User Story 1 together:
Task: "Contract test for MasteryStateResponse.career_connections in backend/tests/contract/test_mastery_state_career_connections.py"
Task: "Component test for CareerConnectionsList in frontend/tests/unit/career-connections-list.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Foundational (schema, validation, loader).
2. Complete Phase 4's T020-T022 alongside Foundational (real content data; no code dependency on US1/US2) so US1 has something real to demo.
3. Complete Phase 2: User Story 1.
4. **STOP and VALIDATE**: run `quickstart.md`'s Scenario 1 independently.
5. This alone is a demoable increment: both the demo learner and a guardian can see one real learner's authored career connections.

### Incremental Delivery

1. Foundational + US3's content population → real authored data ready.
2. User Story 1 → validate → demo (MVP).
3. User Story 2 → validate → demo.
4. Polish → full regression + `quickstart.md`.

## Notes

- No contract-test directory changes beyond the two new files listed above; `contracts/api-changes.md` documents the exact shapes.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

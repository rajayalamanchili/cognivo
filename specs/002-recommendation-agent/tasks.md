# Tasks: Recommendation Agent -- Weak-Area Flagging and Next-Step Suggestions

**Input**: Design documents from `/specs/002-recommendation-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present)

**Tests**: Included. `roadmap.md`'s Milestone 2 Definition of Done makes SC-002 and SC-005 hard gates, and requires all acceptance scenarios to pass plus a Milestone 1 regression check -- so the test tasks below are load-bearing, not optional scaffolding.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete same-phase task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are per `plan.md`'s Project Structure

## Path Conventions

Extends the existing `backend/` monorepo from Milestone 1: `backend/src/{agents,services,api,models}/`, `backend/tests/{unit,integration,contract}/`, `backend/scripts/`, `backend/alembic/versions/`. No frontend change in this milestone (plan.md's Project Structure / Technical Context).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: New package skeletons for this feature -- no new dependency, linting config, or env var (research.md: no new dependency needed)

- [X] T001 [P] Create `backend/src/agents/recommendation/__init__.py` package skeleton per plan.md Project Structure
- [X] T002 [P] Create `backend/src/services/recommendation/__init__.py` package skeleton per plan.md Project Structure
- [X] T003 [P] Create `backend/tests/integration/recommendation/__init__.py` package skeleton per plan.md Project Structure

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema change every user story's audit logging depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Add three new `AssessmentEventType` members (`RECOMMENDATION_REPORT_GENERATED`, `WEAK_AREA_FLAGGED`, `NEXT_STEP_SUGGESTED`) in `backend/src/models/enums.py` per data-model.md
- [X] T005 [P] Relax `AssessmentEvent.topic_id` to nullable in `backend/src/models/assessment_event.py` per data-model.md (additive, backward-compatible -- every existing event type keeps writing a real `topic_id`)
- [X] T006 Generate Alembic migration adding the three new Postgres enum labels and relaxing `topic_id` nullability in `backend/alembic/versions/` (depends on T004, T005)

**Checkpoint**: Foundation ready -- user story implementation can now begin.

---

## Phase 3: User Story 1 - Get a weak-area report grounded in real evidence (Priority: P1)

**Goal**: Analyze a learner's mastery state and assessment-event history and classify every topic as weak (with cited evidence), in-progress, insufficient-data, or not-yet-assessed, plus an overall data-sufficiency verdict and broad-review-needed flag.

**Independent Test**: Call the classification service directly (`backend/src/services/recommendation/weak_area.py`) against a scripted mastery-state/assessment-event fixture with known weak topics and confirm the flagged set + citations match expectations. This is tested at the service layer, not via the live HTTP endpoint -- per FR-006 every flagged topic's response must also carry a `next_step` suggestion, so the full `/recommendations` endpoint isn't wired until User Story 2 completes (the same US1+US2-together pattern `specs/001-domain-agnostic-core/tasks.md` used for its two P1 stories).

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementation

- [X] T007 [US1] Scripted mastery-state/assessment-event fixture builders (known weak topics, tied-weakest topics, not-yet-assessed topics, insufficient-data topics, broad-review scenarios) in `backend/tests/integration/recommendation/scenarios.py` -- MUST NOT be imported by any Sequencing test file (FR-009/SC-005) (depends on T003)
- [X] T008 [P] [US1] Unit test: per-topic classification boundary correctness (weak < 0.4 struggling band with `update_count >= 3`; insufficient_data when `1 <= update_count < 3`; not_yet_assessed when no `MasteryState` row) in `backend/tests/unit/test_weak_area_classification.py`
- [X] T009 [P] [US1] Integration test: weak-area report matches expected flagged set, every flag has non-empty evidence citations (SC-001, SC-002), tied-weakest topics both surface, not-yet-assessed topics explicitly reported, and developing-band topics appear in `in_progress_topic_ids` rather than being omitted (FR-003a, US1 Scenario 5) in `backend/tests/integration/recommendation/test_weak_area_report.py` (depends on T007)
- [X] T010 [P] [US1] Integration test: insufficient-data verdict when every assessed topic has `update_count < 3`, including the single-wrong-answer edge case (SC-004) in `backend/tests/integration/recommendation/test_insufficient_data.py` (depends on T007)
- [X] T011 [P] [US1] Integration test: `broad_review_needed = true` when >= 60% of confidently-assessed topics are struggling, `false` just under that proportion (FR-005) in `backend/tests/integration/recommendation/test_broad_review_threshold.py` (depends on T007)

### Implementation for User Story 1

- [X] T012 [US1] Implement per-topic classification (weak/in_progress/insufficient_data/not_yet_assessed), evidence-citation assembly (join `AssessmentEvent` `event_type=mastery_updated` + `GeneratedQuestion.stem`), data-sufficiency verdict, and broad-review threshold in `backend/src/services/recommendation/weak_area.py` per data-model.md and research.md §4 (depends on T006) -- output MUST include `in_progress_topic_ids` (FR-003a), not just the weak/insufficient/not-yet-assessed buckets

**Checkpoint**: User Story 1's classification logic is independently functional and testable at the service layer.

---

## Phase 4: User Story 2 - Get a concrete next step, not generic advice (Priority: P1)

**Goal**: A prerequisite-aware next-step suggestion per flagged weak topic, and the full customer-facing `GET /api/learners/{learner_id}/recommendations` endpoint assembling User Story 1's classification with this story's suggestions into the FR-006-complete response.

**Independent Test**: Given a flagged topic whose prerequisite is itself unmastered (and whose prerequisite's own prerequisite is also unmastered), request the live endpoint and confirm the suggestion surfaces the true root-cause prerequisite -- not just "practice this topic more," and not stopping one level up the chain.

### Tests for User Story 2 ⚠️

- [ ] T013 [P] [US2] Unit test: prerequisite-chain recursion -- `direct_practice` when all prerequisites mastered, `prerequisite_gap` recursing to the deepest unmastered prerequisite across multiple chain levels, `prerequisite_not_yet_assessed` when the chain hits a topic with no `MasteryState` row, and a topic with more than one unmastered direct prerequisite recurses into only the lowest-`p_mastery` one (ties broken by `Topic.order_index`, per research.md §5) in `backend/tests/unit/test_next_step_prerequisite_chain.py`
- [ ] T014 [P] [US2] Integration test: every suggestion's `recommended_topic_id` and `prerequisite_chain` entries reference real topics in the subject's content artifact, prerequisite-gap suggestions surface the prerequisite rather than the original weak topic (SC-003) in `backend/tests/integration/recommendation/test_next_step_suggestions.py` (depends on T007)
- [ ] T015 [P] [US2] Contract test for `GET /api/learners/{learner_id}/recommendations` per contracts/api.md -- full response shape including `next_step`, `404` on unknown/unvalidated `subject_id`, always-`200` for a learner with no assessment history in `backend/tests/contract/test_recommendation_api.py` (depends on T007)

### Implementation for User Story 2

- [ ] T016 [US2] Implement prerequisite-chain recursion (`suggest_next_step`) in `backend/src/services/recommendation/next_step.py` per data-model.md and research.md §5 (depends on T006)
- [ ] T017 [US2] Implement Recommendation Agent orchestration (`build_weak_area_report`) composing `weak_area.py` (US1) and `next_step.py` (US2) into the full `WeakAreaReport` in `backend/src/agents/recommendation/agent.py` (depends on T012, T016)
- [ ] T018 [US2] Implement `GET /api/learners/{learner_id}/recommendations` endpoint -- `404` subject gate, calls the Recommendation Agent, returns `in_progress_topic_ids` alongside `weak_areas`/`not_yet_assessed_topic_ids`/`insufficient_data_topic_ids` per contracts/api.md, writes `recommendation_report_generated`/`weak_area_flagged`/`next_step_suggested` `AssessmentEvent` rows, wrapped in `traced_request()` in `backend/src/api/routes/recommendation.py` (depends on T017)
- [ ] T019 [P] [US2] Mount the recommendation router in `backend/src/api/main.py` (depends on T018)

**Checkpoint**: User Stories 1 AND 2 together deliver the full, live `/recommendations` endpoint -- Milestone 2's actual demoable slice (mirrors Milestone 1's US1+US2 pattern).

---

## Phase 5: User Story 3 - Trust that recommendations are explainable, not black-box (Priority: P2)

**Goal**: Prove every flag and suggestion is reconstructable after the fact from the audit log and the Langfuse trace.

**Independent Test**: Generate a report, then query `AssessmentEvent` rows and confirm enough detail exists to reconstruct why each flag and suggestion was produced -- no new endpoint needed, matching Milestone 1's SC-006 pattern (direct query, not a dedicated "explain" API).

### Tests for User Story 3

- [ ] T020 [US3] Integration test: audit-log completeness -- one `recommendation_report_generated` row, one `weak_area_flagged` row per flagged topic, one `next_step_suggested` row per suggestion, each with enough payload detail to reconstruct the decision (FR-008) in `backend/tests/integration/recommendation/test_audit_log_completeness.py` (depends on T018)
- [ ] T021 [P] [US3] Integration test: a Langfuse trace is recorded for a `/recommendations` request, matching Milestone 1's SC-008 tracing-completeness pattern in `backend/tests/integration/recommendation/test_tracing_completeness.py` (depends on T018)

**Checkpoint**: All flags/suggestions are independently traceable via the audit log and Langfuse.

---

## Phase 6: User Story 4 - Confirm this agent's job is genuinely distinct from Sequencing (Priority: P2)

**Goal**: Mechanically prove FR-009/FR-010/SC-005 -- Recommendation and Sequencing may diverge on the same mastery state without that being a bug, and their test suites share zero fixtures.

**Independent Test**: Feed the same scripted mastery-state fixture to both Sequencing's `select_next_topic` and Recommendation's report generation; confirm both may name different topics as most urgent, each independently traceable; confirm the fixture-independence check script passes.

### Tests for User Story 4

- [ ] T022 [US4] Implement automated check script failing if any module under `backend/tests/integration/recommendation/` is imported by any module under `backend/tests/integration/test_next_topic_*.py` (or vice versa), or if a scripted-scenario helper name collides between the two, in `backend/scripts/check_no_shared_recommendation_sequencing_fixtures.py` per research.md §6 (depends on T007)
- [ ] T023 [P] [US4] Unit test wiring the check script into the regular pytest suite (mirroring `backend/tests/unit/test_no_subject_conditionals.py`'s wiring of `check_no_subject_conditionals.py`) in `backend/tests/unit/test_no_shared_recommendation_fixtures.py` (depends on T022)
- [ ] T024 [P] [US4] Integration test: same scripted mastery-state fixture fed to both Sequencing's `select_next_topic` and Recommendation's report generation -- confirm they're permitted to name different topics as most urgent, each with independently traceable reasoning (FR-010) in `backend/tests/integration/recommendation/test_sequencing_divergence.py` (depends on T007, T018)

**Checkpoint**: All four user stories independently functional; SC-005 agent-boundary gate mechanically enforced.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and deployment of this feature's schema change

- [ ] T025 [P] Regression check: run Milestone 1's full acceptance-scenario test suite (`backend/tests/`, excluding this feature's new tests) and confirm it still passes unmodified (roadmap.md Milestone 2 Definition of Done)
- [ ] T026 Run `alembic upgrade head` against the `staging` and `production` Neon branches to apply this feature's migration (depends on T006), per `tech-stack.md`'s "Migrations per environment" row
- [ ] T027 Run `quickstart.md` validation end to end against the deployed environment and record results (depends on all prior tasks)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion -- BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion only.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; reuses US1's classification service (T012) to assemble the full response, but its own prerequisite-chain logic (T016) is independently implementable in parallel with US1.
- **User Story 3 (Phase 5)**: Depends on the live endpoint (T018) existing -- it verifies audit/trace output US1+US2 already produce; no new production code of its own.
- **User Story 4 (Phase 6)**: Depends on T007 (fixtures must exist to check) and T018 (the live endpoint, for the divergence comparison).
- **Polish (Phase 7)**: T025 has no hard dependency (can run any time after Setup); T026 needs T006; T027 needs everything.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3/US4.
- **US2 (P1)**: Its `next_step.py` (T016) has no dependency on US1's completion (Foundational is sufficient), but the endpoint (T018) that makes US2 end-to-end testable needs US1's `weak_area.py` (T012) too, since the response always includes both.
- **US3 (P2)**: Depends on US1+US2's endpoint (T018) existing to have something to audit.
- **US4 (P2)**: Depends on US1+US2's fixtures/endpoint existing to have something to check independence against.

### Within Each User Story

- Tests written and failing before implementation.
- Fixtures (T007) before any integration test that uses them.
- Services (`weak_area.py`, `next_step.py`) before agent orchestration; agent orchestration before the endpoint; endpoint before router mounting.

---

## Parallel Example: User Story 1

```bash
# Tests (after Foundational + T007 fixtures are complete):
Task: "Unit test: per-topic classification boundaries in backend/tests/unit/test_weak_area_classification.py"
Task: "Integration test: weak-area report + citations + ties + not-yet-assessed in backend/tests/integration/recommendation/test_weak_area_report.py"
Task: "Integration test: insufficient-data verdict in backend/tests/integration/recommendation/test_insufficient_data.py"
Task: "Integration test: broad-review threshold in backend/tests/integration/recommendation/test_broad_review_threshold.py"
```

---

## Implementation Strategy

### MVP scope: User Stories 1 AND 2 together

Both US1 and US2 are P1, and FR-006 requires every flagged weak area to
carry a next-step suggestion -- so, exactly like Milestone 1's own two
P1 stories, the actual demoable MVP is US1+US2 together (the live
`/recommendations` endpoint), not US1's classification service alone.

1. Complete Phase 1 (Setup) + Phase 2 (Foundational) -- schema change
   ready.
2. Complete Phase 3 (US1) -- weak-area classification works standalone
   at the service layer.
3. Complete Phase 4 (US2) -- prerequisite-aware suggestions work, and
   the full live endpoint is wired.
4. **STOP and VALIDATE**: run both stories' Independent Tests together
   (a scripted weak-area report end to end through the live endpoint).
   This is Milestone 2's MVP.
5. Complete Phase 5 (US3) -- audit/trace completeness confirmed.
6. Complete Phase 6 (US4) -- SC-005 independence mechanically enforced,
   divergence from Sequencing confirmed acceptable.
7. Complete Phase 7 (Polish) -- Milestone 1 regression check, migration
   applied to `staging`/`production`, full quickstart.md validation.

### Incremental delivery

Each phase checkpoint (end of Phase 3, 4, 5, 6, 7) is a point where the
system is in a coherent, testable state.

---

## Notes

- `[P]` tasks = different files, no dependency on an incomplete same-phase task.
- `[Story]` label maps a task to its user story for traceability; Setup, Foundational, and Polish tasks carry no `[Story]` label by design.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently before continuing.
- `/speckit-analyze` MUST run before `/speckit-implement` per CLAUDE.md/Constitution Development Workflow -- do not skip it once this task list is approved.

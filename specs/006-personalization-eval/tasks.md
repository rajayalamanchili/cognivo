---

description: "Task list for Real Personalization Signal -- Sequencing Evaluation Harness"
---

# Tasks: Real Personalization Signal -- Sequencing Evaluation Harness

**Input**: Design documents from `/specs/006-personalization-eval/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present)

**Tests**: Included. This repo's established convention (Milestones 1-2) treats every Success Criterion as an automated hard gate, not something verified by inspection -- this feature's SC-001/SC-003/SC-004/SC-006 follow the same pattern.

**Note**: T004, T006, T010, T030-T034 were added or amended after an initial `/speckit-analyze` pass surfaced one CRITICAL (audit-log scope) and several coverage/wording findings; see `plan.md`'s Revision note and `research.md` §7 for the constitution-compliance fix, and `spec.md`'s FR-004/FR-014/SC-006 for the corresponding requirement changes.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are exact, per `plan.md`'s Project Structure

## Path Conventions

Web app per `plan.md`: `backend/src/`, `backend/tests/`, `frontend/src/`.

---

## Phase 1: Setup

**Purpose**: Project scaffolding for the new evaluation harness code.

- [X] T001 Create `backend/src/services/evaluation/__init__.py`, `backend/tests/unit/evaluation/__init__.py`, and `backend/tests/integration/evaluation/__init__.py` (empty packages, per plan.md's Project Structure)
- [X] T002 [P] Add `backend/evaluation/README.md` documenting the manual run-and-publish workflow (`python -m src.services.evaluation.run_harness`, then commit `backend/evaluation/reports/latest.json` -- Clarifications: manual/on-demand, no CI automation) and `backend/evaluation/reports/.gitkeep` so the directory exists in the repo before any report is published

**Checkpoint**: Directory structure exists; no code yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared simulation machinery every condition and every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Implement the four `SyntheticLearnerProfile` definitions (`cold-start`, `strong-prior`, `uneven`, `prerequisite-bottleneck`) and seeded per-learner, per-topic boolean ground-truth generation in `backend/src/services/evaluation/profiles.py` (research.md §3, §10; data-model.md's `SyntheticLearnerProfile`/`SimulatedLearner`)
- [X] T004 [P] Implement `ConditionRunResult` and `ComparisonReport` dataclasses plus JSON (de)serialization matching `contracts/api.md`'s response schema -- including the computed `non_converged_rate` (`non_converged_count / n`) field per condition/profile/subject/aggregate (FR-006; data-model.md, corrected post-`/speckit-analyze` finding U1) -- in `backend/src/services/evaluation/report.py`
- [X] T005 Implement the shared simulated-answer draw (Bernoulli via `P_S`/`guess_probability` from `src.services.mastery.bkt`, question type from `preferred_question_type`) and mastered-band convergence check (wrapping `mastery_band_for`, not a re-derivation of the 0.7 cutoff) in `backend/src/services/evaluation/conditions.py` (research.md §3, §5; depends on T003)
- [X] T006 Implement synthetic-learner DB lifecycle helpers -- create `is_demo=True` `DemoLearnerProfile` rows (`eval-harness-` prefixed) and empty `MasteryState` for the Sequencing Agent condition; write one `AssessmentEvent` row (type `next_topic_selected`) per Sequencing Agent condition decision, same as `questions.py`'s real route (FR-014; research.md §7, revised post-`/speckit-analyze` finding C1); delete all created rows (`DemoLearnerProfile`, `MasteryState`, and these `AssessmentEvent` rows) at the end of a run, success or failure -- in `backend/src/services/evaluation/conditions.py` (research.md §6-§7; depends on T005, same file)

**Checkpoint**: Foundation ready -- user story implementation can now begin.

---

## Phase 3: User Story 1 - Prove Sequencing Beats Random Ordering (Priority: P1) 🎯 MVP

**Goal**: Run the Sequencing Agent condition and random-order condition side by side for one subject/profile and show the Sequencing Agent condition needs fewer questions to mastery.

**Independent Test**: Run the harness for one subject with one synthetic learner profile; confirm it produces a report showing questions-to-mastery for both conditions, with Sequencing Agent using fewer questions on average.

### Tests for User Story 1

> Write these first; they fail until the corresponding implementation task lands.

- [X] T007 [P] [US1] Unit test: ground-truth generation is deterministic given a fixed seed (same seed -> identical per-learner true-mastery map) in `backend/tests/unit/evaluation/test_ground_truth_determinism.py` (validates T003)
- [X] T008 [P] [US1] Unit test: simulated-answer draw uses the correct Bernoulli rate for truly-mastered vs. not, and the convergence check requires the real confirmation-streak-gated mastered band, not a bare `p_mastery >= 0.7` check, in `backend/tests/unit/evaluation/test_condition_mechanics.py` (validates T005)
- [X] T009 [P] [US1] Integration test: the Sequencing Agent condition's topic choice comes from calling `src.agents.sequencing.agent.select_next_topic` directly (assert via import/call inspection, not output-only comparison) in `backend/tests/integration/evaluation/test_sequencing_condition_real_code_path.py` (FR-008/SC-004; validates T010, written first and expected to fail until then)

### Implementation for User Story 1

- [X] T010 [US1] Implement `run_sequencing_condition` (DB-backed: seeds a synthetic learner via T006's helpers, loops calling real `select_next_topic` + `apply_bkt_update`, writing one `AssessmentEvent` per decision via T006's helper, until converged or budget exhausted) in `backend/src/services/evaluation/conditions.py` (depends on T006)
- [X] T011 [US1] Implement `run_random_condition` (in-memory: uniform-random topic choice each question, no DB writes, per research.md §4) in `backend/src/services/evaluation/conditions.py` (depends on T005)
- [X] T012 [US1] Implement single-subject/single-profile run orchestration and mean/median/non-convergence aggregation over the Sequencing Agent and random conditions in `backend/src/services/evaluation/report.py` (depends on T004, T010, T011)
- [X] T013 [P] [US1] Implement the CLI entry point (`--subject`, `--profile`, `--seed`, `--max-questions-per-topic` flags) that runs T012's orchestration and writes `backend/evaluation/reports/latest.json` in `backend/src/services/evaluation/run_harness.py` (depends on T012)
- [X] T014 [P] [US1] Unit test: for a scripted small run, aggregation reports correct mean/median/non-convergence and the Sequencing Agent condition's mean is lower than random's (SC-001 at small scale) in `backend/tests/unit/evaluation/test_report_shape.py` (depends on T012)

**Checkpoint**: `quickstart.md` step 1 passes. User Story 1 is fully functional and independently demonstrable -- this is the MVP.

---

## Phase 4: User Story 2 - Prove the Result Isn't Cherry-Picked (Priority: P2)

**Goal**: Run the full two-condition (Sequencing Agent, random) comparison across all four profiles and both subjects, with per-breakdown reporting proving the advantage isn't a single lucky case.

**Independent Test**: Run the harness across at least three distinct profiles and both subject content artifacts; confirm the report breaks results out per profile and per subject, not only pooled.

### Implementation for User Story 2

- [X] T015 [US2] Extend the CLI/orchestration to run the full profile x subject matrix when no `--subject`/`--profile` filter is given, populating `ComparisonReport.breakdowns` (one entry per profile x subject) and `aggregate` in `backend/src/services/evaluation/run_harness.py` (depends on T013)
- [X] T016 [US2] Extend `backend/tests/unit/evaluation/test_report_shape.py`: full-matrix report contains all 8 profile x subject breakdown entries, and the Sequencing Agent condition beats random in each individually, not only in the pooled aggregate (depends on T015)
- [X] T017 [P] [US2] Integration test: an identical `--seed` produces a byte-identical report (aside from `run_timestamp`) across two full-matrix runs (SC-003) in `backend/tests/integration/evaluation/test_reproducibility.py` (depends on T015)
- [X] T018 [P] [US2] Verify `python backend/scripts/check_no_subject_conditionals.py` still passes with the new `backend/src/services/evaluation/` code in place (Constitution Principle III; research.md §11) -- add as an assertion in `backend/tests/integration/evaluation/test_reproducibility.py` or a dedicated `backend/tests/integration/evaluation/test_no_subject_conditionals.py` (depends on T015)

**Checkpoint**: `quickstart.md` steps 2 and 4 pass. User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 4 - View the Evidence on a Live Report Page (Priority: P2)

**Goal**: Publish the latest Comparison Report on a live, unauthenticated, nav-linked page so the evidence is part of the deployed demo.

**Independent Test**: Load the report page on the deployed environment without authentication; confirm it renders the latest run's comparison results and a plain-language statement of the result.

### Implementation for User Story 4

- [X] T019 [P] [US4] Implement `GET /api/evaluation/report` -- reads `backend/evaluation/reports/latest.json`, returns its contents or `{"published": false}` if absent, matching `contracts/api.md` -- in `backend/src/api/routes/evaluation.py` (depends on T004 for the report's JSON shape)
- [X] T020 [US4] Register the new router (`app.include_router(evaluation.router)`) in `backend/src/api/main.py` (depends on T019)
- [X] T021 [P] [US4] Contract test for `GET /api/evaluation/report`, covering both the published and not-yet-published response shapes, in `backend/tests/contract/test_evaluation_report_api.py` (depends on T019)
- [X] T022 [P] [US4] Add `getEvaluationReport()` (typed per `contracts/api.md`) to `frontend/src/services/api.ts`
- [X] T023 [US4] Build the report page (`frontend/src/app/personalization-eval/page.tsx` + `personalization-eval-report.tsx`) rendering the headline Sequencing-vs-random result in plain language within one screen (SC-005), and a clear "no evaluation has run yet" state when `published: false` (depends on T022, T020; read `node_modules/next/dist/docs/` first per `frontend/AGENTS.md`)
- [X] T024 [US4] Add minimal main navigation to `frontend/src/app/layout.tsx` linking to the new report page alongside the existing placement/practice/mastery pages (research.md §9; Clarifications: main-nav-linked, not direct-URL-only)

**Checkpoint**: `quickstart.md` steps 7-8 pass. The live deployment shows this milestone's evidence per Constitution Principle IX.

---

## Phase 6: User Story 3 - Compare Against a Fixed Topic Order Too (Priority: P3)

**Goal**: Add the fixed canonical-order baseline as a third condition alongside Sequencing Agent and random.

**Independent Test**: Run the harness with the fixed-order condition included; confirm the report shows a third condition's figures alongside the other two for every profile and subject.

### Implementation for User Story 3

- [X] T025 [US3] Implement `run_fixed_order_condition` (in-memory: cycles topics by ascending `order_index`, repeats the current topic until mastered, then advances; re-cycles remaining unmastered topics after one full pass -- research.md §4) in `backend/src/services/evaluation/conditions.py` (depends on T005)
- [X] T026 [US3] Wire the fixed-order condition into orchestration and aggregation so every `breakdowns` entry and `aggregate` include all three conditions in `backend/src/services/evaluation/report.py` and `backend/src/services/evaluation/run_harness.py` (depends on T025, T015)
- [X] T027 [P] [US3] Unit test: fixed-order condition mechanics -- visits topics in `order_index` order, re-cycles unmastered topics after one pass -- in `backend/tests/unit/evaluation/test_condition_mechanics.py` (depends on T025)
- [X] T028 [US3] Unit test: SC-002 -- the Sequencing Agent condition's pooled aggregate mean is no higher than the fixed-order condition's -- in `backend/tests/unit/evaluation/test_report_shape.py` (depends on T026)

**Checkpoint**: `quickstart.md` step 3 passes. All three conditions are live in the comparison; all four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases and end-to-end verification spanning every story.

- [ ] T029 [P] Edge-case test: a deliberately tiny `--max-questions-per-topic` budget produces a non-zero `non_converged_count`, and mean/median are computed only over converged learners (not skewed by silently dropping non-convergers from the count) in `backend/tests/unit/evaluation/test_condition_mechanics.py`
- [ ] T030 [P] Integration test (SC-006, corrected post-`/speckit-analyze` finding G2): (a) real (`is_demo=False`) `demo_learner_profiles` row count and any pre-existing real `assessment_events` rows are unchanged before vs. after a full harness run; (b) no `eval-harness-*` rows remain in `demo_learner_profiles`, `mastery_states`, or `assessment_events` after the run completes, success or failure -- in `backend/tests/integration/evaluation/test_synthetic_data_cleanup.py`
- [ ] T031 Run `quickstart.md` validation end to end (all 11 steps) against a local dev environment and record results
- [ ] T032 Run the full backend `pytest` suite, including Milestone 1's and Milestone 2's existing test directories, and confirm no regressions (SC-007; added post-`/speckit-analyze` finding G1)
- [ ] T033 [P] Playwright test: the report page renders the headline Sequencing-vs-random result within one screen with no additional navigation required (SC-005; added post-`/speckit-analyze` finding G3), matching this project's existing E2E precedent (`tech-stack.md`'s Testing & evaluation table), in `frontend/tests/e2e/personalization-eval-report.spec.ts`
- [ ] T034 [P] Manual copy-review checklist item: confirm the report page's headline statement (FR-012) is understandable to a non-technical reader with no Spec Kit/BKT jargon -- record the review in `specs/006-personalization-eval/quickstart.md`'s step 7 notes (added post-`/speckit-analyze` finding A1)

**Checkpoint**: All success criteria (SC-001 through SC-007) verified; ready for `/speckit-implement`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately.
- **Foundational (Phase 2)**: Depends on Setup -- BLOCKS all user stories.
- **User Story 1 (Phase 3, P1)**: Depends on Foundational only. This is the MVP.
- **User Story 2 (Phase 4, P2)**: Depends on Foundational + User Story 1 (extends its CLI/orchestration rather than duplicating it).
- **User Story 4 (Phase 5, P2)**: Depends on Foundational's `report.py` schema (T004) only -- does **not** depend on US2 or US3, since it serves whatever report currently exists. Can proceed in parallel with Phase 4 by a second contributor.
- **User Story 3 (Phase 6, P3)**: Depends on Foundational + User Story 2's orchestration (extends the same matrix/aggregation code).
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### User Story Dependencies

Per spec.md, only User Story 1 is a true prerequisite for the others (it establishes the core two-condition engine everything else extends):

- **US1 (P1)**: No dependencies beyond Foundational.
- **US2 (P2)**: Extends US1's single-run orchestration to the full matrix -- not independently buildable before US1 exists.
- **US4 (P2)**: Only needs the report *schema* (Foundational T004), not a specific run's contents -- can be built in parallel with US2/US3 once Foundational is done, though it has nothing real to display until at least one US1-produced report is published.
- **US3 (P3)**: Adds a third condition to US2's matrix machinery -- built after US2.

### Within Each User Story

- Tests written before their corresponding implementation task, expected to fail until it lands.
- Shared-file tasks (`conditions.py`, `report.py`, `run_harness.py`) are sequential within a phase; only genuinely different-file tasks are marked `[P]`.

### Parallel Opportunities

- T001/T002 (Setup) can run together.
- T003/T004 (Foundational) touch different files -- run together; T005/T006 are sequential (same file, and T006 depends on T005).
- Within US1: T007, T008, T009 (three different test files) in parallel; later, T013 and T014 (different files, both depend only on T012) in parallel.
- Within US2: T017 and T018 in parallel (different files).
- Within US4: T019/T021/T022 in parallel (different files; T021 depends on T019 landing first for the contract to test against, but can be drafted in parallel and run once T019 lands).
- Within US3: T027 in parallel with T026/T028 (different file).
- Phase 4 (US2) and Phase 5 (US4) can be worked by two contributors in parallel once Phase 3 (US1) is done, since US4 only needs the report schema, not US2's matrix extension.
- Within Polish: T029/T030/T033/T034 (four different files) in parallel; T032 (full regression suite) runs last since it's the final gate and cheapest to reason about in isolation.

---

## Parallel Example: User Story 1

```bash
# Tests, once Foundational (T003-T006) is done:
Task: "Unit test ground-truth determinism in backend/tests/unit/evaluation/test_ground_truth_determinism.py"
Task: "Unit test condition mechanics in backend/tests/unit/evaluation/test_condition_mechanics.py"
Task: "Integration test real code-path fidelity in backend/tests/integration/evaluation/test_sequencing_condition_real_code_path.py"

# Once T012 (orchestration) lands:
Task: "CLI entry point in backend/src/services/evaluation/run_harness.py"
Task: "Report-shape unit test in backend/tests/unit/evaluation/test_report_shape.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1).
3. **STOP and VALIDATE**: run `quickstart.md` step 1; confirm the Sequencing Agent condition beats random for one subject/profile.
4. This alone proves the milestone's core claim at small scale -- everything after is broadening the evidence (US2, US3) and making it visible (US4).

### Incremental Delivery

1. Setup + Foundational -> engine building blocks ready.
2. US1 -> single-profile proof works -> MVP.
3. US2 -> full-matrix, not-cherry-picked proof.
4. US4 -> evidence goes live on the deployed app (can run in parallel with US2 once US1 is done).
5. US3 -> third baseline condition strengthens the claim further.
6. Polish -> edge cases and full quickstart pass.

### Parallel Team Strategy

With two contributors: one takes US2 (extend the matrix) while the other takes US4 (report page) once US1 lands -- they touch almost entirely disjoint files (`run_harness.py`/`report.py` extensions vs. `api/routes/evaluation.py` + `frontend/`).

---

## Notes

- `[P]` tasks touch different files with no unmet dependency among them.
- `[Story]` labels map every user-story-phase task to spec.md's US1-US4 for traceability.
- Tests are written before the implementation task that makes them pass, per this repo's established convention.
- Every Sequencing Agent condition decision must go through `select_next_topic` -- verified by T009, never a shortcut.
- Commit after each task or logical group, per this repo's normal workflow (not auto-committed by this command).

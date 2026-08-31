---

description: "Task list for Fine-Tuned Misconception Classifier"
---

# Tasks: Fine-Tuned Misconception Classifier

**Input**: Design documents from `/specs/013-misconception-classifier/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included per this project's established convention (every prior milestone's `plan.md` Testing row commits to `pytest`/`Vitest` coverage, and `roadmap.md`'s Definition of Done entries treat test counts as a hard gate, not optional).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3, priority order) so each can be implemented and demonstrated independently, per Setup → Foundational → User Story phases.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3 -- Setup/Foundational/Polish tasks carry no story label

## Path Conventions

Single deployable unit touched: the existing `backend/` project (plus one additive `frontend/` display change). No new project, per `plan.md`'s Project Structure -- this feature ships entirely inside the existing Vercel Services setup.

---

## Phase 1: Setup

**Purpose**: New dependency and package scaffolding, before any schema or code change.

- [X] T001 [P] Add `scikit-learn` as a backend dependency in `backend/pyproject.toml` (research.md §1) -- the only new dependency this feature introduces. Added via `uv add scikit-learn` (resolved `>=1.9.0`, pulling in `numpy`/`scipy`/`joblib` transitively -- `joblib` is what T018 uses for artifact serialization).
- [X] T002 [P] Scaffold `backend/src/services/misconception/__init__.py` per `plan.md`'s Project Structure. Empty file, matching the existing `services/grading_client/`/`services/tutor_agent_client/` convention.
- [X] T003 [P] Create the `backend/misconception_models/` directory (with a `.gitkeep` or README stub) as the checked-in location trained artifacts will be written to (research.md §8) -- empty until T019. `.gitkeep`, matching `backend/evaluation/reports/.gitkeep`'s existing precedent.

**Checkpoint**: Dependency and package skeleton exist. **Done 2026-08-31**: `uv add scikit-learn` succeeds, `import sklearn`/`import src.services.misconception` both clean, full regression suite unaffected (see Phase 6 T032 for the eventual full run).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schema, content-artifact, and data changes every user story depends on. No user story task may start before this phase completes.

- [ ] T004 Add `AssessmentEventType.MISCONCEPTION_CLASSIFIED = "misconception_classified"` to `backend/src/models/enums.py` (data-model.md) -- adds one enum value only, no new column or table, which is the structural proof of FR-009's "no new real-learner-data collection surface"
- [ ] T005 Alembic migration: `ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'misconception_classified'` -- same technique this project already uses for every prior enum extension -- in `backend/alembic/versions/` (depends on T004)
- [ ] T006 [P] Add an optional `misconceptions` field (list of `misconception_id` + `description`) to `services/content_artifact/validator.py`'s `ValidatedTopic` parsing, and persist it through `services/content_artifact/loader.py` into `Topic.skill_definition` (data-model.md, research.md §9) -- optional field; a topic/subject with none defined must still validate and load cleanly (spec.md edge case)
- [ ] T007 [P] Add a `misconceptions` list to >=1 topic in `backend/content/algebra-1/subject.yaml` (research.md §9, depends conceptually on T006's schema support)
- [ ] T008 [P] Add a `misconceptions` list to >=1 topic in `backend/content/biology/subject.yaml` (research.md §9), proving Constitution Principle III holds for a second subject
- [ ] T009 [P] Implement `backend/src/services/misconception/embed.py`: wraps Voyage `voyage-3` embedding of an answer+question-stem pair, reusing the existing embedding call already established for the Tutor Agent (`tutor_agent_client`) rather than a second implementation (research.md §1)
- [ ] T010 Author `backend/evaluation/misconception_ground_truth.jsonl`: a hand-labeled fixture (`question`, `learner_answer`, `expected_grade`, `expected_misconception_id`), mirroring `grading_ground_truth.jsonl`'s existing shape (research.md §6, data-model.md) -- this is the only labeled data available for both training (T018) and evaluation (T031), since no existing `AssessmentEvent` row carries a misconception label (depends on T007, T008 for consistent `misconception_id` values)

**Checkpoint**: Schema, taxonomy, embeddings, and labeled data all exist. User story implementation can begin.

---

## Phase 3: User Story 1 - Named misconception in a weak-area next step (Priority: P1) 🎯 MVP

**Goal**: A learner's accumulated free-text grading history, when it matches a named misconception pattern with enough evidence, produces a cited misconception label the Recommendation Agent's weak-area report surfaces -- with no change to any existing report field.

**Independent Test**: Feed the classifier a learner's accumulated free-text grading history for a topic where wrong answers cluster around one known misconception pattern, run the classification job, and confirm the resulting weak-area report carries the label plus citations, with every other field unchanged.

### Tests for User Story 1 ⚠️

> Write these tests first; confirm they fail before implementing the corresponding service/route code below.

- [ ] T011 [P] [US1] Unit test: the evidence-threshold gate withholds a classification below `>= 3` qualifying free-text incorrect events (research.md §5) in `backend/tests/unit/test_misconception_evidence_threshold.py`
- [ ] T012 [P] [US1] Unit test: the confidence-threshold gate withholds a classification below `MISCONCEPTION_CONFIDENCE_THRESHOLD` (research.md §5) in `backend/tests/unit/test_misconception_confidence_threshold.py`
- [ ] T013 [P] [US1] Integration test: running the classification job for a learner/topic with sufficient matching evidence writes exactly one `misconception_classified` `AssessmentEvent` with a non-empty `cited_event_ids` list, **and** its `misconception_id` matches one of the subject's authored `misconceptions` entries (FR-003 -- never an arbitrary label) (data-model.md) in `backend/tests/integration/test_misconception_classification_job.py`
- [ ] T014 [P] [US1] Integration test: `GET /api/learners/{id}/recommendations` returns a populated, evidence-bearing `misconception` field on the matching `weak_areas[]` entry when a recent `misconception_classified` event exists (contracts/api.md, SC-003) in `backend/tests/integration/test_recommendations_misconception_enrichment.py`
- [ ] T015 [P] [US1] Integration test: with fewer than the minimum qualifying events, no `misconception_classified` event is written and the weak-area report's `misconception` field is `null`, every other field byte-for-byte unchanged from spec 002 (SC-004) in `backend/tests/integration/test_misconception_insufficient_evidence.py`
- [ ] T016 [P] [US1] Integration test: `GET /api/cron/classify-misconceptions` requires `Authorization: Bearer $CRON_SECRET` (`hmac.compare_digest`), returns `503` if unconfigured and `401` on mismatch -- mirroring the existing `reset-demo-data` cron route's own auth tests -- **and**, on a valid request, returns `200` with `{"status": "ok", "classified_count": N}` where `N` equals the number of pairs actually classified (contracts/api.md) in `backend/tests/integration/test_cron_classify_misconceptions_auth.py`

### Implementation for User Story 1

- [ ] T017 [US1] Implement `backend/src/services/misconception/classify.py`: for a given `(learner_id, subject_id, topic_id)`, loads that subject's `classifier.joblib` (research.md §8), embeds qualifying incorrect free-text answers via `embed.py` (T009), applies the evidence (T011) and confidence (T012) thresholds, and writes a `misconception_classified` `AssessmentEvent` citing the qualifying events (depends on T004, T009; satisfies T011, T012, T013)
- [ ] T018 [US1] Implement `backend/scripts/train_misconception_classifier.py`: builds embeddings for `misconception_ground_truth.jsonl`'s labeled examples (T010) via `embed.py`, trains a per-subject `scikit-learn` logistic-regression classifier, serializes each to `backend/misconception_models/<subject_id>/v1/classifier.joblib` (research.md §1/§8) -- an offline, manually-run script, never invoked at request or deploy time (depends on T001, T009, T010)
- [ ] T019 [US1] Run `train_misconception_classifier.py` to generate the initial `classifier.joblib` artifacts for `algebra-1` and `biology`, and check them into `backend/misconception_models/` (T003) (depends on T018, T007, T008)
- [ ] T020 [US1] Add `classify_misconceptions_route` to `backend/src/api/routes/cron.py`, mirroring the existing `reset-demo-data` route's auth pattern exactly: scans learner/topic pairs with newly-qualifying evidence, calls `classify.py` (T017) for each, never raises out of the batch on a single pair's failure, and returns `{"status": "ok", "classified_count": N}` counting how many pairs were actually classified this run (contracts/api.md) (depends on T017; satisfies T016)
- [ ] T021 [US1] Add `{"path": "/api/cron/classify-misconceptions", "schedule": "0 7 * * *"}` to `vercel.json`'s `crons` array (research.md §3) (depends on T020)
- [ ] T022 [US1] Extend `backend/src/services/recommendation/weak_area.py` to read the most recent `misconception_classified` event for each flagged `(learner_id, subject_id, topic_id)` and build a `MisconceptionEnrichment` (data-model.md) when one exists -- its `evidence` list reuses spec 002's existing `EvidenceCitation` construction exactly (including `prior_p_mastery`/`posterior_p_mastery` from each cited event's paired `mastery_updated` event), not a new/narrower shape -- a plain DB read, never a live classifier or LLM call (depends on T017; satisfies T014, T015)
- [ ] T023 [US1] Add the optional `misconception: MisconceptionEnrichment | None` field to `WeakAreaFlag` in `backend/src/agents/recommendation/agent.py`, wired from T022's read, with every existing field untouched (depends on T022)
- [ ] T024 [P] [US1] Render the `misconception` field (description + evidence) on `frontend/src/components/WeakAreaSection.tsx` -- the existing component rendering `flag.topic_id`/`flag.p_mastery`/`flag.next_step` from `RecommendationsResponse` (`@/services/api`) -- when present, unchanged when `null` (depends on T023)

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently -- a learner with enough matching evidence sees a named, cited misconception in their weak-area report.

---

## Phase 4: User Story 2 - Recommendation Agent works with no classifier at all (Priority: P2)

**Goal**: A subject with no authored taxonomy, or a learner/topic with no trained model or classification result yet, produces the exact Milestone 2 weak-area report -- no error, no missing report, no new hard dependency.

**Independent Test**: Request a weak-area report with the classifier unavailable (no taxonomy, no artifact, or a failing classification run) and confirm the report matches Milestone 2's existing shape and fields exactly.

### Tests for User Story 2

- [ ] T025 [P] [US2] Integration test: a subject with no `misconceptions` taxonomy produces a full weak-area report with `misconception: null` on every flag and no error (spec.md edge case) in `backend/tests/integration/test_misconception_no_taxonomy.py`
- [ ] T026 [P] [US2] Integration test: the classification job encountering a missing/unloadable `classifier.joblib` for one subject logs and skips that subject, continuing to classify every other qualifying learner/topic pair without raising (research.md §3) in `backend/tests/integration/test_misconception_missing_artifact.py`

### Implementation for User Story 2

- [ ] T027 [US2] Harden `classify.py` (T017) and the cron route (T020): wrap each learner/topic pair's classification (including artifact load) in a try/except that logs and continues rather than raising, so one bad pair or one subject's missing artifact never fails the whole scheduled run (depends on T017, T020; satisfies T026)
- [ ] T028 [US2] Confirm (via T025) that `weak_area.py`'s read path (T022) already defaults to `misconception: null` whenever no matching event exists -- no separate code path needed, since the read is a plain "event found or not" query with no classifier invocation on the read side (depends on T022; satisfies T025)

**Checkpoint**: At this point, User Stories 1 AND 2 both work independently -- the enrichment is additive everywhere it can run and silently absent everywhere it can't.

---

## Phase 5: User Story 3 - Classifier accuracy is measured honestly against a baseline (Priority: P3)

**Goal**: The trained classifier's misconception-detection accuracy is measured against the hand-labeled validation set and reported alongside a prompted-only baseline's accuracy on the same set, regardless of which one wins.

**Independent Test**: Run the classifier and the prompted-only baseline against `misconception_ground_truth.jsonl` and confirm an accuracy comparison is produced and recorded for both.

### Tests for User Story 3

- [ ] T029 [P] [US3] Unit test: the eval script's accuracy-computation helper returns the correct percentage given a known set of predictions vs. expected labels, including the "classifier scores lower than baseline" case (spec.md Acceptance Scenario 2) in `backend/tests/unit/test_misconception_eval_accuracy.py`

### Implementation for User Story 3

- [ ] T030 [US3] Implement `backend/src/services/misconception/baseline.py`: a single-shot ADK `LlmAgent` call (`LiteLlm`, Claude Haiku default via `MISCONCEPTION_BASELINE_MODEL`) with a Pydantic `output_schema` naming the closest taxonomy label or `none`, structurally mirroring `grading-agent/src/guardrails.py`'s `check_moderation()` (research.md §2) -- used only by the eval script, never the production classification path
- [ ] T031 [US3] Implement `backend/scripts/check_misconception_classifier_eval.py`, mirroring `check_grading_agent_eval.py`'s structure: runs both the trained classifier (T017) and the baseline (T030) against `misconception_ground_truth.jsonl` (T010), computes and prints both accuracies, and exits non-zero **only** on a crash or malformed fixture -- never merely because the classifier scores below the baseline (research.md §7, FR-007) (depends on T017, T030, T010; satisfies T029)

**Checkpoint**: All three user stories are independently functional -- named, cited misconceptions surface when evidence supports them; the report degrades gracefully when it can't; and the classifier's real accuracy is on the record either way.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety, constitutional checks, and the end-to-end validation that only makes sense once every story above is done.

- [ ] T032 [P] Regression check: run Milestones 1-10's full backend and frontend test suites and confirm they still pass unmodified
- [ ] T033 [P] Run `backend/scripts/check_no_subject_conditionals.py` -- confirm zero subject-id-keyed conditionals introduced by this feature's new/changed files (Constitution Principle III)
- [ ] T034 Run `quickstart.md`'s validation scenarios end to end against a live/dev environment with real accumulated free-text grading data (depends on all prior tasks)
- [ ] T035 Update `roadmap.md`'s Milestone 11 status line to reflect implementation completion, per this project's own "update the status line in the same PR" convention (depends on T034)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion (T001/T002 for T009/T018; T003 for T019) -- BLOCKS all user stories.
- **User Stories (Phase 3-5)**: All depend on Foundational completion. US1 (P1) must complete first -- US2's hardening (T027) and US3's eval script (T031) both build directly on US1's `classify.py`/artifacts. US2 and US3 can then proceed in parallel.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task.
- `classify.py` (T017) before the cron route that calls it (T020) and before `weak_area.py`'s read path (T022), which is independent of T017's write side but depends on the event type existing (T004).
- Backend enrichment stable (T022, T023) before frontend rendering (T024).

### Parallel Opportunities

- All Setup tasks (T001-T003) in parallel.
- T006 (schema support) in parallel with T009 (embedding wrapper) -- distinct files; T007/T008 (content YAML, different files) in parallel with each other and once T006 lands.
- All six US1 tests (T011-T016) in parallel -- distinct files, no shared state.
- T024 (frontend) in parallel with backend Polish tasks once T023 lands.
- T025/T026 (US2 tests, distinct files) in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: "Unit test: evidence-threshold gate in backend/tests/unit/test_misconception_evidence_threshold.py"
Task: "Unit test: confidence-threshold gate in backend/tests/unit/test_misconception_confidence_threshold.py"
Task: "Integration test: classification job writes a cited event in backend/tests/integration/test_misconception_classification_job.py"
Task: "Integration test: recommendations endpoint surfaces populated misconception field in backend/tests/integration/test_recommendations_misconception_enrichment.py"
Task: "Integration test: insufficient evidence yields a null field in backend/tests/integration/test_misconception_insufficient_evidence.py"
Task: "Integration test: cron route auth in backend/tests/integration/test_cron_classify_misconceptions_auth.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (blocks everything).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: a learner with sufficient matching evidence sees a named, cited misconception in their weak-area report; a learner without it sees the exact Milestone 2 report.
5. Deploy/demo if ready -- US2's graceful-degradation guarantee is already structurally true from US1's design (T022's read defaults to `null`); US2's own phase only adds the explicit tests and the batch-job hardening.

### Incremental Delivery

1. Setup + Foundational -> foundation ready.
2. Add User Story 1 -> test independently -> this is the MVP: named misconceptions surface when evidence supports them.
3. Add User Story 2 -> test independently -> the classification job survives a missing artifact or an untaxonomied subject without ever degrading the report.
4. Add User Story 3 -> test independently -> the classifier's real accuracy vs. baseline is on the record.
5. Polish -> regression safety, subject-conditional scan, full quickstart run.

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.

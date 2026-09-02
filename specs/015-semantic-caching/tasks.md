---

description: "Task list for Semantic Caching"
---

# Tasks: Semantic Caching

**Input**: Design documents from `/specs/015-semantic-caching/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included per this project's established convention (every prior milestone's `plan.md` Testing row commits to `pytest` coverage, and `roadmap.md`'s Definition of Done entries treat test counts as a hard gate, not optional).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3, priority order) so each can be implemented and demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3 -- Foundational and Polish tasks carry no story label

## Path Conventions

Single existing tree touched: `backend/` (models, services, agents, api/routes, observability, scripts, alembic, tests). No change to `grading-agent/`, `tutor-agent/`, or `frontend/` (plan.md's Project Structure).

---

## Phase 1: Setup

**No new setup required.** This feature introduces no new dependency, package, or service (plan.md's Technical Context) -- `pgvector`, `litellm`'s `voyage/voyage-3` embedding call, and `langfuse>=4.14.4` are already installed and used elsewhere in `backend/`. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two new tables and three shared helpers both User Story 1 and User Story 2 build on (research.md §2-§4).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational

- [ ] T001 [P] Unit tests for `compute_question_signature()` in `backend/tests/unit/caching/test_signature.py`: identical `(stem, answer_key)` always hashes identically; a different `stem` or `answer_key` hashes differently; dict key ordering inside `answer_key` does not change the hash (canonical JSON serialization) -- this is the cross-learner "same question" key research.md §3 depends on
- [ ] T002 [P] Unit tests for `record_cache_hit_trace()` in `backend/tests/unit/caching/test_tracing_cache_hit.py`: mocking `langfuse.get_client()`, confirm it starts a generation-shaped span tagged `usage_details={"input": 0, "output": 0}` (zero token cost) with metadata identifying `cache_entry_id`/`prompt_version`/`cache_type`

### Implementation for Foundational

- [ ] T003 [P] Create the `QuestionGenerationCache` SQLAlchemy model in `backend/src/models/question_generation_cache.py` per data-model.md §1 (all listed columns, composite FK to `topics`, composite index on `(subject_id, topic_id, difficulty, content_version, generation_prompt_version, created_at)`)
- [ ] T004 [P] Create the `GradingResponseCache` SQLAlchemy model in `backend/src/models/grading_response_cache.py` per data-model.md §2 (`answer_embedding: Vector(1024)` matching `content_passage_embedding.py`'s convention, composite index on `(question_signature, grading_logic_version)`)
- [ ] T005 Alembic migration creating both `question_generation_cache` and `grading_response_cache` tables (including their indexes, an IVFFlat/HNSW index on `answer_embedding`), chained off `be66baa35493` (research.md §9) (depends on T003, T004)
- [ ] T006 [P] Implement `compute_question_signature(stem: str, answer_key: dict) -> str` (`sha256` of `stem` + canonical-JSON `answer_key`) in `backend/src/services/cache_common/signature.py` (research.md §3) (depends on T001 failing first)
- [ ] T007 [P] Define the shared `CacheOutcome` frozen dataclass (`hit: bool`, `reason: str | None`) in `backend/src/services/cache_common/outcome.py` (research.md §2/§3's shared wrapper return shape)
- [ ] T008 Implement `record_cache_hit_trace(*, name: str, cache_type: str, cache_entry_id: uuid.UUID, prompt_version: str, learner_id: uuid.UUID) -> None` in `backend/src/observability/tracing.py`, using Langfuse v4's `get_client().start_as_current_generation(...)` with `usage_details={"input": 0, "output": 0}` (research.md §4) (depends on T002 failing first)

**Checkpoint**: Foundation ready -- both cache tables exist, question-signature hashing is deterministic, and a cache hit can be fully traced. User story implementation can now begin.

---

## Phase 3: User Story 1 - Serve Repeated Question-Generation Requests From Cache (Priority: P1) 🎯 MVP

**Goal**: A next-question request for a (topic, difficulty) combination already recently served to another learner is answered from a validated, previously generated question/answer key instead of a new model call.

**Independent Test**: Trigger two next-question requests for the same (topic, difficulty) close together (two different learners); confirm the second returns without a new model call, serving a question that already passed content-artifact validation.

### Tests for User Story 1 ⚠️

> Write these tests first; confirm they fail before implementing T011.

- [ ] T009 [P] [US1] Unit tests for pool lookup/eviction/freshness in `backend/tests/unit/caching/test_question_cache.py`: (a) empty pool -> miss, the passed generator callable is invoked, a row is inserted; (b) pool has a non-recent-duplicate entry -> hit, generator NOT invoked; (c) every pool entry is a near-duplicate of `avoid_stems` -> miss, generator invoked, new row inserted, oldest row evicted once the pool would exceed 5 for that key tuple; (d) an entry older than 24 hours is excluded from matching (treated as a miss) even though not yet deleted; (e) an entry tagged with a different `content_version` or `generation_prompt_version` is never returned (FR-006); (f) a cache-lookup query failure is a miss with `reason="storage_failure"`, and the passed generator callable is still invoked so the request succeeds (FR-008, mirrors T015(e)'s grading-cache case)
- [ ] T010 [P] [US1] Integration test in `backend/tests/integration/test_question_cache_integration.py`: two sequential `get_or_generate_question(...)` calls with the same key return byte-identical `GeneratedQuestionDraft` content on the second call (SC-003), `CacheOutcome.hit is True`; bumping `content_version` between calls forces a fresh generation on the next call (SC-004)

### Implementation for User Story 1

- [ ] T011 [US1] Implement `get_or_generate_question(db, *, subject_id, topic_id, difficulty, content_version, generation_prompt_version, avoid_stems, generate_fn) -> tuple[GeneratedQuestionDraft, CacheOutcome]` in `backend/src/services/question_cache/cache.py`: query the pool by the exact key tuple + `created_at > now() - interval '24 hours'`, exclude rows whose `stem` is a near-duplicate of `avoid_stems` (reusing `services/dedup/checker.py::is_near_duplicate`, same 0.85 threshold), randomly pick a remaining match as a hit; otherwise `await generate_fn()` (the existing `generate_question(...)` call passed in by the caller), compute `question_signature` (T006), insert the new pool row, delete the oldest row for that key tuple beyond 5. Wrap the lookup query itself in try/except -- any exception is a miss with `reason="storage_failure"`, falling through to `generate_fn()` (FR-008) (depends on T003, T005, T006, T007, T009 failing first)
- [ ] T012 [US1] In `backend/src/agents/sequencing/agent.py`, replace the direct `generate_question(...)` call inside `generate_next_question`'s retry loop (lines ~282-292) with `get_or_generate_question(...)`, passing `content_version` fetched from that request's `Subject.content_version` (`db.get(Subject, subject_id).content_version`); add a `cache_outcome: CacheOutcome` field to `NextQuestionResult` (line 243) and populate it from the call (depends on T011)
- [ ] T013 [US1] In `backend/src/services/quiz/session.py`, replace the direct `generate_question(...)` call inside `generate_quiz_question`'s retry loop (lines ~176-186) with `get_or_generate_question(...)`, passing `content_version` from `Subject.content_version` (same as T012); add a `cache_outcome: CacheOutcome` field to `QuizQuestionResult` and populate it. Per spec.md's FR-013 clarification: this path records no dedicated `AssessmentEvent` for question generation even on a fresh call today (only `QUIZ_DIFFICULTY_ADJUSTED`, post-answer) -- its existing per-learner `GeneratedQuestion` row (unchanged by caching, T013 doesn't touch `persist_quiz_question`) already satisfies FR-013's audit-log half for this path, so only call `record_cache_hit_trace(...)` (T008) directly here on a hit, no new payload flag needed (depends on T008, T011)
- [ ] T014 [US1] In `backend/src/api/routes/questions.py`, thread `result.cache_outcome` (T012) into the `NEXT_TOPIC_SELECTED` event's payload (~lines 118-130) as `served_from_cache`/`cache_miss_reason` keys, and call `record_cache_hit_trace(...)` (T008) when `cache_outcome.hit` is `True`, inside this route's existing `traced_request()` block (FR-013) (depends on T008, T012)

**Checkpoint**: quickstart.md Scenarios 1-2 pass -- a repeated topic/difficulty request is served from cache, and a version bump invalidates it.

---

## Phase 4: User Story 2 - Serve Semantically Similar Free-Text Grading Requests From Cache (Priority: P2)

**Goal**: A free-text answer semantically equivalent to one already graded for the same question is answered from a previously computed grade/rubric breakdown instead of a new Grading Agent A2A call.

**Independent Test**: Submit two learners' differently-worded but semantically equivalent answers to the same question; confirm the second submission's grade/rubric breakdown is served without a new Grading Agent call.

### Tests for User Story 2

- [ ] T015 [P] [US2] Unit tests for grading-cache matching in `backend/tests/unit/caching/test_grading_cache.py`: (a) no row with a matching `question_signature` -> miss; (b) matching `question_signature` + `grading_logic_version`, embedding within the similarity threshold -> hit, the Grading Agent client NOT invoked; (c) matching `question_signature` but a different `grading_logic_version` -> miss (FR-006); (d) a similar `answer_embedding` under a *different* `question_signature` -> miss (FR-004, never crosses questions); (e) a storage or embedding failure -> fail-open miss with `reason="storage_failure"` (FR-008)
- [ ] T016 [P] [US2] Integration test in `backend/tests/integration/test_grading_cache_integration.py`: two learners submit differently-worded, semantically equivalent answers to the same cached-pool question; the second call returns a `GradingResult` identical to the first, `CacheOutcome.hit is True`, and `grade_free_text_answer` (mocked/spied) is invoked only once; confirm the response returned for the second submission contains no trace of the first learner's answer text (FR-009)

### Implementation for User Story 2

- [ ] T017 [US2] Implement `get_or_grade_answer(db, *, question_stem, rubric_criteria, learner_answer, question_id, learner_id, grading_logic_version, grade_fn) -> tuple[GradingResult, CacheOutcome]` in `backend/src/services/grading_cache/cache.py`: compute `question_signature` (T006) and `answer_embedding` (reusing `misconception/embed.py::embed_answer(question_stem, learner_answer)` unchanged), query `grading_response_cache` filtered by `question_signature` + `grading_logic_version`, rank remaining rows by `pgvector` cosine distance to `answer_embedding`, take the closest match under 0.15 distance as a hit; otherwise `await grade_fn()` (the existing `grade_free_text_answer(...)` call), insert a new row as a miss. Fail-open (FR-008) on any DB/embedding exception, same pattern as T011 (depends on T004, T005, T006, T007, T015 failing first)
- [ ] T018 [US2] In `backend/src/api/routes/questions.py::_grade_free_text_submission` (~lines 203-227), replace the direct `grade_free_text_answer(...)` call with `get_or_grade_answer(...)` (depends on T017)
- [ ] T019 [US2] In `backend/src/api/routes/questions.py`, add `served_from_cache`/`cache_miss_reason` keys to `answer_payload` (~lines 264-271) before the existing `record_event(...ANSWER_SUBMITTED...)` call, and call `record_cache_hit_trace(...)` (T008) when the grading `CacheOutcome.hit` is `True`, inside this route's existing `traced_request()` block (FR-013) (depends on T008, T018)

**Checkpoint**: quickstart.md Scenarios 3-4 pass -- a semantically equivalent answer hits the cache and never crosses questions or survives a version bump.

---

## Phase 5: User Story 3 - Measure Cache Hit Rate to Verify the Caching Investment Pays Off (Priority: P3)

**Goal**: A maintainer can see the fraction of cache-eligible requests served from cache, broken out by cache type, for a given time window.

**Independent Test**: Run the hit-rate script after a mix of cache-eligible requests and confirm its reported figure matches a manual count from the same window.

### Tests for User Story 3

- [ ] T020 [P] [US3] Unit test for the hit-rate aggregation query in `backend/tests/unit/caching/test_hit_rate_report.py`: given a mix of `AssessmentEvent` rows with `served_from_cache` true/false across both `NEXT_TOPIC_SELECTED` and `ANSWER_SUBMITTED` event types, the aggregation returns the correct hit-rate percentage for each cache type independently (SC-001's per-type scoping, Clarifications 2026-09-02)

### Implementation for User Story 3

- [ ] T021 [US3] Implement `backend/scripts/cache_hit_rate_report.py` (`--since <duration>` CLI flag, mirroring `batch_eval_questions.py`'s CLI shape): query `AssessmentEvent` rows of type `NEXT_TOPIC_SELECTED` and `ANSWER_SUBMITTED` within the window, read `payload->>'served_from_cache'`/`payload->>'cache_miss_reason'`, print a hit-rate percentage per cache type (research.md §8) (depends on T014, T019, T020 failing first)
- [ ] T022 [US3] Implement `backend/scripts/cache_load_test.py`: replay a synthetic, configurable-volume mix of repeated/near-duplicate question-generation requests (same topic/difficulty, multiple synthetic `learner_id`s) and grading requests (paraphrased-but-equivalent answers to shared questions) against `get_or_generate_question`/`get_or_grade_answer` directly (no live server needed), once with caching enabled and once with a `--no-cache` flag that bypasses the pool/lookup entirely; report each cache type's hit rate (via T021's aggregation logic) and the model-call-volume delta between the two runs; exit non-zero if either cache type's hit rate is below 30% (SC-001/SC-002 -- this is the milestone's actual verification mechanism for both, not just a nice-to-have) (depends on T011, T017, T021)

**Checkpoint**: quickstart.md Scenarios 7-9 pass -- the hit-rate script matches a manual count, and the load test demonstrates SC-001/SC-002's per-type hit-rate and cost-reduction targets.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety, threshold validation, and the end-to-end check that only makes sense once every story above is done.

- [ ] T023 [P] Run `backend/scripts/check_no_subject_conditionals.py`; confirm the new cache modules introduce zero subject-id-keyed conditionals (Constitution Principle III, research.md §7)
- [ ] T024 [P] Validate the grading-cache similarity threshold (research.md §3's 0.15 cosine-distance default) against Milestone 6's ground-truth grading eval set, specifically including the spec's negation edge case ("does not require light" vs. "requires light") -- adjust the threshold constant if it produces a false-positive hit against that set
- [ ] T025 [P] Run Milestones 1-12's full `backend`, `grading-agent`, `tutor-agent`, and `frontend` test suites; confirm the same pass rate as immediately before this feature's changes (SC-005)
- [ ] T026 Run `backend/scripts/cache_load_test.py` (T022) against a live/dev environment; confirm each cache type independently reaches >=30% hit rate and model-call volume is measurably reduced vs. the `--no-cache` run (SC-001/SC-002) (depends on T022, T024 -- the similarity threshold should be validated before the load test is treated as a real SC-001/SC-002 signal)
- [ ] T027 Run `quickstart.md`'s full validation scenarios (1-9) end to end against a live/dev environment (depends on T012, T013, T014, T018, T019, T021, T022, T023, T026)
- [ ] T028 Update `roadmap.md`'s Milestone 13 status line to reflect implementation completion (depends on T027)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Not applicable -- see Phase 1 note above.
- **Foundational (Phase 2)**: No dependencies -- start immediately. BLOCKS all user stories.
- **User Story 1 (P1)**: Depends on Foundational only -- no dependency on US2 or US3.
- **User Story 2 (P2)**: Depends on Foundational only. Independent of US1 (uses `question_signature`/`CacheOutcome` from Foundational directly, not from US1's implementation) -- can be implemented in either order relative to US1, though US1's pool is what makes cross-learner grading-cache hits common in practice (research.md §3).
- **User Story 3 (P3)**: T021 depends on T014 (US1) and T019 (US2) existing, since it reads the `served_from_cache` payload keys both add. T022 (the load test) depends on T011 (US1) and T017 (US2) directly -- the only story with real cross-story dependencies.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task.
- US1: T011 (cache lookup) before T012/T013 (call-site wiring, parallel -- different files) before T014 (event payload, depends on T012's new `cache_outcome` field).
- US2: T017 (cache lookup) before T018 (call-site wiring) before T019 (event payload).
- US3: T021 depends on both US1's and US2's payload keys existing (T014, T019); T022 depends on T011, T017, and T021 (it calls T021's aggregation logic).

### Parallel Opportunities

- T001 and T002 (distinct test files) in parallel.
- T003 and T004 (distinct model files) in parallel.
- T006 and T007 (distinct files, no shared state) in parallel once T001/T002 exist to test against.
- T009 and T010 (US1 tests) in parallel with T015 and T016 (US2 tests) once Foundational is done.
- T012 and T013 (distinct call sites) in parallel once T011 lands.
- T023, T024, and T025 (distinct scopes) in parallel.

---

## Parallel Example: Foundational + User Story 1

```bash
# Launch both Foundational test files together:
Task: "Unit tests for compute_question_signature() in backend/tests/unit/caching/test_signature.py"
Task: "Unit tests for record_cache_hit_trace() in backend/tests/unit/caching/test_tracing_cache_hit.py"

# Launch both new models together:
Task: "Create QuestionGenerationCache model in backend/src/models/question_generation_cache.py"
Task: "Create GradingResponseCache model in backend/src/models/grading_response_cache.py"

# Once get_or_generate_question() (T011) exists, wire both call sites together:
Task: "Replace generate_question(...) with get_or_generate_question(...) in backend/src/agents/sequencing/agent.py"
Task: "Replace generate_question(...) with get_or_generate_question(...) in backend/src/services/quiz/session.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational.
2. Complete Phase 3: User Story 1.
3. **STOP and VALIDATE**: quickstart.md Scenarios 1-2 -- a repeated topic/difficulty request is served from cache with identical output, and a prompt/content-version bump invalidates it.
4. This alone delivers the largest share of the milestone's cost/latency value (question generation is the higher-volume surface, plan.md's Summary) and is fully demonstrable on its own.

### Incremental Delivery

1. Foundational -> both tables and shared helpers exist.
2. Add User Story 1 -> test independently -> repeated question-generation requests are served from cache (MVP).
3. Add User Story 2 -> test independently -> semantically similar grading requests are served from cache.
4. Add User Story 3 -> test independently -> hit rate is measurable per cache type, and a synthetic load test demonstrates SC-001/SC-002's actual targets.
5. Polish -> threshold validation, regression safety across Milestones 1-12, the load test's live/dev confirmation run, full quickstart run, roadmap status update.

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.

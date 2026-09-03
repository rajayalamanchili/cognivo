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

- [X] T001 [P] Unit tests for `compute_question_signature()` in `backend/tests/unit/caching/test_signature.py`: identical `(stem, answer_key)` always hashes identically; a different `stem` or `answer_key` hashes differently; dict key ordering inside `answer_key` does not change the hash (canonical JSON serialization) -- this is the cross-learner "same question" key research.md §3 depends on
- [X] T002 [P] Unit tests for `record_cache_hit_trace()` in `backend/tests/unit/caching/test_tracing_cache_hit.py`: mocking `langfuse.get_client()`, confirm it starts a generation-shaped span tagged `usage_details={"input": 0, "output": 0}` (zero token cost) with metadata identifying `cache_entry_id`/`prompt_version`/`cache_type`

### Implementation for Foundational

- [X] T003 [P] Create the `QuestionGenerationCache` SQLAlchemy model in `backend/src/models/question_generation_cache.py` per data-model.md §1 (all listed columns, composite FK to `topics`, composite index on `(subject_id, topic_id, difficulty, content_version, generation_prompt_version, created_at)`)
- [X] T004 [P] Create the `GradingResponseCache` SQLAlchemy model in `backend/src/models/grading_response_cache.py` per data-model.md §2 (`answer_embedding: Vector(1024)` matching `content_passage_embedding.py`'s convention, composite index on `(question_signature, grading_logic_version)`)
- [X] T005 Alembic migration creating both `question_generation_cache` and `grading_response_cache` tables (including their indexes, an IVFFlat/HNSW index on `answer_embedding`), chained off `be66baa35493` (research.md §9) (depends on T003, T004). **Done**: `8e384ff83a4c_semantic_caching_tables.py`. Applied end to end against the dev DB (which required `alembic stamp base` + `alembic upgrade head` first -- that DB's `alembic_version` was stamped past several migrations whose tables had never actually been created, a pre-existing environment issue unrelated to this feature, fixed by replaying the full chain from scratch).
- [X] T006 [P] Implement `compute_question_signature(stem: str, answer_key: dict) -> str` (`sha256` of `stem` + canonical-JSON `answer_key`) in `backend/src/services/cache_common/signature.py` (research.md §3) (depends on T001 failing first)
- [X] T007 [P] Define the shared `CacheOutcome` frozen dataclass (`hit: bool`, `reason: str | None`) in `backend/src/services/cache_common/outcome.py` (research.md §2/§3's shared wrapper return shape)
- [X] T008 Implement `record_cache_hit_trace(*, name: str, cache_type: str, cache_entry_id: uuid.UUID, prompt_version: str, learner_id: uuid.UUID) -> None` in `backend/src/observability/tracing.py`, using Langfuse v4's `get_client().start_as_current_generation(...)` with `usage_details={"input": 0, "output": 0}` (research.md §4) (depends on T002 failing first). **Correction during implementation**: `start_as_current_generation` doesn't exist on the installed v4 client (`langfuse==4.14.x`) -- verified directly against `client.py`. Used the real one-shot API, `get_client().start_observation(name=..., as_type="generation", usage_details=..., metadata=...)`, which returns an observation ended explicitly via `.end()` rather than a context manager -- a better fit here anyway, since there's no wrapped work to run inside a `with` block.

**Checkpoint**: Foundation ready -- both cache tables exist, question-signature hashing is deterministic, and a cache hit can be fully traced. User story implementation can now begin. **Verified 2026-09-02**: 5/5 new unit tests pass; migration applied cleanly to a real dev DB, both tables confirmed present with the exact columns/indexes data-model.md specifies; full `backend` unit suite (188/188) passes with the new models registered.

---

## Phase 3: User Story 1 - Serve Repeated Question-Generation Requests From Cache (Priority: P1) 🎯 MVP

**Goal**: A next-question request for a (topic, difficulty) combination already recently served to another learner is answered from a validated, previously generated question/answer key instead of a new model call.

**Independent Test**: Trigger two next-question requests for the same (topic, difficulty) close together (two different learners); confirm the second returns without a new model call, serving a question that already passed content-artifact validation.

### Tests for User Story 1 ⚠️

> Write these tests first; confirm they fail before implementing T011.

- [X] T009 [P] [US1] Unit tests for pool lookup/eviction/freshness in `backend/tests/unit/caching/test_question_cache.py`: (a) empty pool -> miss, the passed generator callable is invoked, a row is inserted; (b) pool has a non-recent-duplicate entry -> hit, generator NOT invoked; (c) every pool entry is a near-duplicate of `avoid_stems` -> miss, generator invoked, new row inserted, oldest row evicted once the pool would exceed 5 for that key tuple; (d) an entry older than 24 hours is excluded from matching (treated as a miss) even though not yet deleted; (e) an entry tagged with a different `content_version` or `generation_prompt_version` is never returned (FR-006); (f) a cache-lookup query failure is a miss with `reason="storage_failure"`, and the passed generator callable is still invoked so the request succeeds (FR-008, mirrors T015(e)'s grading-cache case). **Done**: 8/8 pass.
- [X] T010 [P] [US1] Integration test in `backend/tests/integration/test_question_cache_integration.py`: two sequential `get_or_generate_question(...)` calls with the same key return byte-identical `GeneratedQuestionDraft` content on the second call (SC-003), `CacheOutcome.hit is True`; bumping `content_version` between calls forces a fresh generation on the next call (SC-004). **Done**: 2/2 pass.

### Implementation for User Story 1

- [X] T011 [US1] Implement `get_or_generate_question(db, *, subject_id, topic_id, difficulty, content_version, generation_prompt_version, avoid_stems, generate_fn) -> tuple[GeneratedQuestionDraft, CacheOutcome]` in `backend/src/services/question_cache/cache.py`: query the pool by the exact key tuple + `created_at > now() - interval '24 hours'`, exclude rows whose `stem` is a near-duplicate of `avoid_stems` (reusing `services/dedup/checker.py::is_near_duplicate`, same 0.85 threshold), randomly pick a remaining match as a hit; otherwise `await generate_fn()` (the existing `generate_question(...)` call passed in by the caller), compute `question_signature` (T006), insert the new pool row, delete the oldest row for that key tuple beyond 5. Wrap the lookup query itself in try/except -- any exception is a miss with `reason="storage_failure"`, falling through to `generate_fn()` (FR-008) (depends on T003, T005, T006, T007, T009 failing first). **Correction during implementation**: `CacheOutcome` (T007) needed a `cache_entry_id: uuid.UUID | None` field, not just `hit`/`reason` -- FR-013's trace/audit-log metadata needs to identify *which* cache entry served a hit, which the originally-scoped shape had no room for. Also: `QuestionGenerationCache.image_url`/`image_alt_text` (data-model.md §1) are never populated here -- unlike `stem`/`answer_key`, they aren't part of what `generate_question` actually returns; the caller derives them fresh from `Topic.image_asset` every time regardless of hit/miss, so caching them would just be stale, unused columns (documented in `cache.py`'s module docstring).
- [X] T012 [US1] In `backend/src/agents/sequencing/agent.py`, replace the direct `generate_question(...)` call inside `generate_next_question`'s retry loop (lines ~282-292) with `get_or_generate_question(...)`, passing `content_version` fetched from that request's `Subject.content_version` (`db.get(Subject, subject_id).content_version`); add a `cache_outcome: CacheOutcome` field to `NextQuestionResult` (line 243) and populate it from the call (depends on T011)
- [X] T013 [US1] In `backend/src/services/quiz/session.py`, replace the direct `generate_question(...)` call inside `generate_quiz_question`'s retry loop (lines ~176-186) with `get_or_generate_question(...)`, passing `content_version` from `Subject.content_version` (same as T012); add a `cache_outcome: CacheOutcome` field to `QuizQuestionResult` and populate it. Per spec.md's FR-013 clarification: this path records no dedicated `AssessmentEvent` for question generation even on a fresh call today (only `QUIZ_DIFFICULTY_ADJUSTED`, post-answer) -- its existing per-learner `GeneratedQuestion` row (unchanged by caching, T013 doesn't touch `persist_quiz_question`) already satisfies FR-013's audit-log half for this path, so only call `record_cache_hit_trace(...)` (T008) directly here on a hit, no new payload flag needed (depends on T008, T011)
- [X] T014 [US1] In `backend/src/api/routes/questions.py`, thread `result.cache_outcome` (T012) into the `NEXT_TOPIC_SELECTED` event's payload (~lines 118-130) as `served_from_cache`/`cache_miss_reason` keys, and call `record_cache_hit_trace(...)` (T008) when `cache_outcome.hit` is `True`, inside this route's existing `traced_request()` block (FR-013) (depends on T008, T012)

**Checkpoint**: quickstart.md Scenarios 1-2 pass -- a repeated topic/difficulty request is served from cache, and a version bump invalidates it. **Verified 2026-09-02**: 15/15 new caching tests pass. Targeted regression (`-k "quiz or next_question or placement or sequencing"`, 98 tests) surfaced one real, fixed issue and two non-issues: (1) `test_quiz_assignment_report.py`'s dedup-exhaustion scenario relied on `patch_generation(stems=[...])` fully controlling generated content, an assumption cross-learner caching breaks -- learners A/B populated the shared `ENTRY_TOPIC` pool before learner D's turn, so D's forced-duplicate mock could be bypassed by a genuine pool hit from A/B's earlier questions; fixed by giving D's isolated dedup-exhaustion scenario a topic no other learner in that test touches (test file only, no product-code change -- this is correct, intended cross-learner-caching behavior, not a bug). (2) Two "server closed the connection unexpectedly" failures and one `test_submit_placement_response_shape_and_unknown_topics` failure during the full ~15-minute run were all confirmed transient/pre-existing on isolated re-run (14/15 passed standalone; the placement test is the same documented Neon/PgBouncer OID-cache-churn flake from Milestone 8, reproduced again in isolation as a clean pass) -- not caused by this feature.

---

## Phase 4: User Story 2 - Serve Semantically Similar Free-Text Grading Requests From Cache (Priority: P2)

**Goal**: A free-text answer semantically equivalent to one already graded for the same question is answered from a previously computed grade/rubric breakdown instead of a new Grading Agent A2A call.

**Independent Test**: Submit two learners' differently-worded but semantically equivalent answers to the same question; confirm the second submission's grade/rubric breakdown is served without a new Grading Agent call.

### Tests for User Story 2

- [X] T015 [P] [US2] Unit tests for grading-cache matching in `backend/tests/unit/caching/test_grading_cache.py`: (a) no row with a matching `question_signature` -> miss; (b) matching `question_signature` + `grading_logic_version`, embedding within the similarity threshold -> hit, the Grading Agent client NOT invoked; (c) matching `question_signature` but a different `grading_logic_version` -> miss (FR-006); (d) a similar `answer_embedding` under a *different* `question_signature` -> miss (FR-004, never crosses questions); (e) a storage or embedding failure -> fail-open miss with `reason="storage_failure"` (FR-008). **Done**: 6/6 pass (added a 7th case beyond plan -- same signature, dissimilar/orthogonal embedding -> miss -- to actually exercise the distance threshold, not just the signature/version filters).
- [X] T016 [P] [US2] Integration test in `backend/tests/integration/test_grading_cache_integration.py`: two learners submit differently-worded, semantically equivalent answers to the same cached-pool question; the second call returns a `GradingResult` identical to the first, `CacheOutcome.hit is True`, and `grade_free_text_answer` (mocked/spied) is invoked only once; confirm the response returned for the second submission contains no trace of the first learner's answer text (FR-009). **Done**: 1/1 pass.

### Implementation for User Story 2

- [X] T017 [US2] Implement `get_or_grade_answer(db, *, question_stem, rubric_criteria, learner_answer, question_id, learner_id, grading_logic_version, grade_fn) -> tuple[GradingResult, CacheOutcome]` in `backend/src/services/grading_cache/cache.py`: compute `question_signature` (T006) and `answer_embedding` (reusing `misconception/embed.py::embed_answer(question_stem, learner_answer)` unchanged), query `grading_response_cache` filtered by `question_signature` + `grading_logic_version`, rank remaining rows by `pgvector` cosine distance to `answer_embedding`, take the closest match under 0.15 distance as a hit; otherwise `await grade_fn()` (the existing `grade_free_text_answer(...)` call), insert a new row as a miss. Fail-open (FR-008) on any DB/embedding exception, same pattern as T011 (depends on T004, T005, T006, T007, T015 failing first). **Correction during implementation**: `grade_fn` is called *with* `question_stem`/`rubric_criteria`/`learner_answer`/`question_id`/`learner_id` kwargs, not as a zero-arg closure like T011's `generate_fn` -- `get_or_grade_answer` already receives every argument `grade_free_text_answer` needs (unlike question generation, which needs sequencing-specific context this wrapper doesn't have), so the real function is passed straight through in production (`grade_fn=grade_free_text_answer`) and a fake substituted in tests. **Design gap surfaced and resolved with the user**: `grading_logic_version` is a code constant living only in the separately-deployed `grading-agent/` service (A2A boundary) -- the backend has no existing way to know it before a live call returns it. Resolved via a new `GRADING_AGENT_LOGIC_VERSION` env var (mirroring `GRADING_AGENT_URL`/`GRADING_AGENT_SHARED_SECRET`'s cross-deployment sync pattern), read at the T018 call site with a fallback default (`"v2"`, the version live at ship time) rather than a hard `os.environ[...]` requirement -- an unset/stale value only ever risks a wrong cache decision, never a request failure, matching FR-008's fail-open spirit; a hard requirement broke every existing free-text test/deployment that hadn't configured the new var yet (confirmed live: 2 real test failures, fixed by switching to `.get(..., "v2")`).
- [X] T018 [US2] In `backend/src/api/routes/questions.py::_grade_free_text_submission` (~lines 203-227), replace the direct `grade_free_text_answer(...)` call with `get_or_grade_answer(...)` (depends on T017)
- [X] T019 [US2] In `backend/src/api/routes/questions.py`, add `served_from_cache`/`cache_miss_reason` keys to `answer_payload` (~lines 264-271) before the existing `record_event(...ANSWER_SUBMITTED...)` call, and call `record_cache_hit_trace(...)` (T008) when the grading `CacheOutcome.hit` is `True`, inside this route's existing `traced_request()` block (FR-013) (depends on T008, T018). `prompt_version` passed as `grading_result.grading_logic_version` (the actually-served row's version), mirroring T014's use of `GENERATION_PROMPT_VERSION`.

**Post-`/speckit-clarify` redesign (2026-09-02, T024's finding -- see T024 below)**: T017-T019/T022's single-embedding-threshold design was disproven live and replaced with a two-stage gate before Phase 6 could complete. `get_or_grade_answer` (T017) gained a new required `verify_fn` parameter (same injectable-callable pattern as `grade_fn`) and its threshold constant was renamed `PREFILTER_DISTANCE_CEILING` (0.15 -> 0.5, now efficiency-only, not a correctness boundary). New module `backend/src/services/grading_cache/equivalence.py` (`classify_criteria_met`/`matches_cached_criteria_pattern`) implements the actual gate: a cheap Haiku classification re-checking the new answer against the rubric, compared against the candidate row's stored `criteria_met` pattern -- never the original answer text (FR-009). `questions.py` (T018) now passes `verify_fn=functools.partial(matches_cached_criteria_pattern, session_service=get_database_session_service())`. `cache_load_test.py` (T022) updated with a fake `verify_fn` (always confirms -- it measures cache-lookup mechanics, not classifier accuracy). T015/T016's tests rewritten for the two-stage flow (9 tests total, up from 7); all pass. Full detail in research.md §3 and data-model.md §2.

**Checkpoint**: quickstart.md Scenarios 3-4 pass -- a semantically equivalent answer hits the cache and never crosses questions or survives a version bump. **Verified 2026-09-02**: 8/8 new grading-caching tests pass (T015's 6 + T016's 1, plus one added case beyond plan). Targeted regression (`-k "free_text or grading or answer or caching"`, 96 tests) all pass -- including the 2 free-text integration tests that initially failed with a `KeyError: GRADING_AGENT_LOGIC_VERSION` before T017's fallback-default fix (see T017's implementation note).

---

## Phase 5: User Story 3 - Measure Cache Hit Rate to Verify the Caching Investment Pays Off (Priority: P3)

**Goal**: A maintainer can see the fraction of cache-eligible requests served from cache, broken out by cache type, for a given time window.

**Independent Test**: Run the hit-rate script after a mix of cache-eligible requests and confirm its reported figure matches a manual count from the same window.

### Tests for User Story 3

- [X] T020 [P] [US3] Unit test for the hit-rate aggregation query in `backend/tests/unit/caching/test_hit_rate_report.py`: given a mix of `AssessmentEvent` rows with `served_from_cache` true/false across both `NEXT_TOPIC_SELECTED` and `ANSWER_SUBMITTED` event types, the aggregation returns the correct hit-rate percentage for each cache type independently (SC-001's per-type scoping, Clarifications 2026-09-02). **Done**: 2/2 pass -- built against in-memory (unpersisted) `AssessmentEvent` instances, no DB needed, since `compute_hit_rates()` only reads `.event_type`/`.payload` (mirrors `batch_eval_questions.py`'s pure `evaluate_sample()`).

### Implementation for User Story 3

- [X] T021 [US3] Implement `backend/scripts/cache_hit_rate_report.py` (`--since <duration>` CLI flag, mirroring `batch_eval_questions.py`'s CLI shape): query `AssessmentEvent` rows of type `NEXT_TOPIC_SELECTED` and `ANSWER_SUBMITTED` within the window, read `payload->>'served_from_cache'`/`payload->>'cache_miss_reason'`, print a hit-rate percentage per cache type (research.md §8) (depends on T014, T019, T020 failing first). **Correction during implementation**: reads `event.payload["served_from_cache"]` in Python after a normal SQLAlchemy row fetch, not a raw `->>'...'` JSON SQL operator -- matches this codebase's existing convention for reading `AssessmentEvent.payload` fields (`services/quiz/session.py`, `services/recommendation/weak_area.py` do the same), simpler than a JSON-operator query for the same result. `compute_hit_rates()` is a pure function (no DB) so T020 doesn't need `database_available`. **Verified live**: found and fixed a real pre-existing dev-DB issue in the process -- `alembic current` reported this feature's head revision but several tables (including `assessment_events`) didn't actually exist (same class of stamped-past-ungenerated-migrations issue T005 hit and fixed earlier the same day, apparently recurred). Re-ran `alembic stamp base` + `alembic upgrade head`; confirmed all 29 expected tables present immediately after. Script then ran cleanly against the live dev DB.
- [X] T022 [US3] Implement `backend/scripts/cache_load_test.py`: replay a synthetic, configurable-volume mix of repeated/near-duplicate question-generation requests (same topic/difficulty, multiple synthetic `learner_id`s) and grading requests (paraphrased-but-equivalent answers to shared questions) against `get_or_generate_question`/`get_or_grade_answer` directly (no live server needed), once with caching enabled and once with a `--no-cache` flag that bypasses the pool/lookup entirely; report each cache type's hit rate (via T021's aggregation logic) and the model-call-volume delta between the two runs; exit non-zero if either cache type's hit rate is below 30% (SC-001/SC-002 -- this is the milestone's actual verification mechanism for both, not just a nice-to-have) (depends on T011, T017, T021). `generate_fn`/`grade_fn` are lightweight in-script fakes (research.md §10: no new test infra, not real LLM/A2A calls); `embed_answer` is patched to a deterministic pseudo-embedding (same question template -> identical vector, different template -> orthogonal) so "paraphrased-but-equivalent" answers can be simulated without a real Voyage call. Reuses T021's `compute_hit_rates()` directly by wrapping each `CacheOutcome` in a minimal `SimpleNamespace` shaped like the `AssessmentEvent` fields it reads, rather than duplicating the aggregation math. Requires `algebra-1`'s content artifact already loaded (FK constraint on `question_generation_cache`); checks this precondition explicitly with a clear error rather than a raw FK-violation traceback. **Verified live** (same freshly-migrated dev DB as T021, content loaded via `scripts/load_content_artifact.py`): `--requests 30` cached run -> question_generation 24/30 hits (80.0%), grading 27/30 hits (90.0%), both well above the 30% floor; `--requests 30 --no-cache` baseline -> 30 `generate_fn` calls (vs. 6 cached) and 30 `grade_fn` calls (vs. 3 cached), demonstrating SC-002's model-call-volume reduction. Exit code 0 on both runs.

**Checkpoint**: quickstart.md Scenarios 7-9 pass -- the hit-rate script matches a manual count, and the load test demonstrates SC-001/SC-002's per-type hit-rate and cost-reduction targets. **Verified 2026-09-02**: T020's 2/2 unit tests pass; T021 and T022 each confirmed live against the (freshly re-migrated) dev DB per their implementation notes above -- both cache types clear the 30% hit-rate floor and the `--no-cache` baseline shows a clear model-call-volume reduction. Full `tests/unit/caching/` + question-cache/grading-cache integration suite (24 tests) still green after the dev-DB migration replay.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety, threshold validation, and the end-to-end check that only makes sense once every story above is done.

- [X] T023 [P] Run `backend/scripts/check_no_subject_conditionals.py`; confirm the new cache modules introduce zero subject-id-keyed conditionals (Constitution Principle III, research.md §7). **Done**: `OK: no subject-id-keyed conditionals found in backend/src for ['algebra-1', 'biology']`.
- [X] T024 [P] Validate the grading-cache similarity threshold (research.md §3's 0.15 cosine-distance default) against Milestone 6's ground-truth grading eval set, specifically including the spec's negation edge case ("does not require light" vs. "requires light") -- adjust the threshold constant if it produces a false-positive hit against that set. **First pass (2026-09-02) found the threshold itself was unfixable**: `backend/scripts/validate_grading_cache_threshold.py` against real `voyage/voyage-3` embeddings showed 14/19 same-question opposite-`expected_correct` ground-truth pairs fell within 0.15 distance (false positives), including the spec's literal negation example (distance 0.0593). No single threshold value could work -- the two genuine true-positive paraphrase pairs measured 0.0651/0.0789, *inside* the false-positive range (0.0133-0.1360). Root cause: `embed_answer(question_stem, answer_text)` embeds the shared, often-longer question stem alongside the answer, so same-question pairs cluster tightly regardless of meaning -- a known general limitation of sentence embeddings on negation. Surfaced to the user as a grading-correctness gap (FR-002/FR-003), not a tunable constant; resolved via `/speckit-clarify` (spec Clarifications, 2026-09-02): embedding distance is now only an efficiency pre-filter (widened to 0.5, `PREFILTER_DISTANCE_CEILING`), and a new cheap rubric-criteria re-classification gate (`backend/src/services/grading_cache/equivalence.py`) is what actually decides a hit -- classifying the new answer against the rubric and comparing to the candidate's stored `criteria_met` pattern, never the original answer text (FR-009). **Re-validation with the real two-stage gate** (`validate_grading_cache_threshold.py` rewritten to exercise `classify_criteria_met` directly, real Haiku calls): first run found one more real bug -- blank/whitespace answers misclassified as satisfying every criterion (a Haiku-specific weakness, fixed with an explicit blank/off-topic instruction in the prompt). Final run: `OK: the equivalence gate produces no false positives against the ground-truth set + the spec's negation example (2/2 genuine paraphrase pairs would still register as hits)`. `research.md` §3 and `data-model.md` §2 updated to describe the two-stage design; the original single-threshold design is documented there as disproven, not silently deleted.
- [X] T025 [P] Run Milestones 1-12's full `backend`, `grading-agent`, `tutor-agent`, and `frontend` test suites; confirm the same pass rate as immediately before this feature's changes (SC-005). **Done 2026-09-02**: `backend` 436/436 (0:15:45), `grading-agent` 23/23, `tutor-agent` 26/26, `frontend` 64/64 -- 100% across all four, no regressions. **Re-run after T024's post-clarify grading-cache redesign** (`backend` only, the only project touched by that rework): 438/438 (0:15:12) -- 100%, the +2 vs. the first run is the two new test cases the two-stage gate's tests added, not a discrepancy.
- [X] T026 Run `backend/scripts/cache_load_test.py` (T022) against a live/dev environment; confirm each cache type independently reaches >=30% hit rate and model-call volume is measurably reduced vs. the `--no-cache` run (SC-001/SC-002) (depends on T022, T024 -- the similarity threshold should be validated before the load test is treated as a real SC-001/SC-002 signal). **Done 2026-09-02** (re-run after T017/T022's post-clarify redesign added `verify_fn`): `--requests 30` cached run -> question_generation 24/30 hits (80.0%), grading 27/30 hits (90.0%), both well above the 30% floor; `--requests 30 --no-cache` baseline -> 30 `generate_fn` calls (vs. 6 cached) and 30 `grade_fn` calls (vs. 3 cached). Hit the same recurring Neon stamped-past-ungenerated-migrations flake as Phase 5 (T021's note) -- same `alembic stamp base` + `upgrade head` fix, content reloaded, re-ran clean.
- [X] T027 Run `quickstart.md`'s full validation scenarios (1-9) end to end against a live/dev environment (depends on T012, T013, T014, T018, T019, T021, T022, T023, T026). **Done 2026-09-02**: Scenarios 1-2 (US1) and 7-9 already verified live in earlier phases (Phase 3/5 checkpoints, T025). Scenarios 3/4/6 -- the parts the post-clarify redesign actually changed -- got a fresh live check specifically for this task: a throwaway script (`TestClient` against the real app, real DB, real `embed_answer`/Voyage call, real Haiku equivalence check via the actual `functools.partial(matches_cached_criteria_pattern, ...)` wiring in `questions.py`, only the outer Grading Agent A2A call mocked -- this project's established test-boundary convention, real model calls never enter the pytest suite itself, see `scripts/` dir precedent) confirmed: two learners submitting a genuine paraphrase to the same question -> second submission returns the first's exact cached grade, `grade_free_text_answer` NOT called (Scenario 3); the `ANSWER_SUBMITTED` audit-log payload for that hit shows `served_from_cache: true`, `cache_miss_reason: null` (Scenario 6). Found and diagnosed one false alarm along the way: an initial run using mismatched `grading_logic_version` between the two mocked calls produced a miss -- isolated diagnostic confirmed the equivalence gate itself was correct (distance 0.042, identical criteria_met patterns); the mismatch was in the throwaway script's own mock setup, not a real bug, and doubled as a live confirmation that FR-006's version-mismatch invalidation genuinely works (Scenario 4's version-bump half). FR-004's cross-question isolation (Scenario 4's other half) already covered by T015's `test_similar_embedding_under_different_signature_is_a_miss`. Scenario 5 (fail-open) already thoroughly covered by T015's `test_embedding_failure_is_a_fail_open_miss`/`test_verification_failure_fails_open_to_a_miss` unit tests -- not re-run live, no incremental value over those.
- [X] T028 Update `roadmap.md`'s Milestone 13 status line to reflect implementation completion (depends on T027). **Done**: full status entry added, matching Milestone 11/12's convention -- spec/branch/task-count, the real design change T024 forced and why, and the live SC-001/SC-002/SC-005 verification figures.

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

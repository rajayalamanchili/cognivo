---

description: "Task list for Moderation & Shielding Classification Caching"
---

# Tasks: Moderation & Shielding Classification Caching

**Input**: Design documents from `/specs/026-moderation-shielding-cache/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included per this project's established convention (every prior milestone's `plan.md` Testing row commits to `pytest` coverage, and `roadmap.md`'s Definition of Done entries treat test counts as a hard gate, not optional) -- mirrors spec 015's identical tasks.md convention statement.

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3, priority order) so each can be implemented and demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3 -- Foundational and Polish tasks carry no story label

## Path Conventions

Single existing tree touched: `backend/` (models, services, api/routes, scripts, alembic, tests). No change to `grading-agent/`, `tutor-agent/`, or `frontend/` (plan.md's Project Structure).

---

## Phase 1: Setup

**No new setup required.** This feature introduces no new dependency, package, or service (plan.md's Technical Context) -- `hashlib` is stdlib, already used by `cache_common/signature.py`; `langfuse`/SQLAlchemy/Alembic are already installed and used elsewhere in `backend/`. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two new tables, the two new signature helpers, and the `tutor_exchanges` schema change both User Story 1 and User Story 2 build on (research.md §1-§2, §6; data-model.md §1-§3).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational

- [X] T001 [P] Add unit tests for `compute_text_signature()` and `compute_paired_signature()` to the existing `backend/tests/unit/caching/test_signature.py` (alongside `compute_question_signature`'s existing tests): identical normalized text always hashes identically; case/whitespace-only differences hash identically (normalization); different text hashes differently; `compute_paired_signature` is order-sensitive (`(a, b) != (b, a)`'s hash) -- this is the exact-match key research.md §2 and spec.md FR-003/FR-004 depend on. **Done**: 6/6 new tests pass (10/10 in the file overall).

### Implementation for Foundational

- [X] T002 [P] Create the `ModerationCache` SQLAlchemy model in `backend/src/models/moderation_cache.py` per data-model.md §1 (`cache_entry_id`, `text_signature`, `moderation_instruction_version`, `allowed`, `created_at`, `last_served_at`, `hit_count`; composite index on `(text_signature, moderation_instruction_version)`). Registered in `src/models/__init__.py`.
- [X] T003 [P] Create the `ShieldingClassificationCache` SQLAlchemy model in `backend/src/models/shielding_classification_cache.py` per data-model.md §2 (`cache_entry_id`, `pair_signature`, `shielding_classification_instruction_version`, `matches`, `created_at`, `last_served_at`, `hit_count`; composite index on `(pair_signature, shielding_classification_instruction_version)`). Registered in `src/models/__init__.py`.
- [X] T004 Add `shielding_checks_total: int NOT NULL DEFAULT 0` and `shielding_checks_from_cache: int NOT NULL DEFAULT 0` columns to the `TutorExchange` model in `backend/src/models/tutor_exchange.py` per data-model.md §3
- [X] T005 Alembic migration creating `moderation_cache`, `shielding_classification_cache` (including their indexes), and altering `tutor_exchanges` to add the two new columns, chained off the current head `824e2c5a0678` (research.md §6) (depends on T002, T003, T004). **Done**: `cf781636cccd_guardrail_caching_tables.py`. `alembic heads` confirms a single clean head, no branching. **Not yet applied live**: no `DATABASE_URL` configured in this environment -- needs a real `alembic upgrade head` run against a dev DB before this is treated as fully verified (flag for Polish/live-verification, mirrors spec 015's T005 note about the recurring Neon stamped-past-migrations flake).
- [X] T006 [P] Implement `compute_text_signature(text: str) -> str` and `compute_paired_signature(first: str, second: str) -> str` (both `sha256` of normalized/trimmed/casefolded input, research.md §2) in `backend/src/services/cache_common/signature.py`, alongside the existing `compute_question_signature` (depends on T001 failing first). **Done**: normalization is trim + casefold (`_normalize` helper).

**Checkpoint**: Foundation ready -- both cache tables and the `tutor_exchanges` columns exist, both signature functions are deterministic and normalize correctly. User story implementation can now begin. **Verified 2026-09-30**: 10/10 signature unit tests pass; full `backend` unit suite (362/362) passes with the new models registered; `check_no_subject_conditionals.py` and `check_deletion_cascade_coverage.py` both pass unchanged. Migration file created and `alembic heads` confirms a single clean chain, but not yet applied against a live DB (no `DATABASE_URL` in this environment) -- pending live verification before Polish.

---

## Phase 3: User Story 1 - Serve Repeated Moderation Checks From Cache (Priority: P1) 🎯 MVP

**Goal**: A free-text or stepwise answer submission whose normalized text has already been moderation-classified is answered from the cached allow/block verdict instead of a new moderation model call.

**Independent Test**: Submit the same exact answer text twice (same or different learners); confirm the second submission's verdict is served without a new moderation model call, and the grading/rejection flow behaves identically to an uncached verdict.

### Tests for User Story 1 ⚠️

> Write these tests first; confirm they fail before implementing T009.

- [X] T007 [P] [US1] Unit tests for moderation-cache lookup in `backend/tests/unit/caching/test_moderation_cache.py`: (a) no matching `text_signature` -> miss, `check_fn` invoked, a row inserted; (b) matching `text_signature` + current `moderation_instruction_version` -> hit, `check_fn` NOT invoked, served verdict equals the stored `allowed` value; (c) matching `text_signature` but a different `moderation_instruction_version` -> miss (FR-005); (d) two texts differing only in case/leading-trailing whitespace produce the same signature and the second is a hit (FR-003's normalization); (e) two genuinely different texts never collide (independent misses); (f) a cache-lookup query failure is a miss with `reason="storage_failure"`, and `check_fn` is still invoked so the request succeeds (FR-006); (g) after an insert, querying the `ModerationCache` row directly confirms no column holds the raw submitted text -- only `text_signature`, never the original string (FR-008)
- [X] T008 [P] [US1] Integration test in `backend/tests/integration/test_guardrail_caching.py`: two sequential `get_or_check_moderation(...)` calls with identical (normalized) text return the same `bool` on the second call (FR-007, SC-003 -- a hit and a miss for the same text are indistinguishable to the caller), `CacheOutcome.hit is True`, and the injected `check_fn` is invoked only once; bumping `moderation_instruction_version` between calls forces a fresh `check_fn` invocation on the next call (SC-004)

### Implementation for User Story 1

- [X] T009 [US1] Implement `get_or_check_moderation(db, *, text, instruction_version, check_fn) -> tuple[bool, CacheOutcome]` in `backend/src/services/moderation_cache/cache.py`: compute `text_signature` (T006), query `moderation_cache` filtered by `text_signature` + `instruction_version`, serve `allowed` on a match; otherwise `await check_fn()`, insert a new row. Wrap the lookup query and the insert each in their own try/except -- any exception on lookup is a miss with `reason="storage_failure"`, falling through to `check_fn()` (FR-006); an insert failure is swallowed the same way (best-effort write, mirrors `question_cache/cache.py`'s existing shape) (depends on T002, T005, T006, T007 failing first)
- [X] T010 [US1] In `backend/src/api/routes/questions.py`, wrap both `check_moderation(...)` call sites with `get_or_check_moderation`: in `_grade_free_text_submission`, `get_or_check_moderation(db, text=response_text, instruction_version=MODERATION_INSTRUCTION_VERSION, check_fn=functools.partial(check_moderation, response_text, session_service=get_database_session_service()))`; in `_grade_stepwise_submission`, the same shape with that function's concatenated step text bound in place of `response_text`. Thread the returned `CacheOutcome` back to each caller (depends on T009)
- [X] T011 [US1] In `backend/src/api/routes/questions.py`, add `moderation_served_from_cache`/`moderation_cache_miss_reason` keys (populated from T010's `CacheOutcome`) to: the `FREE_TEXT_SUBMISSION_REJECTED` payload built in `_reject_free_text` (moderation-block path) and the `answer_payload` dict built for both `FREE_TEXT` and `MULTI_STEP` question types (moderation-allow path, ahead of the existing `ANSWER_SUBMITTED`/rejection `record_event` calls); call `record_cache_hit_trace(name="moderation_cache_hit", cache_type="moderation", cache_entry_id=..., prompt_version=MODERATION_INSTRUCTION_VERSION, learner_id=...)` when the moderation `CacheOutcome.hit` is `True`, inside the route's existing `traced_request()` block (FR-009) (depends on T010)

**Checkpoint**: quickstart.md Scenario 1 passes -- a repeated (normalized) submission is served from cache with an identical verdict, and an instruction-version bump invalidates it. This alone delivers the largest share of this feature's call-volume reduction (moderation is 1:1 per submission, the highest-volume of the two checks) and is fully demonstrable on its own.

---

## Phase 4: User Story 2 - Serve Repeated Shielding-Match Checks From Cache (Priority: P2)

**Goal**: A shielding-classifier check for a (open question stem, tutor message) pairing that has already been classified is answered from the cached match/no-match verdict instead of a new classifier model call.

**Independent Test**: Send the same tutoring-chat message against the same open question twice; confirm the second check's result is served without a new classifier model call, and a different open question paired with the same message still triggers a fresh call.

### Tests for User Story 2

- [X] T012 [P] [US2] Unit tests for shielding-cache lookup in `backend/tests/unit/caching/test_shielding_cache.py`: (a) no matching `pair_signature` -> miss, `classify_fn` invoked, a row inserted; (b) matching `pair_signature` + current `shielding_classification_instruction_version` -> hit, `classify_fn` NOT invoked; (c) matching `pair_signature` but a different instruction version -> miss (FR-005); (d) the same `tutor_question` paired with a *different* `open_question_stem` never matches a cache entry created for the first pairing (FR-004, per-question scoping); (e) a cache-lookup query failure is a miss with `reason="storage_failure"`, `classify_fn` still invoked (FR-006); (f) after an insert, querying the `ShieldingClassificationCache` row directly confirms no column holds the raw open-question stem or tutor-message text -- only `pair_signature`, never either original string (FR-008)
- [X] T013 [P] [US2] Integration test in `backend/tests/integration/test_guardrail_caching.py`: two sequential `get_or_classify_match(...)` calls with the identical (open question, message) pairing return the same `bool` on the second call (SC-003 -- a hit and a miss for the same pairing are indistinguishable to the caller), `CacheOutcome.hit is True`, `classify_fn` invoked only once; the same message against a different open question misses; bumping `shielding_classification_instruction_version` forces a fresh call (SC-004)

### Implementation for User Story 2

- [X] T014 [US2] Implement `get_or_classify_match(db, *, open_question_stem, tutor_question, instruction_version, classify_fn) -> tuple[bool, CacheOutcome]` in `backend/src/services/shielding_cache/cache.py`: compute `pair_signature` (T006), query `shielding_classification_cache` filtered by `pair_signature` + `instruction_version`, serve `matches` on a match; otherwise `await classify_fn()`, insert a new row. Same fail-open try/except shape as T009 (FR-006) -- note `classify_fn` may itself raise `ClassificationFailedError` (shielding.py's existing exception, not a caching concern); that exception MUST propagate unchanged so `determine_shielding`'s existing FR-010 fail-safe still triggers on a genuine classification failure, only a *cache-storage* exception is swallowed here (depends on T003, T005, T006, T012 failing first)
- [X] T015 [US2] In `backend/src/services/tutor/session.py`, replace the `functools.partial(classify_match, session_service=...)` binding passed to `determine_shielding`'s `match_fn` parameter with a small local async wrapper (not a bare `functools.partial`, since `determine_shielding` awaits `match_fn(...) -> bool` directly and has no visibility into per-call outcomes once it returns its one aggregate `ShieldingDecision`): the wrapper closes over a mutable counter object created at the top of this call site (e.g. `check_counts = {"total": 0, "from_cache": 0}`), calls `get_or_classify_match(db, open_question_stem=..., tutor_question=..., instruction_version=SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION, classify_fn=functools.partial(classify_match, open_question_stem=..., tutor_question=..., session_service=get_database_session_service()))`, increments `check_counts["total"]` every call and `check_counts["from_cache"]` when the returned `CacheOutcome.hit` is `True`, calls `record_cache_hit_trace(name="shielding_cache_hit", cache_type="shielding", cache_entry_id=..., prompt_version=SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION, learner_id=...)` on that same hit (FR-009), and returns just the `bool` `determine_shielding` expects -- this wrapper (not `determine_shielding` itself, and not code after it returns) is the only point with per-check visibility, so it's where all counting and tracing must happen (depends on T014)
- [X] T016 [US2] In `backend/src/services/tutor/session.py`, after `determine_shielding` returns, persist T015's `check_counts["total"]`/`check_counts["from_cache"]` onto the `shielding_checks_total`/`shielding_checks_from_cache` columns of the `TutorExchange` row created for that exchange (data-model.md §3) (depends on T015)

**Checkpoint**: quickstart.md Scenario 2 passes -- a repeated (question, message) pairing is served from cache, a different pairing still triggers a real check, and an instruction-version bump invalidates a cached pairing.

---

## Phase 5: User Story 3 - Measure Cache Hit Rate for Both New Cache Types (Priority: P3)

**Goal**: A maintainer can see, per time window, the fraction of cache-eligible moderation and shielding checks served from cache, broken out by cache type.

**Independent Test**: Run a synthetic load test replaying a mix of repeated/duplicate traffic and confirm the reported hit rate for each cache type matches a manual count from the same run.

### Tests for User Story 3

- [X] T017 [P] [US3] Unit tests for the extended hit-rate aggregation in `backend/tests/unit/caching/test_hit_rate_report.py`: given a mix of `AssessmentEvent` rows with `moderation_served_from_cache` true/false across `FREE_TEXT_SUBMISSION_REJECTED` and `ANSWER_SUBMITTED`, the aggregation returns the correct moderation hit-rate percentage; given a mix of `TutorExchange` rows with varying `shielding_checks_total`/`shielding_checks_from_cache`, the aggregation returns the correct shielding hit-rate percentage (summed checks, not summed exchanges) (SC-001's per-type scoping)

### Implementation for User Story 3

- [X] T018 [US3] Extend `backend/scripts/cache_hit_rate_report.py`: add a `moderation` cache-type entry sourced from `FREE_TEXT_SUBMISSION_REJECTED`/`ANSWER_SUBMITTED` event payloads' `moderation_served_from_cache`/`moderation_cache_miss_reason` keys, and a `shielding` cache-type entry sourced from `tutor_exchanges.shielding_checks_total`/`shielding_checks_from_cache` summed over the window (research.md §8) (depends on T011, T016, T017 failing first)
- [X] T019 [US3] Implement `backend/scripts/guardrail_cache_load_test.py`: replay a synthetic, configurable-volume mix of duplicate-heavy answer-submission text (a small set of common blank/short/wrong strings repeated across many synthetic learners) and duplicate-heavy tutoring-chat (question, message) pairings against `get_or_check_moderation`/`get_or_classify_match` directly (no live server), once with caching enabled and once with a `--no-cache` flag bypassing the lookup entirely; report each cache type's hit rate (reusing T018's aggregation logic against in-memory `CacheOutcome` results, not a live DB query) and the model-call-volume delta between the two runs; exit non-zero if either cache type's hit rate is below 30% (SC-001/SC-002) (research.md §7) (depends on T009, T014, T018)

**Checkpoint**: quickstart.md Scenarios 4-5 pass -- the hit-rate report reflects real traffic, and the load test demonstrates SC-001/SC-002's per-type hit-rate and cost-reduction targets.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and the end-to-end checks that only make sense once every story above is done.

- [X] T020 [P] Run `backend/scripts/check_no_subject_conditionals.py`; confirm the two new cache modules introduce zero subject-id-keyed conditionals (Constitution Principle III)
- [X] T021 [P] Run `backend/scripts/check_deletion_cascade_coverage.py`; confirm it passes unchanged -- neither new table introduces a foreign key to `learner_profiles`/`real_guardian_accounts`/`real_instructor_accounts` (Constitution Principle VIII, spec.md FR-008)
- [X] T022 [P] Run Milestones 1-25's full `backend`, `grading-agent`, `tutor-agent`, and `frontend` test suites; confirm the same pass rate as immediately before this feature's changes, with particular attention to spec 007's and spec 016's existing acceptance-scenario tests (SC-005)
- [X] T023 Run `backend/scripts/guardrail_cache_load_test.py` (T019) against a live/dev environment; confirm each cache type independently reaches >=30% hit rate and model-call volume is measurably reduced vs. the `--no-cache` run (SC-001/SC-002) (depends on T019)
- [X] T024 Run `quickstart.md`'s full validation scenarios (1-6) end to end against a live/dev environment (depends on T010, T011, T015, T016, T018, T019, T020, T021, T023)
- [X] T025 Update `roadmap.md`'s status line for this feature to reflect implementation completion (depends on T024)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Not applicable -- see Phase 1 note above.
- **Foundational (Phase 2)**: No dependencies -- start immediately. BLOCKS all user stories.
- **User Story 1 (P1)**: Depends on Foundational only -- no dependency on US2 or US3.
- **User Story 2 (P2)**: Depends on Foundational only. Independent of US1 (uses `compute_paired_signature`/`CacheOutcome` from Foundational directly, not from US1's implementation).
- **User Story 3 (P3)**: T018 depends on T011 (US1) and T016 (US2), since it reads the payload/column fields both add. T019 (the load test) depends on T009 (US1) and T014 (US2) directly, plus T018's aggregation logic.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task.
- US1: T009 (cache lookup) before T010 (call-site wiring) before T011 (payload/trace).
- US2: T014 (cache lookup) before T015 (call-site wiring, per-check counting, and tracing) before T016 (persisting the counts T015 accumulated onto `TutorExchange`).
- US3: T018 depends on both US1's and US2's payload/column additions (T011, T016); T019 depends on T009, T014, and T018.

### Parallel Opportunities

- T002 and T003 (distinct model files) in parallel.
- T007 (US1 tests) in parallel with T012 (US2 tests) once Foundational is done.
- T020, T021, and T022 (distinct scopes) in parallel.

---

## Parallel Example: Foundational + User Story 1

```bash
# Launch both new models together:
Task: "Create ModerationCache model in backend/src/models/moderation_cache.py"
Task: "Create ShieldingClassificationCache model in backend/src/models/shielding_classification_cache.py"

# Once Foundational is done, start both stories' test files together:
Task: "Unit tests for moderation-cache lookup in backend/tests/unit/caching/test_moderation_cache.py"
Task: "Unit tests for shielding-cache lookup in backend/tests/unit/caching/test_shielding_cache.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational.
2. Complete Phase 3: User Story 1.
3. **STOP and VALIDATE**: quickstart.md Scenario 1 -- a repeated submission is served from cache with an identical verdict, and an instruction-version bump invalidates it.
4. This alone delivers the larger share of this feature's call-volume reduction (moderation runs 1:1 per submission; shielding's higher per-message call count is offset by lower cross-learner hit potential, plan.md's Summary) and is fully demonstrable on its own.

### Incremental Delivery

1. Foundational -> both tables, both signature helpers, and the `tutor_exchanges` columns exist.
2. Add User Story 1 -> test independently -> repeated moderation checks are served from cache (MVP).
3. Add User Story 2 -> test independently -> repeated shielding-match checks are served from cache.
4. Add User Story 3 -> test independently -> hit rate is measurable per cache type, and a synthetic load test demonstrates SC-001/SC-002's actual targets.
5. Polish -> Constitution-check scripts, full regression suite, live load-test confirmation, full quickstart run, roadmap status update.

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.

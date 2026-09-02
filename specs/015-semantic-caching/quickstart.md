# Quickstart: Validating Semantic Caching

**Feature**: `023-semantic-caching` | **Date**: 2026-09-02

These scenarios validate the feature end to end, once implemented,
without duplicating implementation detail already in `data-model.md` and
`research.md`.

## Prerequisites

- Repo checked out on this feature branch, `uv sync` run in `backend/`.
- `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` (or whatever `TUTOR_EMBEDDING_MODEL`'s
  provider needs) set locally -- scenarios 1 and 3's first request each
  need one real generation/grading call to seed the cache.
- `uv run alembic upgrade head` applied (creates `question_generation_cache`
  and `grading_response_cache`).

## Scenario 1 -- Second request for the same topic/difficulty is served from cache (US1, Acceptance Scenarios 1-2)

```bash
cd backend
uv run alembic upgrade head
# Trigger two next-question requests for the same (topic, difficulty)
# close together, e.g. two different learner_ids via the existing
# next-question API/integration test fixtures.
```

**Expected**: The first request calls the model and inserts a row into
`question_generation_cache`. The second request's served question/answer
key is byte-identical to a row already in that table (`SELECT * FROM
question_generation_cache ORDER BY created_at DESC LIMIT 1`), and the
corresponding `AssessmentEvent.payload->>'served_from_cache'` for the
second learner's `next_topic_selected` event is `"true"`.

## Scenario 2 -- Prompt-version or content-version bump invalidates the pool (US1, Acceptance Scenarios 3-4 / SC-004)

```sql
UPDATE question_generation_cache SET generation_prompt_version = 'stale-test'
WHERE cache_entry_id = '<the row from scenario 1>';
```

Trigger a third next-question request for the same (topic, difficulty).

**Expected**: The mutated row is never served (its `generation_prompt_version`
no longer matches the live `GENERATION_PROMPT_VERSION`); a fresh model
call happens instead, and a new row is inserted. `served_from_cache` is
`"false"` with `cache_miss_reason` = a version-mismatch reason.

## Scenario 3 -- Semantically similar free-text answers hit the grading cache (US2, Acceptance Scenarios 1-2)

```bash
# Submit a free-text answer to a free-text question via the existing
# answer-submission API/integration test fixtures, worded one way.
# Then submit a second, differently-worded but semantically equivalent
# answer to the SAME question (or a second learner's cached-pool copy
# of it from Scenario 1) as a different learner.
```

**Expected**: The second submission's grade and `criteria_met`/
`criteria_missed` match the first exactly, without a second Grading
Agent A2A call (confirm via `grading_response_cache`'s `hit_count`
incrementing, or by temporarily breaking `GRADING_AGENT_URL` and
confirming the second request still succeeds). The response returned to
the second learner never contains the first learner's answer text.

## Scenario 4 -- Grading cache does not cross questions or survive a prompt-version bump (US2, Acceptance Scenarios 3-4)

Submit a similar-sounding answer to a *different* question than
Scenario 3's. **Expected**: a fresh Grading Agent call, not a hit
(`question_signature` differs).

Bump `GRADING_LOGIC_VERSION` in `grading-agent/src/agent.py` on a
throwaway branch, resubmit Scenario 3's second answer. **Expected**: a
fresh Grading Agent call -- the pre-bump row is never served. Revert
afterward.

## Scenario 5 -- Cache-storage failure fails open (Edge Cases, FR-008)

On a throwaway branch, temporarily make the cache lookup query raise
(e.g. point it at a nonexistent column) and trigger a next-question or
grading request.

**Expected**: The request still succeeds via a direct model call
(no learner-visible error); the corresponding audit-log payload records
`cache_miss_reason` = a storage-failure reason. Revert afterward.

## Scenario 6 -- Every cache hit gets its own audit-log entry and Langfuse trace (FR-013, Clarifications 2026-09-02)

After Scenario 1's second (cache-hit) request:

```sql
SELECT payload->>'served_from_cache' FROM assessment_events
WHERE event_type = 'next_topic_selected' ORDER BY created_at DESC LIMIT 1;
```

**Expected**: `"true"`. Separately, check the configured Langfuse project
for a new trace/generation-shaped span for that request, tagged with
zero token usage and metadata identifying the original cache entry --
confirms the hit was traced as completely as a fresh call, not silently
skipped.

## Scenario 7 -- Hit-rate is measurable (US3, Acceptance Scenario 1)

```bash
cd backend
uv run python scripts/cache_hit_rate_report.py --since 1h
```

**Expected**: prints a hit-rate percentage broken out by cache type
(question-generation vs. grading), computed from `AssessmentEvent`
payloads recorded during this quickstart's scenarios.

## Scenario 8 -- Synthetic load test demonstrates SC-001/SC-002

```bash
cd backend
uv run python scripts/cache_load_test.py --requests 200
uv run python scripts/cache_load_test.py --requests 200 --no-cache
```

**Expected**: the first (cached) run reports a hit rate of at least 30%
for *each* cache type independently (question-generation and grading,
SC-001) and a measurably lower model-call count than the second
(`--no-cache`) run (SC-002). Non-zero exit code if either cache type's
hit rate falls below 30%.

## Scenario 9 -- Milestones 1-12 suites still pass (SC-005)

```bash
(cd backend && uv run pytest -q)
(cd grading-agent && uv run pytest -q)
(cd tutor-agent && uv run pytest -q)
(cd frontend && npm test)
```

**Expected**: same pass rate as immediately before this feature's
changes -- caching must not alter any existing behavior's output
(SC-003), only its cost/latency path.

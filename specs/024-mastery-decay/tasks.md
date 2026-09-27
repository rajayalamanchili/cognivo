---

description: "Task list for Spaced Repetition / Mastery Decay for Foundational Topics"
---

# Tasks: Spaced Repetition / Mastery Decay for Foundational Topics

**Input**: Design documents from `/specs/024-mastery-decay/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included per this project's established convention (every prior milestone's `plan.md` Testing row commits to `pytest` coverage) and because spec.md's SC-001/SC-002/SC-003/SC-004 explicitly require automated proof, not just a manual quickstart run.

**Organization**: Tasks are grouped by user story (spec.md's US1/US2, priority order) so each can be implemented and demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 or US2 -- Foundational/Polish tasks carry no story label

## Path Conventions

One existing tree touched: `backend/` (one new pure-function module, one modified module, four new test files). No new project, package, dependency, or service, per `plan.md`'s Project Structure. No `frontend/` change.

---

## Phase 1: Setup

**No new setup required.** This feature introduces no new dependency, package, or service (plan.md's Technical Context) -- Python 3.12 and SQLAlchemy 2.0 are already installed and already wired. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The decay primitive both user stories build on. Nothing subject- or story-specific -- a standalone pure module, same relationship `bkt.py` already has to the rest of the mastery model.

- [ ] T001 [P] Create `backend/src/services/mastery/decay.py`: module-level constants `GRACE_PERIOD = datetime.timedelta(days=21)` and `HALF_LIFE = datetime.timedelta(days=45)`, and a pure function `effective_mastery_for_review(p_mastery: float, *, updated_at: datetime.datetime, now: datetime.datetime) -> float` implementing data-model.md's formula (no decay within `GRACE_PERIOD`; otherwise `p_mastery * 0.5 ** (elapsed_after_grace / HALF_LIFE)`). Mirror `backend/src/services/mastery/bkt.py`'s module docstring style (cite research.md §1, Constitution Principle I/VIII) and its `import datetime` / `datetime.datetime.now(datetime.UTC)` convention already used in `backend/src/services/quiz/session.py`.
- [ ] T002 Create `backend/tests/unit/test_mastery_decay.py` (depends on T001): `test_within_grace_period_returns_raw_p_mastery` (elapsed <= 21 days -> unchanged), `test_past_grace_period_applies_exponential_decay` (exact expected value at a chosen elapsed time, e.g. `GRACE_PERIOD + HALF_LIFE` -> `p_mastery * 0.5`), `test_decay_approaches_but_never_reaches_zero` (several half-lives out -> small positive value, never exactly `0.0`), `test_deterministic_given_identical_inputs` (same `p_mastery`/`updated_at`/`now` called twice -> identical output, FR-010). Mirrors `tests/unit/test_mastery_bkt.py`'s structure (research.md §5 item 1).

**Checkpoint**: Decay primitive is proven correct in isolation. Ready to wire into ranking.

---

## Phase 3: User Story 1 - A long-untouched mastered topic is reviewed before a recently-mastered one (Priority: P1) 🎯 MVP

**Goal**: `rank_eligible_topics`'s existing mastered-topic fallback ranks by decayed effective mastery instead of raw `p_mastery`, and `select_next_topic`/`preview_topic_priority` supply it with the real data to do so.

**Independent Test**: Seed two mastered `MasteryState` rows with similar `p_mastery` but very different `updated_at` timestamps, exhaust all other eligible topics, and confirm the Sequencing Agent's mastered-topic fallback selects the more time-decayed one first (quickstart.md Scenario 1).

### Tests for User Story 1 ⚠️

> Write these first; both must fail before Phase 3's implementation tasks and pass after.

- [ ] T003 [P] [US1] Create `backend/tests/unit/test_topic_priority_decay.py`: pure-function tests calling `rank_eligible_topics` directly (no DB) with `updated_at_by_topic`/`now` supplied -- two mastered topics with equal raw `p_mastery` and very different `updated_at` sort with the more-decayed one first; a mastered topic within `GRACE_PERIOD` sorts identically whether or not `updated_at_by_topic`/`now` are supplied at all (proves the "no behavior change within grace period" half of SC-002 at the pure-function level); an eligible (non-mastered) topic's position is unaffected regardless of any `updated_at`/`now` values passed for a mastered topic outside its pool; two mastered topics whose `p_mastery`/`updated_at` are chosen so their effective mastery ties exactly still resolve via the existing `order_index` tie-break (spec.md Edge Case #1, FR-012). Mirrors `tests/unit/test_sequencing.py`'s grade-gate convention (research.md §5 item 2).
- [ ] T004 [P] [US1] Create `backend/tests/integration/test_next_topic_decay_fallback.py`: real-DB test seeding two mastered `MasteryState` rows with equal `p_mastery` on a subject/content fixture where both topics' prerequisites are otherwise exhausted (forcing the fallback branch), one row's `updated_at` backdated past `GRACE_PERIOD + HALF_LIFE`; asserts `select_next_topic` returns the backdated topic, `is_fallback=True`, that `selection.p_mastery` equals that topic's **raw**, pre-backdate `p_mastery` exactly rather than any decayed number (FR-005 -- the displayed value never reflects decay, only the ordering does), and that calling it twice with the same DB state produces the identical selection (SC-004). Mirrors `tests/integration/test_next_topic_fallback.py`'s existing setup convention (research.md §5 item 3, quickstart.md Scenario 1).

### Implementation for User Story 1

- [ ] T005 [US1] Modify `rank_eligible_topics` in `backend/src/agents/sequencing/agent.py` (depends on T001): add two optional keyword arguments, `updated_at_by_topic: dict[str, datetime.datetime] | None = None` and `now: datetime.datetime | None = None`. Add a small helper (e.g. `_effective_p_mastery_for_ranking`) that returns `p_mastery_by_topic[t]` unchanged unless `band_by_topic[t] == "mastered"` and both new arguments are provided and `updated_at_by_topic` has an entry for `t`, in which case it returns `decay.effective_mastery_for_review(p_mastery_by_topic[t], updated_at=updated_at_by_topic[t], now=now)`. Change the existing `ranked = sorted(pool, key=lambda t: _sort_key(p_mastery_by_topic[t], order_index_by_topic[t]))` line to call this helper instead of indexing `p_mastery_by_topic` directly. Per research.md §2, this single change point is a no-op for the `eligible` pool (which structurally excludes `"mastered"` topics via `_ELIGIBLE_BANDS`) and for the zero-mastered-topics full-fallback pool, so no branch is needed.
- [ ] T006 [US1] Modify `_TopicRankingContext` and `_load_topic_ranking_context` in `backend/src/agents/sequencing/agent.py` (depends on T005, same file): add an `updated_at_by_topic: dict[str, datetime.datetime]` field to the dataclass, populated from the same `MasteryState` query `_load_topic_ranking_context` already runs (`{state.topic_id: state.updated_at for state in ...}` alongside the existing `mastery_by_topic` dict) -- no new query.
- [ ] T007 [US1] Modify `select_next_topic` and `preview_topic_priority` in `backend/src/agents/sequencing/agent.py` (depends on T006): each captures `now = datetime.datetime.now(datetime.UTC)` once, locally, and passes `updated_at_by_topic=ctx.updated_at_by_topic, now=now` into its `rank_eligible_topics(...)` call (research.md §3, FR-010's "one evaluation timestamp per call").

**Checkpoint**: User Story 1 is fully functional and independently testable -- T003/T004 pass, and quickstart.md Scenario 1 is verifiable end to end against a real dev database.

---

## Phase 4: User Story 2 - Answering a decayed topic updates mastery exactly like any other answer (Priority: P2)

**Goal**: Prove that a decayed topic's answer flows through the existing, unmodified `apply_mastery_update`/`apply_bkt_update` path with zero special-casing.

**Independent Test**: Answer a question on a decayed mastered topic and confirm the resulting `MasteryState.p_mastery` matches what `apply_bkt_update` would produce from the last-persisted (undecayed) prior -- identical to answering a topic with zero elapsed time (quickstart.md Scenario 2).

**No implementation task**: per data-model.md, `apply_mastery_update` (`backend/src/agents/sequencing/mastery_tool.py`) already only ever reads `existing.p_mastery` -- the raw, persisted value -- as the BKT prior. Phase 3 adds no call from anywhere in the answer-submission path into `decay.py`. FR-002/FR-011 hold with zero changes to this file; this story is a regression-proof test only.

### Tests for User Story 2 ⚠️

- [ ] T008 [US2] Create `backend/tests/integration/test_decayed_topic_answer_unaffected.py` (depends on T005-T007; independently seeds its own equivalent of T004's backdated-`MasteryState` scenario rather than importing a shared fixture, matching this repo's existing convention of each integration test file being self-contained -- e.g. `test_next_topic_fallback.py` and `test_next_topic_eligibility.py` don't share fixtures either): after the Sequencing Agent selects the decayed topic, generate and answer a real question on it; assert the answer response's `prior_p_mastery` equals the topic's raw, pre-backdate `p_mastery` exactly (never a decayed number), `posterior_p_mastery` equals what `apply_bkt_update` produces from that same raw prior and the given correctness/question type (calling the pure function directly in the test for the expected value, not duplicating its formula), and that `MasteryState.updated_at` refreshes to the time of this new answer (decay restarts). Confirms SC-003 and quickstart.md Scenario 2.

**Checkpoint**: Both user stories are independently functional. `apply_mastery_update`/`apply_bkt_update` are verified unaffected by reading the actual code path (data-model.md), not assumed from the plan's claim alone -- same discipline Milestone 21 applied to its own "grading is unchanged" claim.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verification that this feature is byte-identical everywhere it claims to be, and that nothing else regressed.

- [ ] T009 [P] Run `cd backend && uv run alembic check` -- confirms zero schema drift (no migration ships with this feature, per plan.md/data-model.md).
- [ ] T010 [P] Run `cd backend && python scripts/check_no_subject_conditionals.py` -- confirms no subject-specific conditional was introduced (trivially true here, but verified rather than assumed, per Constitution Principle III).
- [ ] T011 Run the full backend regression suite (`cd backend && uv run pytest`) as the final, unfiltered check (per this project's "full suite at end only" convention) -- confirms SC-002's "zero change to any existing mastery, sequencing, dashboard, or recommendation-agent behavior" across the entire suite, not just the four new test files.
- [ ] T012 Manually run quickstart.md's Scenario 1 and Scenario 2 against a real dev database (direct SQL backdating of `mastery_states.updated_at`, since the 21+45-day window can't be waited out) -- confirms the automated tests' claims hold against the real API routes and a real Postgres database, not only against test fixtures.
- [ ] T013 Update `roadmap.md`'s Milestone 22 entry with the actual shipped state (test counts, any bugs found during T009-T012, PR number once opened) -- per this project's own convention, checked before every spec-kit commit, of keeping the roadmap's Definition of Done record accurate rather than aspirational.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None -- skipped, no tasks.
- **Foundational (Phase 2)**: No dependencies -- can start immediately. BLOCKS User Story 1 (T005 needs `decay.py` to exist).
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) completion.
- **User Story 2 (Phase 4)**: Depends on User Story 1 (Phase 3) completion -- T008 needs T005-T007's fallback-ranking change to actually be able to select a decayed topic for the learner to answer, even though it independently seeds its own scenario rather than importing T004's. (Unlike most story pairs in this project, US2 is not independently startable before US1 -- spec.md's own priority ordering already reflects this: US2's Independent Test presupposes a decayed topic exists to answer.)
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Within Each User Story

- Tests (T003/T004, T008) are written first and must fail before their corresponding implementation lands.
- T005 → T006 → T007 are sequential (same file, each building on the last).

### Parallel Opportunities

- T001 has no dependency and can start immediately.
- T003 and T004 can be written in parallel (different files) once T001 exists, though both will fail until T005-T007 land.
- T009 and T010 can run in parallel with each other (independent scripts).

---

## Parallel Example: Foundational + User Story 1 test-writing

```bash
# After T001 (decay.py) exists, write both test files in parallel:
Task: "Create backend/tests/unit/test_topic_priority_decay.py"
Task: "Create backend/tests/integration/test_next_topic_decay_fallback.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (`decay.py` + its unit test).
2. Complete Phase 3: User Story 1 (the actual ranking change).
3. **STOP and VALIDATE**: quickstart.md Scenario 1 against a real dev DB.
4. This alone is a demoable increment: a long-untouched mastered topic now gets reviewed first.

### Incremental Delivery

1. Foundational → decay primitive proven correct in isolation.
2. User Story 1 → the fallback pool actually re-ranks by decay. MVP.
3. User Story 2 → proof (not new behavior) that answering a decayed topic is unaffected.
4. Polish → full-suite regression proof, drift/subject-conditional checks, roadmap.md update.

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- [Story] label maps task to specific user story for traceability.
- Commit after each phase (Foundational, US1, US2, Polish) rather than after every individual task, matching this project's "bundle PR at end of a task batch" convention -- one PR once Polish is done.
- No `frontend/` task exists anywhere in this list: this feature has zero frontend surface (plan.md's Technical Context).

# Research: Spaced Repetition / Mastery Decay for Foundational Topics

## §1. Decay mechanism, curve shape, and where it's computed

**Decision**: A new pure function,
`effective_mastery_for_review(p_mastery, updated_at, now)`, in a new
`backend/src/services/mastery/decay.py`. It returns `p_mastery`
unchanged while `now - updated_at <= GRACE_PERIOD`, and otherwise
returns `p_mastery * 0.5 ** (elapsed_after_grace / HALF_LIFE)` where
`elapsed_after_grace = (now - updated_at) - GRACE_PERIOD` -- a
standard exponential ("Ebbinghaus-style forgetting curve") decay,
computed at read time only, never persisted. Fixed global constants:

```python
GRACE_PERIOD = datetime.timedelta(days=21)
HALF_LIFE = datetime.timedelta(days=45)
```

**Rationale**: FR-009 requires fixed, non-per-topic/per-learner
constants -- exactly the same constraint `bkt.py`'s `P_L0`/`P_T`/`P_S`/
`P_G_*` are already under, for the identical reason (Constitution
Principle VIII: no real learner data exists yet to fit against). A
21-day grace period matches this project's own precedent for "a normal
gap between sessions shouldn't trigger review pressure" reasoning
already used for the practice-session/quiz cadence in Milestones 5/20,
scaled to a multi-week span since mastery decay is a slower-moving
signal than an in-session timer. A 45-day half-life means a topic that
sits completely untouched for roughly a month and a half past the
grace period decays to half its mastery value for ranking purposes --
enough to reliably outrank a topic mastered last week, without being so
aggressive that ordinary multi-week gaps between topics dominate the
fallback pool. Both values are explicitly placeholders pending real
learner data (spec.md Assumptions) -- there is no way to fit them
correctly before Milestone 7's real learner data exists, and FR-009
requires them to be *some* fixed deterministic pair, not a precisely
"correct" one yet.

Computing this at read time (inside the same request that already
calls `rank_eligible_topics`) rather than via a background job matches
Constitution Principle IX (no persistent process on Vercel) and this
project's own established precedent: Milestone 20's timed-session
expiry check (`expires_at = started_at + time_limit_seconds`, evaluated
lazily on the next request that touches the session, `research.md` §1
of that spec) is the exact same shape -- a deterministic function of a
stored timestamp and "now," evaluated on demand, never a scheduled
recomputation.

**Alternatives considered**:
- *A scheduled job (Vercel Cron) that periodically recomputes and
  stores a decayed value*: rejected. This is exactly the "invent a
  separate scheduler" the feature description explicitly asked to
  avoid unless research showed the read-time approach wasn't viable --
  and it is viable, since the only consumer of the decayed value
  (`rank_eligible_topics`'s fallback branch) already runs inside a
  request. A cron job would also mean *persisting* a decayed value,
  reintroducing the exact "does decay overwrite the evidence-based
  estimate" risk FR-002 exists to rule out.
- *Linear decay* (`p_mastery - rate * elapsed`) instead of exponential:
  rejected -- it eventually goes negative without an explicit floor,
  requiring a `max(0.0, ...)` clamp that an asymptotic curve doesn't
  need, and exponential/Ebbinghaus-style decay is the standard shape
  for a forgetting curve in the spaced-repetition literature this
  feature is explicitly named after.
- *A step function* (drop one full mastery band after N days): rejected
  by the earlier scope decision itself (resolved with the user before
  drafting spec.md) -- decay must never change a topic's band, only its
  ranking within the existing fallback pool, so a step function's
  natural unit (a band) doesn't fit this feature's chosen effect
  surface at all.

## §2. Where the decayed sort key is wired in

**Decision**: `rank_eligible_topics` (`backend/src/agents/sequencing/
agent.py`) gains two new optional keyword arguments,
`updated_at_by_topic: dict[str, datetime.datetime] | None = None` and
`now: datetime.datetime | None = None`, defaulting to `None`. The
existing `ranked = sorted(pool, key=lambda t: _sort_key(p_mastery_by_
topic[t], ...))` line changes to look up an *effective* mastery per
topic instead of the raw dict directly, via a small helper that returns
`p_mastery_by_topic[t]` unchanged whenever `band_by_topic[t] !=
"mastered"`, or either kwarg is `None`, or `updated_at_by_topic` has no
entry for that topic.

**Rationale**: This single change point covers all three pools
(`eligible`, `mastered`, and the "zero mastered topics" full fallback)
without a branch, because it only ever changes behavior for a topic
whose band is `"mastered"` -- and the `eligible` pool is defined as
`band_by_topic[t] in _ELIGIBLE_BANDS`, a frozenset that already
excludes `"mastered"` entirely (`_ELIGIBLE_BANDS = frozenset({"unknown",
"struggling", "developing"})`). So FR-004 (eligible-pool ranking
unaffected) and the "full fallback when zero topics are mastered"
case (nothing in that pool is `"mastered"` either, by definition of how
it's reached) both hold *by construction*, matching this file's own
existing docstring aesthetic ("holds by construction rather than by
convention") rather than needing a second code path to maintain. Making
both new kwargs optional and default to `None` (rather than required)
follows the exact precedent spec 017 already set on this same function
for `grade_by_topic`/`unlocked_grade`: every one of the five existing
test files that call `rank_eligible_topics` directly (`test_sequencing.
py`, `test_topic_priority_ranking.py`, and three integration tests)
needs zero changes, because omitting the new kwargs reproduces today's
exact behavior -- this is how SC-002's "zero regression" is verified by
construction, not only by re-running the suite.

**Alternatives considered**:
- *A separate `rank_mastered_fallback_topics` function*, called only
  from the `else` branch: rejected -- it would duplicate the sort/tie-
  break logic (`_sort_key`, `order_index_by_topic`) that already exists
  once in this function, for no benefit over a lookup that's already a
  no-op outside the mastered branch.
- *Making `now`/`updated_at_by_topic` required, not optional*: rejected
  -- would force every existing test and caller to pass them even when
  irrelevant (e.g. `test_sequencing.py`'s grade-gate tests, which never
  touch a mastered topic), for a feature spec 017 already showed how to
  add without that churn.

## §3. Caller wiring: `_load_topic_ranking_context`, `select_next_topic`, `preview_topic_priority`

**Decision**: `_load_topic_ranking_context` gains one new field on its
return dataclass, `updated_at_by_topic: dict[str, datetime.datetime]`,
populated from the exact same `MasteryState` query it already runs (no
new query -- `updated_at` is already a column on the row it already
fetches). `select_next_topic` and `preview_topic_priority` each capture
`now = datetime.datetime.now(datetime.UTC)` once, locally, and pass
`updated_at_by_topic=ctx.updated_at_by_topic, now=now` into their
`rank_eligible_topics` call.

**Rationale**: FR-010 requires one consistently captured evaluation
timestamp per ranking/selection call, not a fresh `datetime.now()` read
per topic compared against each other -- capturing it once at the top
of each of these two functions (which are each "one call" from spec.
md's perspective) satisfies that directly, and mirrors the exact
pattern `backend/src/services/quiz/session.py` already uses (`now =
datetime.datetime.now(datetime.UTC)` captured once per function, reused
for every comparison inside it) rather than inventing a new timestamp-
capture convention.

**Alternatives considered**:
- *Passing `now` in from each endpoint caller instead of capturing it
  inside `select_next_topic`/`preview_topic_priority`*: rejected --
  neither of this function's two real callers (the next-question API
  route, the topic-priority-preview API route) has any other reason to
  know the current time; threading it through an extra layer for no
  behavioral difference (both would just call `datetime.now(UTC)`
  immediately before the same function call) adds a parameter with no
  real caller-side flexibility need.

## §4. No new API contract, no schema change, no frontend change

**Decision**: No `contracts/` directory (mirrors Milestone 19's
schema-drift-check precedent for a feature with no API/UI surface of
its own). `GET /api/.../topic-priority-preview`
(`backend/src/api/routes/sequencing_preview.py`, response model
`TopicPreviewEntryOut`) and the next-question route's response shape
are both unchanged -- `TopicPreviewEntryOut.p_mastery` is still sourced
from `ctx.p_mastery_by_topic` (the raw dict), never the decayed value,
matching FR-005. Only the *order* `rank_eligible_topics` returns for
its mastered-fallback branch changes. No new `AssessmentEventType`, no
new column, no Alembic migration.

**Rationale**: Directly required by FR-005 (band/displayed-mastery
stays raw everywhere outside the Sequencing Agent's own fallback
ranking) and the spec's Assumptions (no dashboard, weak-area-report, or
prerequisite-gating change). Verified by reading `sequencing_preview.
py`'s `to_entry`/`TopicPreviewEntryOut` construction directly, not
assumed from the spec's claim alone -- the same "read the actual code
path, don't rely on the plan's claim" discipline Milestone 21 applied
to its own "grading is unchanged" claim.

## §5. Testing strategy

**Decision**: Four new test files, no changes to any existing test
file:
1. `backend/tests/unit/test_mastery_decay.py` -- pure-function coverage
   of `effective_mastery_for_review`: within grace period (no decay),
   just past grace period (near-`p_mastery`), several half-lives out
   (approaches but never reaches zero), and a determinism check (same
   inputs, repeated calls, identical output).
2. `backend/tests/unit/test_topic_priority_decay.py` -- `rank_eligible_
   topics` with `updated_at_by_topic`/`now` supplied: two mastered
   topics with equal raw `p_mastery` and different `updated_at`s sort
   with the more-decayed one first; a mastered topic within the grace
   period sorts identically to omitting the new kwargs entirely (proves
   the "no behavior change within grace period" half of SC-002 at the
   pure-function level); the eligible pool's ordering is provably
   unaffected by an extreme `updated_at`/`now` gap on a mastered topic
   that isn't even in that pool; two mastered topics whose effective
   mastery ties exactly still resolve via the existing `order_index`
   tie-break (spec.md Edge Case #1, FR-012).
3. `backend/tests/integration/test_next_topic_decay_fallback.py` --
   real-DB proof: two mastered `MasteryState` rows with equal
   `p_mastery`, one row's `updated_at` backdated well past
   `GRACE_PERIOD + HALF_LIFE`, both topics' prerequisites otherwise
   exhausted (forcing the fallback branch); `select_next_topic` returns
   the backdated topic, and its returned `p_mastery` is the raw,
   undecayed value (FR-005), not the decayed one used only for sorting.
4. `backend/tests/integration/test_decayed_topic_answer_unaffected.py`
   -- real-DB proof for US2: after the fallback selects a decayed
   topic, answering it produces a `prior_p_mastery`/`posterior_p_
   mastery` pair identical to what `apply_bkt_update` would produce
   from the raw, undecayed prior -- confirming FR-011/SC-003 against
   the real answer-submission path, not just by reading the code.

**Rationale**: Mirrors this codebase's existing three-tier convention
for a ranking-rule change (pure-function unit test for the new
primitive, pure-function unit test for the ranking function itself,
DB-backed integration test(s) proving the real call path) -- the exact
same shape spec 017's grade-gate feature used
(`test_mastery_bkt.py`-style module test → `test_sequencing.py`-style
ranking test → `test_next_topic_eligibility.py`/`test_next_topic_
fallback.py`-style integration test). Item 4 adds a second integration-
tier file rather than folding into item 3, matching this project's
existing per-story test-file convention (e.g. spec 017's own
`test_next_topic_eligibility.py` vs. `test_next_topic_fallback.py` stay
separate files despite both being integration tests of the same
function) rather than merging two user stories' proofs into one file.

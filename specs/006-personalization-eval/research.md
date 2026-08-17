# Research: Real Personalization Signal -- Sequencing Evaluation Harness

**Feature**: `006-personalization-eval` | **Date**: 2026-08-16

Resolves every open implementation question the spec deliberately deferred
to `plan.md`, plus two corrections discovered while reading the actual
Sequencing Agent code (recorded as decisions, not new user-facing
ambiguities -- see each rationale below).

## 1. What "the Sequencing Agent's real code path" actually means

**Decision**: The harness calls `select_next_topic(db, learner_id, subject_id)`
(`backend/src/agents/sequencing/agent.py`) directly -- the pure,
deterministic, DB-query-driven topic-selection function -- and never calls
`generate_next_question` (which additionally invokes the LLM-backed
Assessment-Generation Agent to produce question text).

**Rationale**: FR-002 already establishes that simulated answer
correctness is drawn from the locked BKT emission model given a learner's
ground-truth mastery, not from grading a real generated question. FR-003
also scopes the comparison to "next-topic selection," not question
generation. `select_next_topic` is exactly the unit under test; nothing
about the comparison requires paying for an LLM call per simulated
question. This keeps a population of hundreds of simulated learners cheap
and fast to run (no LLM cost/latency in the loop at all), which is also
what makes the single-seed-with-adequate-population methodology
(Clarifications) practical to run repeatedly.

**Alternatives considered**: Calling `generate_next_question` end-to-end
for full fidelity -- rejected; it would make every simulated question an
LLM call, at a cost/latency that actively fights the "large enough
population that per-answer noise doesn't flip the result" requirement
from Clarifications, for no gain in what's being measured (ordering
quality, not question-generation quality, which Milestone 1 already
covers).

## 2. Correcting FR-008/SC-004's tracing claim

**Discovery**: `select_next_topic` makes no ADK/LLM call, so it emits no
Langfuse span even in production -- tracing (`traced_request()` in
`questions.py`) wraps the *combination* of topic selection and LLM
question generation, not topic selection alone. This matches an existing,
already-locked precedent: `recommendation.py`'s `build_weak_area_report`
and the `GET /mastery-state` route are both explicitly documented as
untraced for the same reason (no LLM/ADK invocation to instrument).

**Decision**: `spec.md`'s FR-008 and SC-004 were corrected (during this
planning pass) to require code-path fidelity -- the harness calls the real
`select_next_topic` function, never a reimplementation -- rather than
asserting a Langfuse trace that was never going to exist for this
function even in production. This is a factual correction of the spec's
own drafting mistake, not a new product decision, so it did not need a
fresh `/speckit-clarify` round.

**Rationale**: Carrying a requirement into `tasks.md` that's unsatisfiable
by construction (no code path here calls the LLM, so nothing will ever
produce the trace SC-004 originally demanded) would either block
implementation or force a fake/contrived trace just to satisfy the letter
of a wrong requirement -- worse than fixing the spec now.

## 3. Ground-truth mastery generative model

**Decision**: A Synthetic Learner Profile defines, per topic, a
probability that a simulated learner in that profile *truly knows* that
topic. At population-generation time (seeded RNG, FR-007), each simulated
learner's ground-truth mastery per topic is drawn once as a **boolean**
latent state (`True` = truly mastered, `False` = not) via that
probability -- not as a continuous value. This state is fixed for the
learner's entire simulated run across all three conditions (each
condition re-plays the *same* underlying learners and ground truth, only
the question order differs -- this is what makes the three conditions
comparable at all).

Each simulated answer for a topic is then an independent Bernoulli draw
using the existing locked emission parameters
(`src/services/mastery/bkt.py`): `P(correct) = 1 - P_S` if the topic's
latent state is `True`, `P(correct) = guess_probability(question_type)`
if `False`. `question_type` per topic comes from the same
`preferred_question_type(topic)` helper the real pipeline already uses
(`src.agents.diagnostic.agent`), so guess probability is picked exactly
as production would.

**Rationale**: This is the same generative assumption BKT itself is built
on (a binary latent mastery state observed through slip/guess noise), so
"can the Sequencing Agent's estimate reach ~ the true state faster" is a
coherent, well-posed question. A continuous ground-truth probability
would have no clean way to generate a single answer's correctness without
implicitly picking this same binary-draw mechanism anyway.

**Alternatives considered**: Treating ground-truth mastery as a
continuous probability used directly as `P(correct)` per answer (skipping
slip/guess) -- rejected; it would silently test a different, easier
emission model than the one the real Sequencing Agent's BKT tool assumes,
undermining the comparison's validity.

## 4. Random and fixed-order baseline mechanics

**Decision**:
- **Random baseline**: each question, pick uniformly at random from all
  topics in the subject (seeded RNG), independent of any mastery state --
  the "no personalization at all" baseline.
- **Fixed-order baseline**: topics are visited in ascending `order_index`.
  The harness asks about the current topic repeatedly until it reaches
  the "mastered" band (see §5), then advances to the next topic by
  `order_index`. After one full pass, if any topics remain unmastered
  (e.g. a later topic's questions came before its prerequisite was ready),
  the harness cycles through the remaining unmastered topics again in
  `order_index` order until the budget is exhausted.

**Rationale**: These are the simplest, most defensible operationalizations
of "no ordering intelligence" and "a fixed curriculum order" respectively
-- neither uses the mastery model to choose what to ask next, which is
exactly the contrast the comparison needs against the Sequencing Agent
condition (which does).

## 5. "Reaches target mastery" = the real `mastered` band, confirmation streak included

**Discovery**: The existing "mastered" band is not simply `p_mastery >=
0.7` -- `mastery_band_for()` (`src/models/enums.py`) additionally requires
`consecutive_mastered_observations >= MASTERY_CONFIRMATION_THRESHOLD` (2),
specifically to prevent one lucky guess from counting as mastery
(Milestone 1's SC-005 anti-degenerate-answer-pattern requirement).

**Decision**: The harness's convergence check calls the same
`mastery_band_for(p_mastery, consecutive_mastered_observations)` function
(not a re-derivation of the 0.7 cutoff) to decide "has this topic reached
the mastered band yet." This is what `spec.md`'s "the existing mastered
band" language already meant; this note makes the exact mechanics
explicit for `tasks.md`.

**Rationale**: Using a simplified `p_mastery >= 0.7` check instead would
silently test a more lenient bar than the one the real product actually
uses to decide a topic is done -- undermining SC-001's claim.

## 6. Where synthetic learners live, and why

**Discovery**: `MasteryState.learner_id` has a foreign-key constraint to
`demo_learner_profiles.learner_id`. Since the Sequencing Agent condition
must call the real `select_next_topic`, which reads `MasteryState` from
Postgres by `learner_id`, synthetic learners for that condition must be
real rows in `demo_learner_profiles`.

**Decision**: Each synthetic learner used in the Sequencing Agent
condition is seeded as a `DemoLearnerProfile` row with `is_demo=True`
(Constitution Principle VIII -- no inferred flag) and a `display_name`
prefixed `eval-harness-` for identifiability, plus real `MasteryState`
rows updated via the same `apply_bkt_update` function production uses.
**The random and fixed-order baseline conditions run entirely in-memory**
(no DB writes) since they never call `select_next_topic` and have no
other requirement to touch the database -- only the Sequencing Agent
condition needs real persisted rows to exercise the real code path.

All rows the harness creates (including the `AssessmentEvent` rows from
§7 below) are deleted at the end of a run (success or failure), so
repeated manual runs (per Clarifications' manual-publish decision) don't
accumulate cruft in whatever database the harness is pointed at. The
harness is intended to be run against a local/dev database, not
`staging`/production -- it is a manually-invoked script, not part of any
deploy pipeline.

**Rationale**: Reusing the exact same `apply_bkt_update`/`MasteryState`
machinery production uses (rather than a parallel in-memory-only mastery
tracker for every condition) keeps the Sequencing Agent condition
provably not a reimplementation (FR-008/SC-004), while keeping the two
baseline conditions cheap and side-effect-free since code-path fidelity
was never required for them.

## 7. Audit-log (AssessmentEvent) scope

**Revised decision** (post-`/speckit-analyze`, finding C1): The harness
**does** write real `AssessmentEvent` rows (reusing the existing
`NEXT_TOPIC_SELECTED` type, same payload shape `questions.py` already
writes) for the **Sequencing Agent condition's** decisions only. Random
and fixed-order conditions still write none, because they never touch
the database at all (§6) -- they have no `learner_id` row to attach an
`AssessmentEvent` to, and they aren't real agent decisions in Principle
I's sense (they're deliberately non-personalized baselines), so there is
nothing for Principle V's "why was this decision made" question to be
asked *of* in the first place.

This corrects an earlier version of this decision that proposed skipping
`AssessmentEvent` writes entirely for the Sequencing Agent condition too,
justified by narrowing Principle V's "every sequencing decision... MUST
be logged" to only real (non-synthetic) learners. `/speckit-analyze`
flagged that as an unauthorized reinterpretation of a MUST clause rather
than a legitimate deviation -- the constitution's own process requires
either full compliance or an explicit, separate constitution amendment,
not a plausible-sounding scope narrowing embedded in a plan's Complexity
Tracking table.

**Rationale**: The Sequencing Agent condition already writes real
`MasteryState`/`DemoLearnerProfile` rows to the same database production
uses (§6) -- adding `AssessmentEvent` rows for that one condition is
additive to a DB surface already in use, not a new one, and is bounded to
1 of 3 conditions (up to ~38,400 rows for a full Evaluation Run at this
milestone's population/budget sizing, not the ~10^5 the original,
rejected all-conditions estimate assumed). All of it is deleted at run
end alongside the `MasteryState`/`DemoLearnerProfile` rows (§6), so there
is no permanent audit-log bloat from synthetic data, keeping this
consistent with Principle VIII's synthetic-data hygiene while still
satisfying Principle V's literal requirement for the one condition that
actually exercises a real personalization decision.

## 8. Report publication mechanism

**Decision**: The harness writes one self-describing JSON file (a
`ComparisonReport`, including `run_timestamp`, `seed`, and the
profiles/subjects covered -- satisfying FR-013 without a separate log
table) to `backend/evaluation/reports/latest.json`. An engineer commits
this file when they choose to publish a new run (Clarifications:
manual/on-demand). A new `GET /api/evaluation/report` FastAPI route reads
this file at request time and returns its contents (or a "not yet
published" shape if the file doesn't exist), matching the existing
API-route-per-concern pattern (`mastery.py`, `recommendation.py`, etc.).

**Rationale**: Consistent with `tech-stack.md`'s content-schema pattern
("bundled with the deployed function... avoids relying on local
filesystem writes, which are not reliably persistent across serverless
invocations") -- the file is committed to the repo and deployed read-only
with the function, never written at request time. No new database table
or migration needed.

**Alternatives considered**: A new Postgres table for published runs --
rejected; adds a migration and write path for a value that changes only
when an engineer manually decides to publish, which a committed file
already models faithfully and more simply, per Constitution Principle IX
(no state assumed to persist beyond what's explicitly persisted).

## 9. Report page location and navigation

**Decision**: `frontend/src/app/personalization-eval/page.tsx`, fetching
from the new backend route via a new `frontend/src/services/api.ts`
function. A minimal navigation element is added to
`frontend/src/app/layout.tsx` (which currently renders only `DemoBadge`
with no nav at all) linking to this page and the existing
placement/practice/mastery pages, per the Clarifications' main-navigation
decision.

**Rationale**: Matches the existing per-page route + shared `api.ts`
client pattern already used by `practice`, `mastery`, and `placement`.
Adding minimal nav is the smallest change that satisfies "linked from
main navigation" -- no nav component exists yet to reuse.

**Implementation note for `/speckit-implement`**: `frontend/AGENTS.md`
flags that this project's `next` package has breaking changes from
training-data Next.js; read `node_modules/next/dist/docs/` before writing
the new route/page.

## 10. Synthetic learner profiles and scale parameters

**Decision**: Four profiles, each an archetype of per-topic
true-mastery probability:

| Profile | Per-topic true-mastery probability | Purpose |
|---|---|---|
| `cold-start` | Uniform(0.05, 0.25) for every topic | Baseline: learner starts knowing almost nothing anywhere |
| `strong-prior` | Uniform(0.6, 0.9) for every topic | Tests that Sequencing Agent doesn't waste questions re-asking already-known topics |
| `uneven` | Alternating Uniform(0.7, 0.9) / Uniform(0.05, 0.2) by `order_index` parity | Tests targeting of real weak spots amid known ones |
| `prerequisite-bottleneck` | Early-`order_index` topics Uniform(0.05, 0.2), later topics Uniform(0.6, 0.9) | Tests prerequisite-aware navigation specifically (does the agent get stuck less than baselines when later "known" topics are gated behind unmastered early ones) |

30 simulated learners per profile, per subject, per condition (4 profiles
x 2 subjects x 3 conditions x 30 = 720 simulated learner runs per
Evaluation Run). Maximum-question budget: 20 questions per topic (160 per
subject's 8-topic run) before a learner/condition/topic-set is recorded
as non-converged.

**Rationale**: 30 learners per profile is enough that a handful of
unlucky slip/guess draws (P_S=0.1, P_G up to 0.25) average out in the
mean/median without needing multi-seed repetition (Clarifications). 20
questions/topic is generous headroom above BKT's typical convergence
speed at these parameters (empirically converges within ~5-10 questions
per topic starting from `P_L0=0.3`), so budget exhaustion should be rare
and meaningful (a real non-convergence signal, e.g. a baseline stuck
cycling on an unreachable prerequisite) rather than an artifact of too
tight a cap. These are implementation parameters per `spec.md`'s
Assumptions -- adjustable in `tasks.md` if early runs show otherwise.

## 11. Constitution Principle III compliance (no subject conditionals)

**Decision**: The harness reads topic/prerequisite structure generically
via `Subject`/`Topic`/`PrerequisiteEdge` queries scoped by `subject_id`
parameter, exactly as `select_next_topic` already does -- no
`if subject_id == "algebra-1"` branching anywhere in harness code. The
existing `backend/scripts/check_no_subject_conditionals.py` CI check
already scans all of `backend/src`; the harness's service code lives
under `backend/src/services/evaluation/`, inside that existing scan
scope, so no new check is needed.

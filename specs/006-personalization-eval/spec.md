# Feature Specification: Real Personalization Signal -- Sequencing Evaluation Harness

**Feature Branch**: `006-personalization-eval`

**Created**: 2026-08-16

**Status**: Planned -- `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`,
and `/speckit-analyze` complete; pending `/speckit-implement`

**Input**: User description: "Milestone 3: Real Personalization Signal -- an
evaluation harness that simulates synthetic learner populations (with known,
simulated true mastery) and measures whether the Sequencing Agent's chosen
order reaches target mastery faster than a random or fixed-order baseline.
This is the milestone that makes 'personalizes based on what you know' a
measured claim instead of an assumed one. Report is surfaced on a live
deployed report page (Option C), not just a committed artifact."

## Clarifications

### Session 2026-08-16

- Q: Should the pass/fail hard gate (SC-001) be based on a single
  fixed-seed evaluation run, or must the Sequencing Agent's advantage
  hold across multiple independent random seeds before it counts as
  proven? → A: Single fixed seed, with population size per profile
  large enough that per-answer emission noise doesn't by itself flip
  the result -- not multi-seed repetition.
- Q: Should the harness re-run and republish a fresh Comparison Report
  automatically in CI, or is it manually triggered with an engineer
  choosing when to commit/publish its output? → A: Manual/on-demand --
  no CI job re-runs the harness automatically; an engineer runs it and
  publishes the result when they choose to.
- Q: Should the live report page be linked from the app's main
  navigation, or only reachable by someone who knows its direct URL? →
  A: Linked from main navigation -- any visitor browsing the deployed
  app can find it.

### Session 2026-08-17

- Q: When a synthetic learner has a topic that was never truly mastered
  (ground-truth `false`), should "questions-to-mastery" require the
  harness to keep asking about it until BKT's confirmation-streak
  crosses the mastered threshold anyway (which can happen from pure
  guessing noise, not real mastery), or should such topics be excluded
  from what counts as "converged" for that learner? → A: Excluded --
  FR-004's "every topic" is scoped to topics where that learner's
  ground-truth mastery is `true` only. Discovered during
  `/speckit-implement` Phase 7 (T031/T032): BKT's transition
  probability means any topic eventually drifts toward "mastered" from
  guessing noise alone, so requiring truly-unmastered topics to also
  cross the mastered band was making whole-learner convergence
  practically unreachable (empirically ~0% for `cold-start`, ~5% for
  `strong-prior` at the spec's default budget), leaving SC-001's
  random-baseline comparison with no converged data to compare against.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prove Sequencing Beats Random Ordering (Priority: P1)

An engineer (or anyone evaluating the product's core claim) runs the
evaluation harness against synthetic learner populations with known
ground-truth mastery, and sees whether the Sequencing Agent's real
next-topic selection reaches full mastery in fewer questions than picking
topics in a random order.

**Why this priority**: This is the milestone's entire reason for existing --
"personalizes based on what you know" is currently an assumed claim, not a
measured one. Without this comparison, nothing else in this milestone has a
foundation.

**Independent Test**: Run the harness for one subject with one synthetic
learner profile; confirm it produces a report showing questions-to-mastery
for both the Sequencing Agent condition and the random-order condition, with
the Sequencing Agent condition using fewer questions on average.

**Acceptance Scenarios**:

1. **Given** a synthetic learner population with known per-topic ground-truth
   mastery, **When** the harness runs the Sequencing Agent condition and the
   random-order condition side by side, **Then** the report shows the number
   of questions each condition needed to bring every truly-masterable topic
   (ground-truth `true`) to the "mastered" band for every simulated learner
   (FR-004; Clarifications, session 2026-08-17).
2. **Given** a completed evaluation run, **When** the aggregate report is
   computed, **Then** the Sequencing Agent condition's mean questions-to-
   mastery is lower than the random-order condition's mean questions-to-
   mastery.

---

### User Story 2 - Prove the Result Isn't Cherry-Picked (Priority: P2)

An engineer re-runs the harness across multiple distinct synthetic learner
profiles (varying starting ground-truth mastery patterns) and across both
existing subject content artifacts, to confirm the Sequencing Agent's
advantage holds broadly rather than only for one convenient scenario.

**Why this priority**: A single favorable comparison isn't evidence of a
real effect. The roadmap's definition of done explicitly requires this
result to hold "across multiple synthetic learner profiles (not
cherry-picked)."

**Independent Test**: Run the harness across at least three distinct learner
profiles and both subject content artifacts; confirm the report breaks
results out per profile and per subject, not only as a single pooled
average.

**Acceptance Scenarios**:

1. **Given** multiple synthetic learner profiles spanning different starting
   mastery patterns, **When** the harness runs all conditions for each
   profile, **Then** the report shows a per-profile breakdown, and the
   Sequencing Agent condition outperforms the random-order condition in each
   profile individually, not only in the pooled aggregate.
2. **Given** both Milestone 1 subject content artifacts (Algebra I and
   Biology), **When** the harness runs against each, **Then** the report
   shows results broken out per subject, demonstrating the comparison holds
   subject-agnostically.

---

### User Story 3 - Compare Against a Fixed Topic Order Too (Priority: P3)

An engineer also compares the Sequencing Agent's ordering against a fixed,
canonical topic order (the order topics are authored in the content
artifact), to rule out the possibility that any deterministic order --
mastery-model-driven or not -- would perform just as well.

**Why this priority**: Beating a random baseline is necessary but not
sufficient; a skeptic's next question is "would any fixed order have done as
well?" This strengthens the claim but isn't the roadmap's hard gate the way
the random-baseline comparison is.

**Independent Test**: Run the harness with the fixed-order condition
included; confirm the report shows a third column/condition for fixed order
alongside Sequencing Agent and random order.

**Acceptance Scenarios**:

1. **Given** a completed evaluation run, **When** the report is generated,
   **Then** it includes the fixed canonical-order condition's
   questions-to-mastery figures alongside the other two conditions for every
   profile and subject tested.

---

### User Story 4 - View the Evidence on a Live Report Page (Priority: P2)

A visitor to the deployed product (e.g. an instructor evaluating the
platform, or anyone verifying the personalization claim) opens a report page
on the live site and sees the evaluation harness's latest results presented
in plain terms, without needing to run anything locally.

**Why this priority**: Per the chosen scope, this milestone's evidence must
be part of the live, clickable demo (Constitution Principle IX), not only a
developer-facing artifact -- otherwise the product's central personalization
claim remains unverifiable to anyone who isn't running the codebase
themselves.

**Independent Test**: Load the report page on the deployed environment
without authentication; confirm it renders the latest evaluation run's
comparison results (not a stale or placeholder value) and states, in plain
language, that the Sequencing Agent reaches mastery faster than random
ordering.

**Acceptance Scenarios**:

1. **Given** a completed evaluation run has been published, **When** a
   visitor loads the report page, **Then** the page displays per-condition
   questions-to-mastery figures and a plain-language statement of the
   result, sourced from that run's output -- never a hardcoded or
   illustrative number.
2. **Given** no evaluation run has ever been published yet, **When** a
   visitor loads the report page, **Then** the page states clearly that no
   evaluation has run yet rather than showing blank or fabricated figures.

### Edge Cases

- What happens when a synthetic learner's ground-truth mastery for a topic
  already starts at or above the "mastered" band? That topic contributes
  zero questions-to-mastery for every condition for that learner, and must
  not be excluded from the average (it's a real, valid data point).
- What happens when a simulated learner does not reach the "mastered" band
  for every topic where their ground truth is `true` (FR-004) within the
  configured maximum-question budget under a given condition? That
  learner/condition pair is recorded as "did not converge" and excluded from
  the mean/median questions-to-mastery figure for that condition, but
  counted and surfaced in the report as a non-convergence rate -- silently
  dropping it would misrepresent the comparison. Topics where the learner's
  ground truth is `false` play no role in this determination (Clarifications,
  session 2026-08-17).
- What happens if a topic is never reachable under a condition because its
  prerequisites are never satisfied within the question budget (e.g. the
  random-order condition never happens to visit a prerequisite)? Same
  treatment as non-convergence above.
- How does the report page behave if the underlying evaluation run's data is
  present but incomplete (e.g. only one subject has results)? The page
  renders what's available and states which subjects/profiles are covered,
  rather than failing to render or implying full coverage.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST generate synthetic learner populations, each
  with a known ground-truth mastery value per topic that is tracked
  separately from, and never directly revealed to, the Sequencing Agent
  under test.
- **FR-002**: The harness MUST simulate each synthetic learner's answer
  correctness for a given question using the same slip/guess emission
  parameters already locked for the mastery model (`tech-stack.md` /
  `specs/001-domain-agnostic-core/research.md`), driven by that learner's
  ground-truth mastery -- never by the Sequencing Agent's own belief about
  that learner.
- **FR-003**: The harness MUST run three ordering conditions per synthetic
  learner: (a) the production Sequencing Agent's real next-topic selection,
  invoked through its actual code path (not a reimplementation); (b) a
  random topic-order baseline; (c) a fixed canonical topic-order baseline
  derived from the content artifact's authored `order_index`.
- **FR-004**: For each condition and each synthetic learner, the harness
  MUST record the number of questions answered until every topic **where
  that learner's ground-truth mastery is `true`** reaches the existing
  "mastered" band -- BKT posterior `p_mastery ≥ 0.7` **and** the existing
  confirmation-streak requirement (two consecutive post-update observations
  at or above 0.7, per the three-band model's anti-degenerate-answer-pattern
  gate already locked in Milestone 1) -- or a configured maximum-question
  budget is exhausted, whichever comes first. Topics where the learner's
  ground-truth mastery is `false` are excluded from this convergence check
  entirely: BKT's transition probability means any topic eventually drifts
  toward "mastered" from guessing noise alone regardless of true mastery, so
  requiring a genuinely-unmastered topic to also cross the mastered band
  would measure spurious drift, not real mastery, and would make
  whole-learner convergence practically unreachable for realistic profiles
  (Clarifications, session 2026-08-17).
- **FR-005**: The harness MUST run the full three-condition comparison
  across multiple distinct synthetic learner profiles (varying starting
  ground-truth mastery patterns) and across both Milestone 1 content
  artifacts (Algebra I, Biology) -- never a single profile or single
  subject.
- **FR-006**: The harness MUST produce a comparison report containing, per
  condition, per profile, per subject, and in aggregate: mean and median
  questions-to-mastery, and the non-convergence count/rate.
- **FR-007**: Synthetic learner population generation MUST be deterministic
  given a fixed seed, so a report is reproducible run-to-run (Constitution
  Principle I).
- **FR-008**: The harness MUST call the Sequencing Agent's real
  `select_next_topic` function for the Sequencing Agent condition's
  decisions, not a reimplementation or approximation of its logic --
  consistent with the existing precedent (the Recommendation Agent's
  report builder, `GET /mastery-state`) that pure, LLM-free tool
  functions are not individually Langfuse-traced; topic selection alone
  has never been traced independently of full question generation, so
  the harness introduces no new tracing gap.
- **FR-009**: The harness MUST use only synthetic learner data; it MUST NOT
  read, write, or depend on any real learner's assessment history or
  mastery state (Constitution Principle VIII).
- **FR-010**: The system MUST publish the most recent evaluation run's
  comparison report to a live report page in the deployed application,
  reachable without authentication and linked from the application's main
  navigation (not direct-URL-only), per the chosen scope of making this
  milestone's evidence part of the live demo.
- **FR-011**: The report page MUST render the actual latest run's figures
  (never hardcoded, illustrative, or placeholder numbers) and MUST clearly
  state when no evaluation run has been published yet, rather than showing
  blank or fabricated results.
- **FR-012**: The report page MUST present, in plain language accessible to
  a non-technical visitor (e.g. an instructor), the headline result: whether
  and by how much the Sequencing Agent's ordering outperforms the random
  baseline.
- **FR-013**: Publishing an evaluation run's report MUST be logged with
  enough context (run timestamp, seed, profiles/subjects covered) to answer
  "which run produced the numbers currently shown on the report page"
  (Constitution Principle V).
- **FR-014**: Every Sequencing Agent condition decision (every simulated
  learner's topic selection) MUST be recorded in the same pedagogical
  audit log real learner decisions use, exactly as a real request would
  (Constitution Principle V) -- the harness's synthetic learners are real
  rows in that log's own data model (FR-009's `is_demo=True` requirement),
  not an exempted code path. These rows MUST be deleted at the end of the
  harness run alongside the synthetic learner rows themselves, so no
  synthetic data persists after the run completes. Random and fixed-order
  conditions are exempt from this requirement because they never invoke
  the Sequencing Agent or touch any learner row at all (FR-003b/c).

### Key Entities

- **Synthetic Learner Profile**: A named archetype (e.g. "strong prior,"
  "weak prior," "uneven mastery") defining a distribution used to generate
  ground-truth per-topic mastery values for a batch of simulated learners.
- **Simulated Assessment Event**: A synthetic answer the harness generates
  for one simulated learner, topic, and question, produced from that
  learner's ground-truth mastery via the locked emission model. For the
  Sequencing Agent condition, this is recorded as a real `AssessmentEvent`
  row (FR-014), the same audit mechanism a real request uses; for the
  random and fixed-order conditions it stays in-memory only (FR-003b/c
  never touch a learner row at all).
- **Evaluation Run**: One full execution of the harness across all
  profiles, subjects, and conditions, under a fixed seed, producing a single
  Comparison Report.
- **Comparison Report**: The aggregated and per-breakout (profile x subject
  x condition) questions-to-mastery statistics produced by an Evaluation
  Run, including non-convergence counts -- this is also the data source for
  the live report page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across every synthetic learner profile and both subjects
  tested, the Sequencing Agent condition's mean questions-to-mastery is
  lower than the random-order baseline's mean questions-to-mastery, both in
  the per-profile/per-subject breakdowns and in the pooled aggregate,
  evaluated from a single fixed-seed Evaluation Run (not repeated across
  multiple seeds -- see Clarifications). (Hard gate, per roadmap.)
- **SC-002**: The Sequencing Agent condition's mean questions-to-mastery is
  no higher than the fixed canonical-order baseline's, in the pooled
  aggregate across all profiles and subjects tested.
- **SC-003**: An identical evaluation run (same seed, same profile/subject
  configuration) produces an identical Comparison Report on repeated runs.
- **SC-004**: 100% of the Sequencing Agent condition's topic-selection
  decisions are produced by calling the production `select_next_topic`
  function directly (verified by a code-level check, e.g. that the
  harness imports and calls it rather than duplicating its logic), never
  a reimplementation.
- **SC-005**: A visitor can load the live report page and, within one
  screen (no additional navigation), see the headline Sequencing-Agent-
  vs-random-baseline result stated in plain language.
- **SC-006**: Zero real learner data is read or written by any harness
  component, verified by two automated checks: (a) pre-existing real
  (non-`is_demo`) learner rows are provably unchanged by a harness run,
  and (b) zero synthetic rows -- including `DemoLearnerProfile`,
  `MasteryState`, and the `AssessmentEvent` rows FR-014 requires -- remain
  in the database after a run completes.
- **SC-007**: Milestones 1 and 2's full acceptance-scenario suites still
  pass after this milestone's changes (regression check, per roadmap).

## Assumptions

- "Target mastery" reuses the three-band mastery model already locked in
  Milestone 1: a topic counts as reaching target mastery once it reaches
  the existing "mastered" band, which requires both `p(mastery) ≥ 0.7`
  *and* the confirmation-streak gate (two consecutive qualifying
  observations) -- not the 0.7 threshold alone (see FR-004; corrected
  post-`/speckit-analyze`, finding I2). A learner's overall
  "questions-to-mastery" convergence is scoped to topics where that
  learner's ground-truth mastery is `true` only -- topics with `false`
  ground truth are excluded from the convergence check, since BKT's
  transition probability means any topic eventually drifts toward
  "mastered" from guessing noise alone, which would otherwise make
  universal (all-topics) convergence practically unreachable and not a
  meaningful signal of ordering quality (Clarifications, session
  2026-08-17).
- The fixed canonical-order baseline uses each content artifact's existing
  authored `order_index` field; no new ordering needs to be authored for
  this milestone.
- Both existing Milestone 1 content artifacts (Algebra I, Biology) are the
  full subject pool for this milestone; no new subject content is required.
- The exact number of synthetic learner profiles, population size per
  profile, and the maximum-question budget per learner are implementation
  parameters finalized in `plan.md`, constrained by FR-005's "multiple
  profiles, both subjects, not cherry-picked" requirement and by the
  Clarifications' single-seed methodology: population size per profile
  must be large enough that per-answer slip/guess noise doesn't by itself
  determine SC-001's result.
- The live report page is a read-only, unauthenticated page reachable from
  the deployed application (consistent with Milestone 1's demo-first,
  no-login-required posture); it does not require instructor/learner
  accounts to exist, since those don't exist yet at this point in the
  roadmap.
- The report page sources its data from the most recently published
  Evaluation Run's Comparison Report. Publishing is manual and on-demand
  (see Clarifications): an engineer runs the harness and commits/publishes
  its output when they choose to -- there is no CI job that re-runs the
  harness automatically on merge. The exact publication mechanism (e.g.
  committed data file read at build/request time vs. a small stored
  record) is a `plan.md`-level implementation decision, not fixed here.
- This milestone does not require real-time re-running of the evaluation
  harness in response to a page load -- the harness is expected to run as
  part of the development/CI workflow, and the report page displays its
  most recent output per Constitution Principle IX's serverless/stateless
  constraint (no long-running simulation job triggered by a request).

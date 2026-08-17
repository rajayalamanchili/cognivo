# Feature Specification: Recommendation Agent -- Weak-Area Flagging and Next-Step Suggestions

**Feature Branch**: `002-recommendation-agent`

**Created**: 2026-08-14

**Status**: Draft -- pending `/speckit-clarify`

**Input**: User description: "A Recommendation Agent that analyzes a
learner's mastery state and assessment history to flag weak areas with
cited evidence and suggest concrete, prerequisite-aware next steps"

## Clarifications

### Session 2026-08-16

- Q: Should "weak area" reuse Milestone 1's existing three-band mastery
  model, and if so, which band(s) count as "weak"? → A: Reuse 001's
  three-band model; "weak" means the "struggling" band only (mastery <
  0.4). The "developing" band (0.4-0.7) is reported separately as
  "in progress," not flagged as weak. The same 0.4 cutoff is used for
  FR-007's prerequisite-gap check.
- Q: What's the minimum amount of assessment data required before a
  topic can be confidently flagged as weak? → A: Per-topic minimum of 3
  assessment events. A topic with fewer than 3 recorded events (but at
  least 1) is reported as "insufficient data for this topic" rather than
  confidently flagged weak, developing, or mastered -- distinct from
  FR-003's "not yet assessed" (zero events).
- Q: What rule decides when the report switches from a "top weak areas"
  list to a "broad review needed" message (FR-005)? → A: Proportion-
  based threshold -- when 60% or more of confidently-assessed topics
  (those with >= 3 recorded events, per the prior clarification) fall in
  the struggling band, the report uses "broad review needed across most
  topics" framing instead of enumerating each struggling topic
  individually. Topics with "not yet assessed" or "insufficient data"
  status are excluded from this proportion's denominator.
- Q: Should the set of flagged weak topics be computed deterministically,
  or can an LLM participate in deciding which topics count as weak? →
  A: Fully deterministic flagging. Weak-topic selection (FR-002),
  per-topic data-sufficiency status (FR-004), the broad-review threshold
  (FR-005), and prerequisite-gap detection (FR-007) are all computed by
  deterministic code from the mastery model's output -- never an LLM's
  judgment call. An LLM, if used, is restricted to generating
  natural-language prose that describes already-computed structured
  results; it never decides which topics are flagged or which
  prerequisite is named. This mirrors Constitution Principle I's bar for
  the Sequencing Agent.
- Q: When a flagged topic's prerequisite is itself unmastered, and that
  prerequisite also has an unmastered prerequisite, does the suggestion
  recurse to the deepest unmastered root or stop one level up? → A:
  Recurse to the root cause -- walk the prerequisite chain until reaching
  a topic whose own prerequisites are all mastered (or that has no
  prerequisites), and surface that topic as the suggestion. If the chain
  reaches a topic with no recorded assessment data before reaching an
  unmastered-but-assessed one, recursion stops there and that topic is
  surfaced as "not yet assessed" (per the Edge Cases entry on
  unassessed prerequisites), not assumed mastered or unmastered.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a weak-area report grounded in real evidence (Priority: P1)

A learner (or instructor, on a learner's behalf) requests a progress
report. The Recommendation Agent analyzes the learner's full mastery
state and assessment history and produces a list of flagged weak topics,
each backed by specific supporting evidence -- not a vague impression.

**Why this priority**: This is the direct implementation of the original
product requirement to "analyze performance data to flag weak areas" --
and it's the foundation the next-step suggestions (User Story 2) are
built on, so it has to be right first.

**Independent Test**: Given a scripted mastery-state and
assessment-history fixture with known weak topics, request a report and
confirm the flagged topics match the expected set, each with a citation
to the specific assessment events that justify the flag.

**Acceptance Scenarios**:

1. **Given** a learner's mastery state shows a topic below the mastery
   threshold, **When** a weak-area report is requested, **Then** that
   topic appears in the flagged list, citing the specific assessment
   events (which questions, which answers, how mastery moved) that
   justify the flag -- not just the topic name and a number.
2. **Given** a topic the learner has never been assessed on, **When** a
   report is generated, **Then** that topic is explicitly reported as
   "not yet assessed," never silently omitted or falsely implied to be
   fine.
3. **Given** every topic in a learner's assessment history has fewer
   than 3 recorded assessment events (FR-004's per-topic minimum),
   **When** a report is requested, **Then** the agent explicitly states
   there isn't enough data yet, rather than producing a confident-
   sounding report from thin evidence.
4. **Given** 60% or more of a learner's confidently-assessed topics fall
   in the struggling band (a learner just starting out), **When** a
   report is generated, **Then** the agent represents this honestly
   (e.g. "broad review needed across most topics") rather than
   arbitrarily narrowing to a misleadingly small subset to fit a
   fixed-length "top weak areas" list.
5. **Given** a topic in the "developing" band (mastery 0.4-0.7, at
   least 3 recorded events), **When** a report is generated, **Then**
   that topic is explicitly listed as "in progress" -- distinct from a
   flagged weak area and from "not yet assessed" -- never silently
   omitted from the report.

---

### User Story 2 - Get a concrete next step, not generic advice (Priority: P1)

For each flagged weak area, the learner gets a specific, actionable
suggestion grounded in the subject's actual content structure -- not
"study more" or "practice topic X," but a suggestion that accounts for
what the learner needs to shore up first.

**Why this priority**: "Suggest next steps" was the second half of the
original product requirement this agent implements, and a weak-area
report without an actionable suggestion attached is only half the
value.

**Independent Test**: Given a flagged weak topic whose prerequisite is
itself unmastered, request next-step suggestions and confirm the
suggestion surfaces the prerequisite gap, not just "practice this
topic more."

**Acceptance Scenarios**:

1. **Given** a flagged weak topic whose prerequisites (per the content
   artifact's topic graph) are all already mastered, **When** a
   suggestion is generated, **Then** it recommends direct practice on
   that topic.
2. **Given** a flagged weak topic whose prerequisite is itself below
   mastery threshold, **When** a suggestion is generated, **Then** it
   recommends addressing the prerequisite first, explicitly naming it --
   never suggesting the learner "jump ahead" to practice a topic whose
   foundation is shaky.
3. **Given** a suggestion is generated, **When** it's inspected, **Then**
   it references a real topic that exists in the subject's content
   artifact -- never a fabricated or freeform topic name not present in
   the actual content graph.
4. **Given** a flagged weak topic with more than one direct prerequisite
   and more than one of them is unmastered, **When** a suggestion is
   generated, **Then** it names exactly one root-cause prerequisite --
   the one with the lowest mastery value, ties broken by the content
   artifact's authored topic order -- never surfacing more than one
   prerequisite as the suggestion.

---

### User Story 3 - Trust that recommendations are explainable, not black-box (Priority: P2)

An instructor questioning a flagged weak area or a suggested next step
can trace it back to the specific data that produced it.

**Why this priority**: Directly implements Constitution Principle V for
this specific agent -- scoped below User Stories 1-2 because the report
and suggestions have to exist first before their explainability is
worth testing in isolation.

**Independent Test**: Given a generated report, confirm every flagged
weak area and every suggestion is present in the audit log with enough
detail (which assessment events, which mastery values, which
prerequisite check) to reconstruct why it was produced.

**Acceptance Scenarios**:

1. **Given** a weak-area report has been generated, **When** an
   instructor asks "why was this topic flagged," **Then** the system
   returns the specific assessment events and mastery trajectory that
   justify the flag, traceable via the audit log.

---

### User Story 4 - Confirm this agent's job is genuinely distinct from Sequencing (Priority: P2)

A reviewer (or a future contributor) needs to be able to see that the
Recommendation Agent and the Sequencing Agent are not doing the same
thing under two different names.

**Why this priority**: Directly required by Constitution Principle IV,
which requires every agent boundary to reflect a real, distinct
responsibility with its own evaluation criteria -- this is the test that
proves that requirement is actually satisfied here, not just asserted.

**Independent Test**: Compare the Sequencing Agent's per-question,
real-time topic selection against the Recommendation Agent's on-demand,
multi-topic synthesized report for the same mastery state, and confirm
they answer genuinely different questions (what to assess right now, vs.
a broader pattern across the learner's whole history) -- and that the
two are allowed to point at different topics without that being treated
as a bug.

**Acceptance Scenarios**:

1. **Given** the same mastery state, **When** the Sequencing Agent
   selects the next question topic and the Recommendation Agent
   generates a weak-area report, **Then** the two are permitted to name
   different topics as most urgent -- Sequencing optimizes the single
   next question given prerequisite ordering and question freshness;
   Recommendation synthesizes a broader pattern across the learner's
   whole history. This divergence must itself be explainable (each
   agent's own reasoning is traceable), not treated as an inconsistency
   to eliminate.
2. **Given** the two agents' own test suites, **When** they are
   inspected, **Then** neither reuses the other's fixtures or assertions
   -- each is evaluated against its own distinct correctness criteria.

---

### Edge Cases

- What happens if a learner's mastery state has been recently reset or
  the content artifact's topic graph has changed since the learner's
  last assessment? (The report must handle stale or partially-invalid
  references gracefully -- flagging the mismatch, not crashing or
  silently ignoring affected topics.)
- What happens when a suggested next step names a prerequisite topic
  that itself has no recorded assessment data at all (neither mastered
  nor known weak)? (Must be treated the same as User Story 1 Scenario 2
  -- explicitly "not yet assessed" -- not silently assumed mastered or
  unmastered.)
- What happens if a learner requests a report immediately after a single
  wrong answer? (Must not overreact to one data point -- per FR-004, a
  topic needs at least 3 recorded assessment events before it can be
  confidently flagged weak; a single wrong answer produces "insufficient
  data for this topic," never a confident weak-area flag.)
- What happens if two topics are tied for "weakest"? (The report must
  surface both, not arbitrarily pick one via an undocumented tie-break
  rule.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Recommendation Agent MUST analyze a learner's full
  mastery state and assessment-event history to produce a weak-area
  report on request.
- **FR-002**: Every flagged weak area MUST cite the specific assessment
  events and mastery-value trajectory that justify it -- a topic name
  and a bare number alone does not satisfy this requirement. A topic is
  "weak" when its mastery value is in the "struggling" band (< 0.4) per
  Milestone 1's three-band mastery model (Clarifications); the
  "developing" band is not flagged as weak (see FR-003a).
- **FR-003**: Topics with no recorded assessment data MUST be explicitly
  reported as "not yet assessed," never omitted or implied to be fine.
- **FR-003a**: Topics in the "developing" band (mastery 0.4-0.7, per
  FR-002's three-band model, with at least 3 recorded events per
  FR-004) MUST be explicitly reported as "in progress" -- a third
  category distinct from a flagged weak area (FR-002) and from "not yet
  assessed" (FR-003), never silently omitted from the report.
- **FR-004**: A topic with fewer than 3 recorded assessment events (but
  at least 1) MUST be reported as "insufficient data for this topic"
  rather than confidently flagged weak, developing, or mastered. A
  topic's assessment-event count for this rule is the same count
  Milestone 1's mastery model already tracks per (learner, topic) --
  the number of mastery updates recorded for it (`specs/001-domain-
  agnostic-core/data-model.md`'s `MasteryState.update_count`) -- not a
  second, independently-computed count. When
  every assessed topic in the learner's mastery state falls below this
  per-topic minimum, the agent MUST explicitly state that there isn't
  enough data yet for a confident report, rather than producing a
  confidently-worded report from insufficient evidence.
- **FR-005**: When 60% or more of confidently-assessed topics (those
  with at least 3 recorded events) fall in the struggling band, the
  report MUST use "broad review needed across most topics" framing
  instead of enumerating each struggling topic individually as a
  fixed-size "top N" list that misrepresents the learner's actual state.
  Topics with "not yet assessed" or "insufficient data" status are
  excluded from this proportion's denominator.
- **FR-006**: Each flagged weak area MUST come with at least one
  concrete next-step suggestion that references a real topic in the
  subject's content artifact.
- **FR-007**: A next-step suggestion for a topic whose prerequisite is
  itself below mastery threshold (mastery < 0.4, the same "struggling"
  cutoff used for FR-002) MUST recommend addressing that prerequisite
  first, named explicitly -- never suggesting direct practice on a topic
  whose foundation is unmastered. When that prerequisite itself has an
  unmastered prerequisite, the suggestion MUST recurse up the chain and
  name the deepest unmastered prerequisite (the root cause), stopping
  early only if it reaches a topic with no recorded assessment data, in
  which case that topic is surfaced as "not yet assessed" instead. When
  a topic reached during this recursion (the originally-flagged topic
  or any prerequisite along the way) has more than one direct
  prerequisite and more than one of them is unmastered, recursion MUST
  follow only the one with the lowest mastery value, ties broken by the
  content artifact's authored topic order -- the same deterministic
  tie-break the Sequencing Agent already uses for topic selection (per
  Milestone 1's data-model.md) -- so exactly one root-cause prerequisite
  is ever surfaced per flagged topic, never a branching set.
- **FR-008**: Every weak-area flag and next-step suggestion MUST be
  logged in the audit log with enough detail to reconstruct why it was
  produced (Constitution Principle V), and MUST emit a trace to the
  observability backend per the tracing requirement established for
  every agent invocation.
- **FR-009**: The Recommendation Agent's test suite MUST be independent
  of the Sequencing Agent's -- distinct fixtures and assertions,
  verifying distinct correctness criteria, operationalizing Constitution
  Principle IV's requirement that agent boundaries reflect real,
  separately-evaluable responsibilities.
- **FR-010**: The Recommendation Agent's divergence from the Sequencing
  Agent's real-time topic selection (they may legitimately point at
  different topics for the same mastery state) MUST NOT be treated as a
  defect to reconcile -- each agent's own reasoning must be independently
  explainable, but the two are not required to agree.
- **FR-011**: Weak-topic selection (FR-002), per-topic data-sufficiency
  status (FR-004), the broad-review threshold (FR-005), and
  prerequisite-gap detection (FR-007) MUST be computed by deterministic
  code operating on the mastery model's output -- never decided by an
  LLM's freeform judgment. Any LLM use in this agent MUST be restricted
  to generating natural-language prose describing already-computed
  structured results; it MUST NOT influence which topics are flagged or
  which prerequisite is named.

### Key Entities *(include if feature involves data)*

- **WeakAreaReport**: a learner's full report at a point in time --
  flagged weak topics (each with cited evidence), "in progress"
  (developing-band) topics, "not yet assessed" topics, "insufficient
  data" topics, and an overall confidence/data-sufficiency statement.
- **NextStepSuggestion**: a concrete, content-artifact-grounded
  suggestion tied to a specific flagged weak area, including any
  prerequisite-gap reasoning that produced it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a scripted mastery-state fixture with known weak
  topics, the Recommendation Agent's flagged weak areas match the
  expected set, verified by an automated test.
- **SC-002**: 100% of flagged weak areas in the test suite cite specific
  supporting assessment events -- verified by an automated check that
  rejects any flag without a citation.
- **SC-003**: 100% of next-step suggestions in the test suite reference
  a real topic present in the relevant content artifact, and 100% of
  suggestions involving an unmastered prerequisite correctly surface
  that prerequisite rather than the original weak topic directly --
  verified by an automated check against the content artifact's
  prerequisite graph.
- **SC-004**: Given a "too little data" fixture where every topic has
  fewer than 3 recorded assessment events, the agent explicitly states
  insufficient data rather than producing a confident-sounding report --
  verified by a specific test.
- **SC-005**: The Recommendation Agent's and Sequencing Agent's test
  suites share zero fixtures or assertions, verified by inspection --
  operationalizing the "distinct evaluation criteria" requirement
  concretely rather than leaving it as an unverified design intention.

## Assumptions

- This agent operates on a single learner's data at a time. Instructor-
  facing aggregation of weak-area reports across an entire classroom
  roster is deferred to the instructor-classroom milestone, which is
  expected to consume this agent's per-learner output as a building
  block rather than re-implementing weak-area detection from scratch.
- Next-step suggestions in this milestone reference only the platform's
  own content artifact (its topic graph and generated-question flow) --
  recommending external resources (specific videos, articles, or other
  content this platform doesn't control) is explicitly out of scope
  here. External-resource recommendation would introduce a different
  trust and quality-evaluation problem (is a third-party resource
  actually good?) distinct enough that, per Constitution Principle IV,
  it deserves its own separately-evaluated capability if built later,
  not a silent extension of this one.
- The Recommendation Agent is implemented as a local ADK sub-agent, not
  a remote A2A service, per Constitution Principle VI -- no concrete
  need for independent versioning or deployment has been identified for
  this agent at this milestone's scope.
- This feature depends on the mastery-state and assessment-event data
  model established in the domain-agnostic core milestone, but does not
  require the personalization-evaluation harness or free-text grading to
  exist first, since it can operate on structured-question data alone.

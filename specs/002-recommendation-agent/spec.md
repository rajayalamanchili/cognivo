# Feature Specification: Recommendation Agent -- Weak-Area Flagging and Next-Step Suggestions

**Feature Branch**: `002-recommendation-agent`

**Created**: 2026-08-14

**Status**: Draft -- pending `/speckit-clarify`

**Input**: User description: "A Recommendation Agent that analyzes a
learner's mastery state and assessment history to flag weak areas with
cited evidence and suggest concrete, prerequisite-aware next steps"

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
3. **Given** a learner has answered too few questions overall for any
   confident assessment, **When** a report is requested, **Then** the
   agent explicitly states there isn't enough data yet, rather than
   producing a confident-sounding report from thin evidence.
4. **Given** every topic in a learner's mastery state is roughly equally
   weak (a learner just starting out), **When** a report is generated,
   **Then** the agent represents this honestly (e.g. "broad review
   needed across most topics") rather than arbitrarily narrowing to a
   misleadingly small subset to fit a fixed-length "top weak areas" list.

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
  wrong answer? (Must not overreact to one data point -- the "too little
  data" and "broad review needed" honesty requirements from User Story 1
  apply here too; a single wrong answer alone should not produce a
  confidently-worded weak-area flag.)
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
  and a bare number alone does not satisfy this requirement.
- **FR-003**: Topics with no recorded assessment data MUST be explicitly
  reported as "not yet assessed," never omitted or implied to be fine.
- **FR-004**: When overall assessment history is too sparse for a
  confident report, the agent MUST explicitly state this rather than
  producing a confidently-worded report from insufficient evidence.
- **FR-005**: When most or all topics are roughly equally weak, the
  report MUST represent this honestly (e.g. "broad review needed") 
  rather than arbitrarily narrowing to a fixed-size "top N" list that
  misrepresents the learner's actual state.
- **FR-006**: Each flagged weak area MUST come with at least one
  concrete next-step suggestion that references a real topic in the
  subject's content artifact.
- **FR-007**: A next-step suggestion for a topic whose prerequisite is
  itself below mastery threshold MUST recommend addressing that
  prerequisite first, named explicitly -- never suggesting direct
  practice on a topic whose foundation is unmastered.
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

### Key Entities *(include if feature involves data)*

- **WeakAreaReport**: a learner's full report at a point in time --
  flagged weak topics (each with cited evidence), "not yet assessed"
  topics, and an overall confidence/data-sufficiency statement.
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
- **SC-004**: Given a "too little data" fixture, the agent explicitly
  states insufficient data rather than producing a confident-sounding
  report -- verified by a specific test.
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

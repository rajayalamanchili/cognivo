# Feature Specification: Learner Dashboard

**Feature Branch**: `004-learner-dashboard`

**Created**: 2026-08-14

**Status**: Draft -- pending `/speckit-clarify`

**Input**: User description: "A learner-facing dashboard surfacing
per-topic mastery, the Recommendation Agent's latest weak-area report,
and an illustrative path-so-far and path-ahead visualization"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See overall progress at a glance (Priority: P1)

A learner opens their dashboard and sees per-topic mastery across the
subject's whole topic graph -- not just the one topic they happened to
be assessed on most recently.

**Why this priority**: Without this, all of Milestone 1's mastery-model
work is invisible to the person it's meant to serve -- the model exists,
but nothing surfaces it directly.

**Independent Test**: Given a learner with a mix of mastered,
in-progress, and untouched topics, load the dashboard and confirm every
topic in the subject's content artifact appears with its correct current
mastery value or an explicit "not yet assessed" state.

**Acceptance Scenarios**:

1. **Given** a learner has mastery data for some topics, **When** the
   dashboard loads, **Then** every topic in the subject's content
   artifact is shown with its current mastery value, and topics with no
   assessment history are explicitly labeled "not yet assessed" -- never
   silently omitted (consistent with Milestone 1's FR-005 and the
   Recommendation Agent's FR-003).
2. **Given** a learner has just answered a new question, **When** the
   dashboard is next loaded, **Then** it reflects the updated mastery
   state -- read fresh from the database on each load, never from a
   stale cache.

---

### User Story 2 - See weak areas and next steps without asking (Priority: P1)

The dashboard surfaces the Recommendation Agent's weak-area report and
next-step suggestions directly, so a learner doesn't have to know to ask
for one.

**Why this priority**: This is the most direct way the Recommendation
Agent's value actually reaches a learner -- without this, that agent's
output only exists for someone who explicitly requests a report.

**Independent Test**: Given a learner with a known weak topic, load the
dashboard and confirm the same flagged weak area and next-step
suggestion the Recommendation Agent would independently produce for
that mastery state appears on the dashboard.

**Acceptance Scenarios**:

1. **Given** a learner's current mastery state, **When** the dashboard
   loads, **Then** it triggers a fresh Recommendation Agent report
   (not a cached one, consistent with User Story 1's freshness
   requirement) and displays its flagged weak areas and next-step
   suggestions.
2. **Given** the Recommendation Agent's "too little data" or "broad
   review needed" honesty requirements (that feature's FR-004/FR-005),
   **When** either applies, **Then** the dashboard displays that
   framing verbatim -- it does not paraphrase away the agent's explicit
   uncertainty language into a falsely confident-sounding summary.

---

### User Story 3 - See the path so far and what's likely ahead (Priority: P2)

The dashboard shows topics already engaged with, the currently
recommended focus, and a small set of likely upcoming topics -- clearly
marked as illustrative, not a fixed commitment.

**Why this priority**: This is the direct answer to "does the product
show a learning path" -- but it's scoped below User Stories 1-2 because
an accurate mastery view and weak-area surface have to exist first; the
path visualization is presentation on top of data those provide.

**Independent Test**: Given a learner's current mastery state, load the
dashboard and confirm the displayed "upcoming topics" list is generated
by consulting the Sequencing Agent's current selection logic (not a
separately invented ordering) and is visibly labeled as subject to
change.

**Acceptance Scenarios**:

1. **Given** a learner's mastery state and the subject's topic graph,
   **When** the dashboard loads, **Then** it shows: topics already
   assessed (with mastery level), the Sequencing Agent's current
   top-priority next topic, and a small number of topics likely to
   follow based on the prerequisite graph.
2. **Given** the "upcoming topics" section is displayed, **When** a
   learner reads it, **Then** it carries an explicit, visible disclosure
   that this is illustrative and can change based on future performance
   -- never presented as a committed, fixed multi-step plan, since the
   Sequencing Agent only ever commits to one decision at a time
   (Milestone 1's own architecture).

---

### User Story 4 - The dashboard makes sense for a brand-new learner (Priority: P2)

A learner with zero assessment history opens the dashboard and gets a
coherent "just getting started" view, not an empty or broken page.

**Why this priority**: An unhandled empty state is one of the most
common real-world dashboard bugs -- worth its own scenario rather than
assuming User Stories 1-3 handle it by accident.

**Independent Test**: Load the dashboard for a learner with no
assessment history at all and confirm it renders a coherent
"just getting started" state rather than an empty or error view.

**Acceptance Scenarios**:

1. **Given** a learner has no assessment history, **When** the dashboard
   loads, **Then** every topic shows "not yet assessed," the weak-area
   section reflects the Recommendation Agent's own "not enough data"
   framing, and the path visualization shows the subject's entry-level
   topics as the starting point -- a coherent, honest empty state, not
   a broken or blank page.

---

### Edge Cases

- What happens if the subject's content artifact changes (a topic is
  added or removed) after a learner already has assessment history
  against the old version? (Topics no longer in the current artifact
  must not appear; new topics with no history must show "not yet
  assessed" -- the dashboard always reflects the current content
  artifact, not a stale snapshot.)
- What happens if a learner has two browser tabs open and answers a
  question in one? (The other tab's dashboard is allowed to be stale
  until its next load/refresh -- this milestone does not require
  real-time push updates; see Assumptions.)
- What happens if the Recommendation Agent's report generation is slow
  or fails when the dashboard loads? (The mastery-view portion of the
  dashboard must still render correctly; the weak-area section must
  show a clear "couldn't load" state rather than the whole dashboard
  failing.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The dashboard MUST display per-topic mastery values for
  every topic in the learner's current subject's content artifact,
  including explicit "not yet assessed" for untouched topics.
- **FR-002**: The dashboard MUST trigger a fresh Recommendation Agent
  report on each load and display its flagged weak areas and next-step
  suggestions verbatim, including that agent's own uncertainty framing
  when applicable ("not enough data," "broad review needed") -- never
  paraphrased into false confidence.
- **FR-003**: The dashboard MUST display a path visualization consisting
  of: topics already assessed (with mastery level), the Sequencing
  Agent's current top-priority next topic, and a small set of likely
  upcoming topics derived from the prerequisite graph -- generated by
  consulting the Sequencing Agent's actual selection logic, not a
  separately invented ordering.
- **FR-004**: The path visualization's upcoming-topics section MUST
  carry a visible disclosure that it is illustrative and subject to
  change, never presented as a fixed, committed plan.
- **FR-005**: A learner with zero assessment history MUST see a coherent
  "just getting started" state -- every topic "not yet assessed," the
  weak-area section reflecting the Recommendation Agent's own
  insufficient-data framing, and the path visualization anchored on the
  subject's entry-level topics.
- **FR-006**: Dashboard data MUST be read fresh from the database on
  every load -- no indefinite caching, consistent with Milestone 1's
  FR-013 statelessness requirement.
- **FR-007**: If the Recommendation Agent's report fails to generate
  when the dashboard loads, the mastery-view portion MUST still render
  correctly, with a distinct, clear failure state for the weak-area
  section alone -- not a whole-dashboard failure.
- **FR-008**: The dashboard MUST work correctly for at least two
  subjects with zero engine-code changes beyond each subject's own
  content artifact, extending the same extensibility check pattern
  established in Milestone 1.

### Key Entities *(include if feature involves data)*

- **DashboardView**: a read-time composition of a learner's current
  `MasteryState`, the Recommendation Agent's freshly-generated
  `WeakAreaReport`, and a path visualization derived from the
  Sequencing Agent's current topic-graph traversal -- not persisted as
  its own stored entity, assembled fresh on each request.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a learner with assessment history, the dashboard's
  displayed per-topic mastery values match the underlying `MasteryState`
  exactly, with no drift beyond the current request.
- **SC-002**: Given a learner with zero assessment history, the
  dashboard renders the "just getting started" state without error.
- **SC-003**: The dashboard's weak-area section matches what a direct
  Recommendation Agent call would independently produce for the same
  mastery state, verified by comparing dashboard output to a direct
  agent call in an automated test.
- **SC-004**: 100% of dashboard renders including an "upcoming topics"
  section carry the illustrative/subject-to-change disclosure, verified
  by an automated content check (the same pattern as Milestone 1's
  simulated-behavior disclosure check).
- **SC-005**: The dashboard works correctly for at least two subjects
  with zero engine-code changes, verified by the extended extensibility
  check.

## Assumptions

- This milestone covers the learner-facing dashboard only. An
  instructor-facing dashboard (roster-wide, aggregate view) is a
  distinct extension of the instructor-classroom milestone, not built
  here, since it requires multi-learner roster infrastructure this
  milestone doesn't have.
- The dashboard does not introduce real-time push updates (e.g.
  WebSockets) -- each load computes fresh from current database state,
  consistent with the stateless Vercel deployment model. Acceptable
  staleness is "as of last page load," not continuously live.
- The path visualization shows illustrative upcoming topics only, never
  a committed multi-step plan, since the Sequencing Agent's actual
  decisions are made one at a time based on the latest mastery state at
  the moment each question is requested.
- This milestone depends on Milestone 1 (mastery state, content
  artifact) and the Recommendation Agent (weak-area reports). It does
  not require the personalization-evaluation harness, free-text
  grading, classroom features, the Tutor Agent, or multimodal support.

# Feature Specification: STEM-Career Connections

**Feature Branch**: `039-stem-career-connections`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "STEM-career connections surfaced alongside a topic, should be optional choice for user to turn on/off"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a real-world career tied to a topic (Priority: P1)

A learner viewing a topic (on their dashboard or wherever topic-level progress is shown) sees a short, real-world STEM career or application connected to that topic -- e.g. a linear-equations topic noting that civil engineers use the same equations to calculate load limits.

**Why this priority**: This is the entire value of the feature -- relevance that answers "why does this topic matter?" Without this, there is nothing to toggle.

**Independent Test**: Can be fully tested by viewing a topic that has an authored career connection, with the feature enabled, and confirming the connection displays correctly -- delivers the feature's core value on its own.

**Acceptance Scenarios**:

1. **Given** a topic has an authored career connection and the learner's preference has this feature enabled, **When** the learner views that topic, **Then** the career connection (career/field name plus a short explanation of the tie to the topic) is displayed alongside it.
2. **Given** a topic has no authored career connection yet, **When** the learner views that topic with the feature enabled, **Then** no career-connection section is shown for that topic and nothing else about the topic's display is affected.

---

### User Story 2 - Turn the feature on or off (Priority: P2)

A learner who finds the career callouts distracting, or who wants them back, can turn the feature off or back on from their own settings, and that choice sticks across future sessions until they change it again.

**Why this priority**: The request explicitly frames this as an optional, learner-controlled choice, not a permanent addition to every topic view -- without this control the feature is just always-on content, which is a different feature.

**Independent Test**: Can be fully tested by toggling the preference, reloading/returning in a later session, and confirming the display matches the last-set preference -- independently verifies the on/off control end to end.

**Acceptance Scenarios**:

1. **Given** the feature is enabled for a learner, **When** the learner turns it off, **Then** no career-connection content is displayed anywhere for that learner from that point forward.
2. **Given** a learner turned the feature off in a previous session, **When** they return in a new session without changing the setting, **Then** the feature remains off.
3. **Given** the feature is off, **When** the learner turns it back on, **Then** career connections resume displaying on topics that have them.

---

### User Story 3 - Real coverage across existing content (Priority: P3)

Every graded topic in the project's existing subjects has a real, accurate STEM-career connection authored for it, not placeholder text -- so a learner who enables the feature gets genuine value on any topic they visit, not gaps.

**Why this priority**: Lower priority than the mechanism itself (US1/US2) -- the toggle and display logic deliver value even with partial coverage -- but without real authored content the feature has nothing true to show, which matches the precedent set by Standards Alignment (spec 038) authoring real codes rather than shipping only the mechanism.

**Independent Test**: Can be fully tested by enumerating every graded topic across the existing subjects and confirming each has an authored, accurate career connection -- independent of the display/toggle mechanism already covered by US1/US2.

**Acceptance Scenarios**:

1. **Given** the full set of graded topics in the project's existing subjects, **When** each topic's authored content is reviewed, **Then** every one has a career connection naming a real STEM career/field and an accurate, non-fabricated explanation of the tie to that topic.

---

### Edge Cases

- A topic with no authored career connection yet (partial rollout, or a future subject added later) renders with that section simply absent -- never an error, placeholder box, or generic filler text.
- A learner who has never touched the setting sees the feature's default state (see Assumptions) rather than an unset/broken state.
- Turning the feature off takes effect immediately for that learner, without needing to leave and re-enter the page they're on.
- A demo learner account behaves identically to a real learner account for this preference -- no special-casing beyond the existing `is_demo` flag's normal handling.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support associating a real-world STEM-career or application connection with a topic, authored as content-artifact-level data alongside that topic's existing content (same pattern as the topic's other authored fields -- no subject-specific logic outside the content artifact itself).
- **FR-002**: Each career connection MUST include a named real-world career/field and a short, plain-language explanation of how that career uses or relates to the topic.
- **FR-003**: System MUST display a topic's career connection to a learner wherever that topic is currently surfaced to them (e.g. dashboard topic list), when the learner's preference for this feature is enabled.
- **FR-004**: System MUST let each learner independently turn this feature on or off for themselves.
- **FR-005**: A learner's on/off choice MUST persist across sessions until the learner changes it again.
- **FR-006**: When a learner's preference is off, System MUST NOT render any career-connection content or related UI element to that learner, anywhere.
- **FR-007**: A topic with no authored career connection MUST render without that section rather than an error, empty box, or placeholder text.
- **FR-008**: System MUST apply a default preference state for a learner who has never explicitly set one (see Assumptions for the chosen default).
- **FR-009**: This feature MUST NOT alter mastery calculation, sequencing, grading, or any other personalization/grading decision -- it is presentation-only.
- **FR-010**: System MUST have a real, accurate (non-placeholder) authored career connection for every graded topic in the project's existing subjects (`algebra-1`, `biology`) at feature completion.
- **FR-011**: The on/off control MUST be discoverable from a learner settings surface reachable from wherever topics are displayed to that learner.

### Key Entities

- **Career Connection**: A topic-level piece of authored content -- which topic it belongs to, a named real-world STEM career/field, and a short explanation tying that career to the topic. Zero or one per topic in this feature's scope; a topic with none simply has nothing to show.
- **Career Connections Preference**: A per-learner on/off setting controlling whether that learner sees career connections at all. Defaults per the Assumptions below when unset; persists until the learner changes it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A learner can change their career-connections preference in a single action (one click/tap) from a reachable settings surface, with the change visible immediately.
- **SC-002**: 100% of graded topics in the project's existing subjects (`algebra-1`, `biology`) display a real, accurate career connection when the feature is enabled.
- **SC-003**: A learner's preference persists correctly across 100% of subsequent sessions until they explicitly change it again.
- **SC-004**: With the preference off, 0% of a learner's topic views show any career-connection content or control chrome for it.

## Assumptions

- "User" in the feature request means the learner, not the instructor -- this is a personal, presentation-only preference with no bearing on mastery, grading, or classroom-level reporting, so it doesn't need instructor-level configuration the way grade bands or standards alignment do.
- Default preference state for a learner who hasn't set one is **on** -- the request frames this as content "surfaced alongside a topic" by default, with an explicit path to turn it *off* for a learner who doesn't want it, rather than content hidden until opted into.
- Career connections are surfaced wherever a learner currently views topic-level information (e.g. the Learner Dashboard's topic list), not injected into the active question-answering or quiz flow -- keeping assessment moments free of added content, consistent with Multimodal (Milestone 10) and Timed Practice (Milestone 20)'s precedent of keeping in-session UI minimal.
- Career-connection content is authored directly into the existing content-artifact files, the same way Standards Alignment (spec 038) wrote real standards codes as static authored data -- no new external careers API or dataset dependency.
- No grade-band-based filtering of career-connection content in this feature's scope; age-appropriateness is handled at authoring time (plain language, no jargon), not by a runtime rule -- consistent with there being no existing precedent for grade-filtering presentational content.
- Coverage (FR-010) is scoped to the project's two existing subjects' graded topics as they exist today; a future subject added later would need its own authoring pass, the same dependency Standards Alignment already established for its own tags.

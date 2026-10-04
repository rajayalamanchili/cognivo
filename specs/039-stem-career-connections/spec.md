# Feature Specification: STEM-Career Connections

**Feature Branch**: `039-stem-career-connections`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "STEM-career connections surfaced alongside a topic, should be optional choice for user to turn on/off"

## Clarifications

### Session 2026-10-04

- Q: Should the on/off preference be saved to the learner's account on the backend (so it follows them to any device/browser), or kept only in local browser storage on the device where they set it? → A: Backend-persisted -- a field tied to the learner's account, read/written via the backend so it follows the learner to any device they sign in from.
- Q: Where should the on/off control for this feature live -- a small toggle added to the existing learner dashboard, or a new dedicated learner settings page? → A: A new dedicated learner settings page, reachable from the learner's existing account/avatar icon, styled consistent with the project's existing learner-facing UI.
- Q: This project has no real-learner login -- the dashboard/practice/mastery/tutor flow is hardcoded to the single, shared, unauthenticated seeded demo learner; a real (guardian-managed) learner never signs in and only ever appears in their guardian's read-only views. Given that, who actually gets this preference: the demo learner only, the guardian (on behalf of each real learner they manage), or both? → A: Both -- the demo learner gets a self-service toggle (via its existing avatar menu); a guardian also gets a per-real-learner toggle in their own "My Learners" UI, on behalf of each real learner they manage.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a real-world career tied to a topic (Priority: P1)

Wherever a topic is currently shown to whoever is looking at that learner's progress -- the demo learner's own dashboard, or a guardian's view of a real learner they manage -- a short, real-world STEM career or application connected to that topic is shown alongside it, e.g. a linear-equations topic noting that civil engineers use the same equations to calculate load limits.

**Why this priority**: This is the entire value of the feature -- relevance that answers "why does this topic matter?" Without this, there is nothing to toggle.

**Independent Test**: Can be fully tested by viewing a topic that has an authored career connection, with the feature enabled, and confirming the connection displays correctly -- delivers the feature's core value on its own.

**Acceptance Scenarios**:

1. **Given** a topic has an authored career connection and a learner's preference has this feature enabled, **When** that topic is viewed (on the demo learner's dashboard, or on a guardian's view of a real learner), **Then** the career connection (career/field name plus a short explanation of the tie to the topic) is displayed alongside it.
2. **Given** a topic has no authored career connection yet, **When** that topic is viewed with the feature enabled, **Then** no career-connection section is shown for that topic and nothing else about the topic's display is affected.

---

### User Story 2 - Turn the feature on or off (Priority: P2)

For the demo learner -- the only learner with a self-service dashboard session in this project today -- whoever finds the career callouts distracting, or wants them back, can turn the feature off or back on from a new settings page reachable from the demo learner's existing avatar menu, and that choice sticks across future visits until changed again.

For a real, guardian-managed learner -- who has no login or dashboard session of their own -- the learner's guardian turns the feature on or off for that learner from the guardian's existing "My Learners" page, and that choice sticks the same way until the guardian changes it again.

**Why this priority**: The request explicitly frames this as an optional, controllable choice, not a permanent addition to every topic view -- without this control the feature is just always-on content, which is a different feature. Covering both actors matters because this project's only directly-learner-operated UI is the shared demo learner; a real learner's preference can only ever be set by the guardian who manages them.

**Independent Test**: Can be fully tested, for each actor independently, by toggling the preference, returning in a later visit/session, and confirming the display matches the last-set preference -- independently verifies both on/off controls end to end.

**Acceptance Scenarios**:

1. **Given** the feature is enabled for the demo learner, **When** a visitor in the demo-learner flow turns it off from the demo learner's settings page, **Then** no career-connection content is displayed anywhere in that flow from that point forward.
2. **Given** the demo learner's feature was turned off in a previous visit, **When** a visitor returns to the demo-learner flow without anyone changing the setting, **Then** the feature remains off.
3. **Given** a real learner's feature is enabled, **When** that learner's guardian turns it off from "My Learners," **Then** no career-connection content is displayed anywhere that learner's data is shown (including the guardian's own view of that learner).
4. **Given** the feature is off for either actor, **When** that actor turns it back on, **Then** career connections resume displaying on topics that have them.

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
- A learner (demo or real) whose preference was never explicitly set sees the feature's default state (see Assumptions) rather than an unset/broken state.
- Turning the feature off takes effect immediately -- for the demo learner, without needing to leave and re-enter the page they're on; for a real learner, the next time that learner's data is shown to their guardian.
- A guardian managing more than one real learner can set this preference independently per learner -- turning it off for one does not affect another.
- A guardian who is not the owning guardian of a given real learner (per the existing `require_learner_ownership_if_real` ownership rule) cannot read or change that learner's preference.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support associating a real-world STEM-career or application connection with a topic, authored as content-artifact-level data alongside that topic's existing content (same pattern as the topic's other authored fields -- no subject-specific logic outside the content artifact itself).
- **FR-002**: Each career connection MUST include a named real-world career/field and a short, plain-language explanation of how that career uses or relates to the topic.
- **FR-003**: System MUST display a topic's career connection wherever that topic's progress is currently surfaced for a learner whose preference is enabled -- the demo learner's own dashboard, and a guardian's view of a real learner they manage.
- **FR-004**: For the demo learner, System MUST let whoever is in that flow turn the feature on or off via the demo learner's own settings page. For a real learner, System MUST let that learner's owning guardian turn the feature on or off on the learner's behalf, from the guardian's "My Learners" page.
- **FR-005**: A preference choice MUST be saved on the affected learner's own record on the backend, so it persists across sessions -- for the demo learner, across any visit to the demo flow; for a real learner, across any session where that learner's guardian is signed in -- until changed again.
- **FR-006**: When a learner's preference is off, System MUST NOT render any career-connection content or related UI element anywhere that learner's topics are shown, including a guardian's view of a real learner.
- **FR-007**: A topic with no authored career connection MUST render without that section rather than an error, empty box, or placeholder text.
- **FR-008**: System MUST apply a default preference state for a learner who has never explicitly set one (see Assumptions for the chosen default).
- **FR-009**: This feature MUST NOT alter mastery calculation, sequencing, grading, or any other personalization/grading decision -- it is presentation-only.
- **FR-010**: System MUST have a real, accurate (non-placeholder) authored career connection for every graded topic in the project's existing subjects (`algebra-1`, `biology`) at feature completion.
- **FR-011**: System MUST provide a new settings page for the demo learner, reachable from the demo learner's existing avatar menu, that hosts its on/off control and visually matches the project's existing learner-facing UI design system (Learner-Facing UI Redesign, spec 027). A real learner's control needs no new page -- it is added to the guardian's existing "My Learners" page, one control per learner the guardian manages.

### Key Entities

- **Career Connection**: A topic-level piece of authored content -- which topic it belongs to, a named real-world STEM career/field, and a short explanation tying that career to the topic. Zero or one per topic in this feature's scope; a topic with none simply has nothing to show.
- **Career Connections Preference**: A per-learner on/off setting controlling whether career connections show for that learner's topics, saved on that learner's own backend record. Set directly by the demo learner (self-service, unauthenticated, one shared record) or by a guardian on behalf of each real learner they manage (the only existing write-access pattern for real-learner data). Defaults per the Assumptions below when unset; persists until changed again.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The demo learner's preference can be reached from the avatar menu and changed in a single action (one click/tap), with the change visible immediately; a guardian can likewise change a real learner's preference in a single action from "My Learners," visible immediately in the guardian's own view of that learner.
- **SC-002**: 100% of graded topics in the project's existing subjects (`algebra-1`, `biology`) display a real, accurate career connection when the feature is enabled.
- **SC-003**: A preference persists correctly across 100% of subsequent sessions/visits for the affected learner until explicitly changed again.
- **SC-004**: With a learner's preference off, 0% of that learner's topic views (wherever shown) display any career-connection content or control chrome for it.

## Assumptions

- "User" in the feature request means the learner, not the instructor -- this is a personal, presentation-only preference with no bearing on mastery, grading, or classroom-level reporting, so it doesn't need instructor-level configuration the way grade bands or standards alignment do. Since this project has no real-learner login (Clarifications), "the learner" controlling it is either the demo learner directly or, for a real learner, the guardian who manages them -- not the instructor either way.
- Default preference state for a learner who hasn't set one is **on** -- the request frames this as content "surfaced alongside a topic" by default, with an explicit path to turn it *off* for whoever doesn't want it, rather than content hidden until opted into.
- Career connections are surfaced wherever a learner's topic-level information is currently shown (the demo learner's own dashboard topic list, or a guardian's view of a real learner), not injected into the active question-answering or quiz flow -- keeping assessment moments free of added content, consistent with Multimodal (Milestone 10) and Timed Practice (Milestone 20)'s precedent of keeping in-session UI minimal.
- Career-connection content is authored directly into the existing content-artifact files, the same way Standards Alignment (spec 038) wrote real standards codes as static authored data -- no new external careers API or dataset dependency.
- No grade-band-based filtering of career-connection content in this feature's scope; age-appropriateness is handled at authoring time (plain language, no jargon), not by a runtime rule -- consistent with there being no existing precedent for grade-filtering presentational content.
- Coverage (FR-010) is scoped to the project's two existing subjects' graded topics as they exist today; a future subject added later would need its own authoring pass, the same dependency Standards Alignment already established for its own tags.

# Feature Specification: Instructor-Assigned Quizzes

**Feature Branch**: `011-instructor-assigned-quizzes`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "milestone 8"

## Clarifications

### Session 2026-08-23

- Q: No real-learner login exists yet -- only guardian and instructor
  sessions (`backend/src/services/auth/dependencies.py`), and the
  existing quiz-start endpoint currently hardcodes the demo learner.
  How should a real, roster-enrolled learner actually start/continue an
  assigned quiz? → A: Guardian-mediated -- the learner never logs in
  directly; their guardian's existing session starts/continues the quiz
  on the learner's behalf, consistent with spec 009's guardian-holds-
  credentials model for minors. No new account type or auth flow.
- Q: Can a learner attempt an assigned quiz more than once, and does the
  due date block starting a new attempt once it has passed? → A: Single
  attempt per learner per assignment; starting is blocked once the due
  date passes, though an already-in-progress attempt may still finish.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instructor assigns a quiz to a chosen subset of a roster (Priority: P1)

An instructor picks one or more topics, a question count, and optionally
a due date, then assigns that quiz configuration to some or all of the
learners enrolled in one of their rosters. The assignment is saved and
becomes visible to the instructor as pending for each targeted learner.

**Why this priority**: This is the entire point of the milestone --
without the ability to configure and target an assignment, nothing else
in this feature has anything to act on.

**Independent Test**: An instructor with an existing roster (per
Milestone 7) selects a subset of enrolled learners, configures topic(s)
and question count, and confirms the assignment now appears, targeted
at exactly those learners, without needing any other part of this
feature to exist yet.

**Acceptance Scenarios**:

1. **Given** an instructor viewing one of their rosters, **When** they
   configure a quiz (topic(s), question count, optional due date) and
   select a subset of enrolled learners, **Then** an assignment is
   created targeting exactly the selected learners.
2. **Given** an instructor configuring an assignment, **When** they
   select "all" instead of a subset, **Then** the assignment targets
   every learner currently enrolled in that roster.
3. **Given** an instructor who does not own a given roster, **When**
   they attempt to create an assignment for it, **Then** the system
   rejects the request.
4. **Given** an assignment has already been created, **When** a new
   learner is later enrolled in that roster, **Then** that learner is
   **not** retroactively added to the existing assignment's target list.

---

### User Story 2 - A guardian starts an assigned quiz on behalf of their learner (Priority: P1)

The guardian of a learner targeted by an assignment starts and (if
needed, across separate visits) continues that quiz on the learner's
behalf, from within the guardian's own existing session -- the learner
never logs in directly (per Clarifications). The quiz itself behaves
exactly like the learner-initiated adaptive-difficulty quiz established
in Milestone 5 -- difficulty adapts within the session, it reaches a
defined completion state with a score, and every answered question
updates the learner's persistent mastery state through the same
mechanism a non-assigned quiz already uses.

**Why this priority**: An assignment nobody can ever actually take is
not a usable feature -- this is the other half of the milestone's core
value, and it depends on Milestone 5's existing quiz mechanism being
reused unchanged rather than duplicated.

**Independent Test**: Given a learner targeted by an existing
assignment, confirm their guardian can start it from the guardian's own
session, that its adaptive-difficulty behavior and mastery-state
updates are indistinguishable from a learner-initiated quiz on the same
topic(s), and that the attempt is recorded against that specific
assignment.

**Acceptance Scenarios**:

1. **Given** a learner targeted by an assignment, **When** their
   guardian starts it from the guardian's own session, **Then** a quiz
   session begins using the assignment's configured topic(s) and
   question count, with the same adaptive-difficulty behavior as any
   other quiz.
2. **Given** an assigned quiz in progress, **When** the guardian
   completes it, **Then** every answered question has already updated
   the learner's mastery state via the exact same mechanism as a
   non-assigned quiz (no separate/new grading or mastery-update logic).
3. **Given** a learner who is **not** targeted by a given assignment
   (not enrolled in the roster, or enrolled but not selected), **When**
   any guardian attempts to start it on that learner's behalf, **Then**
   the system rejects the attempt.
4. **Given** a guardian who is not the targeted learner's own guardian,
   **When** they attempt to start or continue that learner's assignment
   attempt, **Then** the system rejects the request.
5. **Given** a learner has already completed their single attempt at an
   assignment, **When** their guardian tries to start it again, **Then**
   the system rejects the request.
6. **Given** an assignment's due date has passed and the targeted
   learner never started it, **When** their guardian attempts to start
   it, **Then** the system rejects the request; an attempt already in
   progress before the due date passed is allowed to finish.

---

### User Story 3 - Instructor reviews per-student assignment results (Priority: P2)

An instructor opens their dashboard and sees, for a given assignment,
each targeted learner's individual status (not started / in progress /
completed / ended early) and score, broken out per student rather than
collapsed into a single class-wide number.

**Why this priority**: Assigning work an instructor can't then check on
delivers little value on its own -- but it strictly depends on User
Stories 1 and 2 having something to report on, so it's sequenced after
both.

**Independent Test**: Given an assignment with a mix of learners who
have completed it, started it, and not touched it at all, confirm the
instructor's dashboard shows the correct distinct status and score (if
any) for each of those learners individually.

**Acceptance Scenarios**:

1. **Given** an assignment where some targeted learners have completed
   it and others have not started, **When** the instructor views the
   assignment, **Then** each targeted learner's individual status and
   score (if completed) is shown separately.
2. **Given** an assignment past its due date with learners who never
   started it, **When** the instructor views the assignment, **Then**
   those learners are clearly distinguishable from ones who completed it
   on time.

---

### Edge Cases

- What happens when an instructor deletes/cancels an assignment that no
  learner has started yet, versus one where some learners are mid-quiz
  or already completed? (Completed attempts and their mastery-state
  updates must never be retracted; in-progress attempts should be
  allowed to finish or be explicitly ended, not silently orphaned.)
- What happens when a learner is unenrolled from the roster (Milestone
  7's existing unenrollment flow) after being targeted by an assignment
  but before starting it? They should no longer be able to start it.
- What happens when an instructor targets zero learners? The system
  should reject assignment creation rather than create a no-op
  assignment.
- What happens when the due date passes while a learner is mid-quiz?
  The in-progress attempt is allowed to finish; see Clarifications for
  whether a *new* attempt can start after the due date.
- What happens when a roster has no learners enrolled at all? "Assign to
  all" should be unavailable/rejected rather than silently creating an
  empty-target assignment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow an instructor to configure a quiz
  assignment specifying one or more topics, a question count, and
  optionally a due date, scoped to one of their own rosters.
- **FR-002**: The system MUST allow the instructor to target the
  assignment at either a specific chosen subset of the roster's
  currently-enrolled learners, or all of them.
- **FR-003**: The system MUST reject assignment creation if the
  resulting target-learner list would be empty.
- **FR-004**: The system MUST reject any attempt to create, view,
  modify, or cancel an assignment for a roster the requesting instructor
  does not own.
- **FR-005**: The system MUST fix an assignment's target-learner list at
  creation time; learners enrolled in the roster afterward are not
  retroactively added to that assignment.
- **FR-006**: The system MUST allow only the guardian of a learner
  targeted by a given assignment to start or continue that learner's
  attempt at it, acting from the guardian's own existing session (the
  learner does not authenticate directly).
- **FR-007**: An assigned quiz's in-session difficulty adaptation MUST
  use the exact same mechanism Milestone 5 established for
  learner-initiated quizzes -- no new or modified difficulty-adaptation
  logic.
- **FR-008**: Every answered question within an assigned quiz MUST
  update the learner's persistent mastery state through the exact same
  grading and mastery-update mechanism already used for a
  learner-initiated quiz (Milestones 5 and 6) -- no new grading logic
  path.
- **FR-009**: The system MUST record which assignment a given quiz
  attempt belongs to, so results can be reported per assignment.
- **FR-010**: The instructor dashboard MUST show, for a given
  assignment, each targeted learner's individual status (not started /
  in progress / completed / ended early) and score if completed --
  never only a class-wide aggregate.
- **FR-011**: The system MUST prevent a learner who is unenrolled from
  the roster after being targeted from starting or continuing an
  assignment attempt they had not already completed.
- **FR-012**: The system MUST NOT retract or alter a learner's
  already-recorded mastery-state updates when an instructor cancels an
  assignment.
- **FR-013**: The system MUST require the requester starting or
  continuing an assigned-quiz attempt to be authenticated as the
  targeted learner's own guardian; no separate learner-facing login or
  session exists for this milestone.
- **FR-014**: The system MUST allow at most one attempt per learner per
  assignment, and MUST reject any request to start a new attempt after
  the assignment's due date has passed -- an attempt already in
  progress before the due date passed MAY continue to completion.

### Key Entities *(include if feature involves data)*

- **Quiz Assignment**: An instructor-configured, roster-scoped quiz
  definition (topic(s), question count, optional due date) plus a fixed
  list of targeted learners, created at a point in time by a specific
  instructor.
- **Assignment Attempt**: The link between a specific targeted learner's
  quiz session (Milestone 5's existing quiz mechanism) and the
  assignment it counts toward, carrying that learner's status and score
  for reporting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An instructor can configure and assign a quiz to a chosen
  subset (or all) of a roster's learners in a single guided flow,
  without needing to leave the roster/dashboard context.
- **SC-002**: 100% of assigned-quiz completions update the targeted
  learner's mastery state, verified to go through the identical
  mechanism a learner-initiated quiz already uses -- zero new grading or
  mastery-update code paths introduced.
- **SC-003**: For every assignment, the instructor dashboard shows a
  distinct status for 100% of targeted learners individually, never
  collapsing results into a single class-wide number.
- **SC-004**: Zero learners outside an assignment's targeted list (or no
  longer enrolled in the roster) are able to start, continue, or appear
  in that assignment's results.
- **SC-005**: An instructor can distinguish, for any assignment past its
  due date, which targeted learners completed it on time versus never
  started, without manual cross-referencing.

## Assumptions

- This milestone reuses Milestone 5's adaptive-difficulty quiz mechanism
  and Milestone 6's grading/mastery-update mechanism entirely unchanged;
  its own scope is limited to assignment configuration, targeting, and
  per-student reporting, per the roadmap's explicit framing ("this
  milestone introduces no new grading logic, only assignment and
  reporting").
- The instructor dashboard's per-assignment, per-student breakout
  extends the existing roster dashboard built in Milestone 7 (which
  already aggregates Milestone 2's Recommendation Agent output per
  learner) rather than introducing a separate reporting surface.
- Only the roster's owning instructor may create, view, modify, or
  cancel assignments for that roster, mirroring the instructor-owns-
  roster authorization pattern already established in Milestone 7's
  dashboard endpoint.
- Quiz templates or reuse of an assignment's configuration across future
  terms/semesters is out of scope (explicitly deferred by the roadmap).
- An assignment, once created, is not editable in place (topics,
  question count, or target list) -- an instructor who needs to change
  those cancels it and creates a new one. This keeps "what a learner was
  actually assigned" unambiguous for reporting (FR-012) without needing
  a versioning scheme this milestone doesn't otherwise require.

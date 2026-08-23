# Feature Specification: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review

**Feature Branch**: `010-instructor-classroom`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "milestone 7"

## Clarifications

### Session 2026-08-23

- Q: Once a learner is enrolled in a roster, is there a way to remove them from just that roster (unenrollment) without deleting their whole account? → A: Yes -- both a guardian (removing their child from a roster they no longer want them in) and an instructor (removing a learner from their own roster, e.g. end of term) can unenroll a learner. This only removes the `Enrollment` link; it never triggers a spec 009 `DeletionRequest` or touches the learner's account/data.
- Q: Can the same person hold both a guardian account and an instructor account (e.g. a parent who is also a teacher), and can they share one email across both? → A: Yes -- `RealGuardianAccount` and `RealInstructorAccount` are separate account universes; email uniqueness is enforced independently within each, not globally across both. The same email can register once as a guardian and once as an instructor.

This is Milestone 7 proper -- the auth/rosters/dashboard/content-review
work that `specs/009-privacy-retention/spec.md` (Constitution Principle
VIII's prerequisite gate) explicitly gated on being approved first. That
condition is met (009 merged 2026-08-23). This spec builds directly
against 009's approved policy and forward-looking data model
(`RealGuardianAccount`, `RealLearnerAccount`, `RealInstructorAccount`,
`ClassroomRoster`, `DeletionRequest`, `RetentionRecord`) rather than
re-deriving account/consent/retention rules -- see this spec's
Assumptions for exactly which of 009's requirements this milestone is
responsible for actually implementing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An instructor and a guardian can each create an account and sign in (Priority: P1)

A prospective instructor registers an account with their own
credentials. A prospective guardian registers an account with their
own credentials and adds one or more of their children as learner
profiles. Both can subsequently sign in, stay signed in across
requests, and sign out.

**Why this priority**: Every other user story requires an authenticated
identity to act as. Without this, nothing else in this spec is
reachable.

**Independent Test**: Register a new instructor account and a new
guardian account, sign in as each, confirm the session persists across
a page reload/subsequent request, sign out, confirm the session no
longer grants access.

**Acceptance Scenarios**:

1. **Given** no existing account, **When** a prospective instructor
   registers with an email and password, **Then** a `RealInstructorAccount`
   is created (spec 009's data model) and they are signed in.
2. **Given** no existing account, **When** a prospective guardian
   registers, **Then** a `RealGuardianAccount` is created and they can
   add a `RealLearnerAccount` child profile under it (spec 009 FR-003 --
   the guardian, never the learner, controls the credential).
3. **Given** a signed-in instructor or guardian, **When** they sign out,
   **Then** subsequent requests requiring authentication are rejected
   until they sign in again.

---

### User Story 2 - An instructor creates a classroom roster; a guardian enrolls their child into it (Priority: P1)

An instructor creates a roster scoped to one subject (matching this
platform's per-subject content model), choosing open or closed
enrollment (spec 009 FR-003a). A guardian enrolls one of their learner
profiles into a roster -- immediately for an open roster via its join
code, or via a pending request an instructor must approve for a closed
roster.

**Why this priority**: The roster is the access-control boundary every
later user story (dashboard, content review) scopes against -- it has
to exist before there's anything to aggregate or review.

**Independent Test**: As an instructor, create one open and one closed
roster. As a guardian, join the open roster directly via its code;
submit a request to the closed roster and confirm it stays pending
until the instructor approves it.

**Acceptance Scenarios**:

1. **Given** an authenticated instructor, **When** they create a roster
   for a chosen subject with `enrollment_mode: open`, **Then** a join
   code is generated and any guardian holding that code can enroll a
   learner immediately.
2. **Given** an authenticated instructor, **When** they create a roster
   with `enrollment_mode: closed`, **Then** a guardian's join attempt
   creates a pending request that only completes enrollment once the
   instructor approves it.
3. **Given** a pending closed-roster join request, **When** the
   instructor declines it, **Then** the learner is not enrolled and the
   guardian is informed.
4. **Given** an enrollment completes (either mode), **When** the
   resulting `RetentionRecord` is inspected, **Then** it records the
   correct authorizing party -- the guardian for an open join, the
   instructor for a closed approval (spec 009 FR-011).
5. **Given** an enrolled learner, **When** either the guardian or the
   owning instructor unenrolls them, **Then** the `Enrollment` link is
   removed and the learner immediately stops appearing in that
   roster's dashboard or content-review queue -- their account and all
   other data are untouched.

---

### User Story 3 - An instructor sees a class-wide weak-area view, aggregated from each learner's own report (Priority: P1)

An instructor selects one of their rosters and sees, for every enrolled
learner, that learner's current weak-area report -- computed by calling
the same per-learner Recommendation Agent output every learner already
sees individually (Milestone 2), never a second, separately-implemented
weak-area classification.

**Why this priority**: This is the milestone's core value proposition
per `roadmap.md`'s own framing -- everything else (auth, rosters) exists
to make this view possible and correctly scoped.

**Independent Test**: Enroll two learners with different mastery
histories into one roster; confirm the instructor's dashboard shows
each learner's weak areas exactly matching what `GET /api/learners/
{learner_id}/recommendations` returns for that learner directly, with
no discrepancy.

**Acceptance Scenarios**:

1. **Given** a roster with enrolled learners, **When** the instructor
   opens its dashboard, **Then** each learner's weak-area data is
   byte-for-byte the same as calling that learner's own recommendations
   endpoint (no separate aggregation logic re-deriving weak areas).
2. **Given** a learner with insufficient assessment history, **When**
   the instructor views the dashboard, **Then** that learner is shown
   with an explicit "insufficient data" indicator, never omitted or
   shown as an error.
3. **Given** two instructors with non-overlapping rosters, **When**
   instructor A views their dashboard, **Then** no learner belonging to
   instructor B's roster appears anywhere in it (spec 009 FR-006).

---

### User Story 4 - An instructor reviews and resolves flagged questions from their own roster's learners (Priority: P2)

A question a learner flagged (Milestone 1's existing flag mechanism,
FR-011) as wrong or broken currently has no owner to act on it. An
instructor sees every flagged question belonging to a learner on one of
their own rosters and resolves each one.

**Why this priority**: Important for content quality, but the platform
functions without it (a flagged question is already excluded from
future selection) -- lower priority than the auth/roster/dashboard
spine everything else depends on.

**Independent Test**: Flag a question via the existing learner-facing
flag endpoint; confirm it appears in the owning instructor's review
queue and disappears once resolved.

**Acceptance Scenarios**:

1. **Given** a flagged question belonging to a learner on the
   instructor's roster, **When** the instructor opens their content-
   review queue, **Then** that question appears with its flag reason
   and the learner's submitted context.
2. **Given** a flagged question belonging to a learner *not* on any of
   the instructor's rosters, **When** that instructor views their
   queue, **Then** it never appears there (spec 009 FR-006's
   access-control principle extended to content review).
3. **Given** an instructor resolves a flagged question, **When** the
   resolution is recorded, **Then** a distinct, audited event captures
   which instructor resolved it, when, and what action was taken
   (Constitution Principle V).

---

### User Story 5 - A visitor can try the instructor and student classroom experience without signing up (Priority: P2)

A seeded demo instructor account and at least one seeded demo student
account, reachable only via a dedicated "View Demo" entry point, let a
visitor experience the classroom features without creating a real
account.

**Why this priority**: Important for the live deployment's demoability
(Constitution Principle IX), but the real, non-demo flows (Stories 1-4)
are the substance of this milestone -- the demo accounts are a
presentation layer over them.

**Independent Test**: From the product's home page, reach the demo
classroom experience without ever passing through real sign-up;
confirm the demo instructor's and demo student's data resets to a
known-good state on schedule.

**Acceptance Scenarios**:

1. **Given** the product's home page, **When** a visitor selects the
   demo entry point, **Then** they land in a fully-functional instructor
   (or student) view without ever creating a real account.
2. **Given** the real sign-up flow, **When** any user completes it,
   **Then** the resulting account never has `is_demo: true` (spec 009
   FR-007/FR-008, now exercised against a real, live sign-up flow for
   the first time).

---

### Edge Cases

- What happens when a guardian tries to join a closed roster twice
  while their first request is still pending? (The second attempt must
  not create a duplicate pending request -- it either no-ops or
  surfaces the existing pending status.)
- What happens when an instructor deletes a roster that still has
  enrolled learners? (Per spec 009's Edge Cases, learner data outlives
  roster/instructor deletion -- the enrollment link is removed, but
  enrolled learners' own accounts and data are untouched.)
- What happens when a guardian submits a deletion request (spec 009
  FR-004) for a learner mid-enrollment in an active roster? (The
  enrollment link is removed as part of the same cascade -- spec 009
  FR-005 already requires roster membership to be included in a
  deletion's cascade.)
- What happens when an instructor's content-review queue is empty?
  (Shown as a clear empty state, not an error or omission.)
- What happens when a learner is flagged as having insufficient data
  for every topic in a subject? (Matches the existing recommendations
  endpoint's own `broad_review_needed`/`data_sufficiency` handling --
  the dashboard surfaces it, doesn't reinterpret it.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A prospective instructor MUST be able to self-register a
  `RealInstructorAccount` (spec 009) with their own credentials -- no
  guardian or institution approval is required to create the account
  itself (only *enrolling a learner* is gated, per spec 009 FR-003a).
- **FR-002**: A prospective guardian MUST be able to self-register a
  `RealGuardianAccount` (spec 009 FR-003) and add one or more
  `RealLearnerAccount` child profiles under it.
- **FR-002a**: Email uniqueness is enforced independently within
  `RealGuardianAccount` and within `RealInstructorAccount` -- not
  globally across both. The same person (and the same email address)
  may hold one of each, since the two are separate account universes
  with no shared identity table.
- **FR-003**: The system MUST authenticate a returning instructor or
  guardian via their credentials and maintain their authenticated
  session across subsequent requests until sign-out or session expiry.
  Since one email may correspond to both a guardian and an instructor
  account (FR-002a), sign-in MUST resolve which account type the
  credentials refer to without ambiguity (e.g. the sign-in flow itself
  is entered separately for each role, or the same credentials
  disambiguate to whichever single account type they were registered
  under in that flow).
- **FR-004**: An authenticated instructor MUST be able to create a
  `ClassroomRoster` scoped to exactly one subject (matching this
  platform's per-subject content/mastery model), choosing `open` or
  `closed` enrollment mode at creation time (spec 009 FR-003a).
- **FR-005**: For an `open` roster, a guardian submitting the roster's
  join code MUST enroll their chosen learner immediately, recording the
  guardian as the authorizing party (spec 009 FR-011).
- **FR-006**: For a `closed` roster, a guardian's join attempt MUST
  create a pending request that only completes enrollment once the
  owning instructor approves it, recording the instructor as the
  authorizing party (spec 009 FR-011); a decline MUST leave the learner
  unenrolled.
- **FR-007**: A learner MAY be enrolled in more than one roster
  simultaneously (e.g. different subjects, different instructors) --
  enrollment is many-to-many, per spec 009's data model.
- **FR-007a**: A guardian MUST be able to unenroll their own learner
  from a roster, and an instructor MUST be able to unenroll a learner
  from their own roster -- either action removes only the `Enrollment`
  link, never the learner's account or any other data (distinct from a
  spec 009 `DeletionRequest`).
- **FR-008**: An authenticated instructor MUST be able to view a
  dashboard, scoped to one roster they own at a time, listing every
  currently-enrolled learner's weak-area report -- computed by invoking
  the existing per-learner `GET /api/learners/{learner_id}/recommendations`
  once per enrolled learner (Milestone 2's Recommendation Agent),
  never a second, separately-implemented weak-area classification.
- **FR-009**: The dashboard MUST display a learner for whom the
  underlying report indicates insufficient data with an explicit
  indicator, never as an error and never by omitting that learner.
- **FR-010**: An instructor MUST never see any learner, roster, or
  weak-area data belonging to another instructor's roster (spec 009
  FR-006), enforced server-side.
- **FR-011**: An authenticated instructor MUST be able to view every
  flagged (`validation_status: flagged`) question belonging to a
  learner enrolled in one of that instructor's own rosters, and MUST
  NOT be able to see a flagged question belonging to a learner outside
  their roster(s).
- **FR-012**: For each flagged question, the instructor MUST be able to
  resolve it by marking it either reactivated (the question returns to
  normal selection eligibility) or permanently rejected (the question
  is never selected again) -- editing a flagged question's own content
  is out of scope for this milestone (see Assumptions).
- **FR-013**: Resolving a flagged question MUST record a distinct,
  audited event capturing the resolving instructor's identity, the
  action taken, and a timestamp (Constitution Principle V).
- **FR-014**: The system MUST seed at least one demo instructor account
  and at least one demo student account, each carrying `is_demo: true`
  (spec 009 FR-007), reachable only via a dedicated demo entry point
  separate from real sign-up.
- **FR-015**: The demo instructor's and demo student's data MUST reset
  to a known-good seeded state on the schedule `tech-stack.md` defines
  (spec 009 FR-009), independent of real accounts' retention rules.
- **FR-016**: The real sign-up flow (instructor or guardian) MUST NOT
  accept any client-supplied value that could set `is_demo: true` --
  verified by an automated integration test that attempts exactly that
  and confirms it's rejected or silently ignored, never honored.

### Key Entities *(include if feature involves data)*

Extends spec 009's `data-model.md` (`RealGuardianAccount`,
`RealLearnerAccount`, `RealInstructorAccount`, `ClassroomRoster`,
`DeletionRequest`, `RetentionRecord`) with the entities below.
`RealLearnerAccount` here names the concept (a real learner's account,
guardian-controlled per FR-002) -- see this feature's own
`data-model.md` for how planning found that concept must actually be
*implemented* (extending the existing learner-profile table in place,
not a new one), a physical-schema detail this spec deliberately doesn't
dictate.

- **ClassroomRoster.subject_id** (extends spec 009's entity): the one
  subject this roster is scoped to -- added here since spec 009 left
  this field undetermined pending this milestone's own design.
- **Enrollment**: The many-to-many link between a `RealLearnerAccount`
  and a `ClassroomRoster` spec 009 mentioned but didn't model in
  detail. Carries `enrolled_at` and which `RetentionRecord` authorized
  it. Removable by either the guardian or the owning instructor
  (FR-007a's unenrollment) -- removal deletes only this link, never the
  `RealLearnerAccount` it referenced.
- **EnrollmentRequest**: A closed roster's pending guardian join
  request -- `learner_id`, `roster_id`, `requested_at`,
  `decided_at`/`decision` (approved/declined), distinct from
  `Enrollment` itself since a request can be declined and never become
  one.
- **DemoInstructorProfile**: The seeded demo instructor, structurally
  parallel to Milestone 1's `DemoLearnerProfile` (an `is_demo` flag, no
  real credential-holder relationship needed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of an instructor dashboard's per-learner weak-area
  data is identical to that same learner's own individual
  recommendations-endpoint response -- zero discrepancies across a test
  suite covering multiple learners and rosters.
- **SC-002**: Across a cross-tenant test suite of at least 2 instructors
  with non-overlapping rosters, 0 of the tested read paths (dashboard,
  roster list, content-review queue) ever return another instructor's
  data.
- **SC-003**: 100% of flagged questions belonging to an instructor's
  roster are resolvable from their content-review queue, with 0 left
  permanently un-actionable.
- **SC-004**: 100% of real accounts created via the sign-up flow have
  `is_demo: false`, verified by an automated test attempting to force
  `is_demo: true` and confirming it never succeeds.
- **SC-005**: The demo instructor and demo student accounts reset to
  their known-good seeded state on schedule with 0 drift incidents
  across a monitoring window.
- **SC-006**: Milestones 1-6's full test suites still pass unmodified.
- **SC-007**: 100% of unenroll actions (FR-007a) remove exactly the
  `Enrollment` link, with zero observed side effects on the learner's
  account, mastery state, or history across a test suite.

## Assumptions

- **Review action scope (resolved, not authoring)**: "Content review"
  in this milestone means triaging already-flagged AI-generated
  questions (reactivate or permanently reject) -- it does NOT include
  letting an instructor author brand-new questions from scratch or edit
  a flagged question's own text. `roadmap.md`'s phrase "content-
  authoring and review workflow" is interpreted here as authoring
  *the review decision* (the resolution action itself), not authoring
  new question content -- a full authoring UI is a materially larger,
  distinct feature this milestone's own DoD doesn't require, and isn't
  named as in-scope anywhere else in `roadmap.md`. Revisit as its own
  future milestone if instructor-authored content becomes a real need.
- **Roster is single-subject**: A `ClassroomRoster` is scoped to
  exactly one subject, matching how the recommendations endpoint and
  this platform's content model are already organized per-subject --
  an instructor teaching multiple subjects creates one roster per
  subject rather than one multi-subject roster (matches how a real
  teacher's class periods are usually subject-specific).
- **A learner may belong to multiple rosters**: Consistent with spec
  009's data model describing enrollment as many-to-many; a real
  student plausibly has multiple subjects/instructors.
- **An instructor may own multiple rosters**: The dashboard is scoped
  to one selected roster at a time (standard multi-class teacher
  workflow), not an all-rosters-merged view.
- **Auth mechanism is a plan.md/tech-stack.md decision**: This spec
  describes authentication *behavior* (register, sign in, maintain a
  session, sign out) without dictating the specific mechanism (session
  cookie, JWT, third-party provider) -- `tech-stack.md` explicitly
  deferred that choice to this milestone's planning phase.
- **Password reset/forgot-password** uses a standard email-link flow;
  not detailed further here as it doesn't materially change this
  spec's scope or data model.
- **Instructor self-registration is unrestricted in v1**: Any
  prospective instructor can register (no institutional vetting or
  invite-only gate) -- consistent with `roadmap.md`'s framing of this
  milestone as standard SaaS-building work, not a school-procurement
  workflow. Revisit if abuse (e.g. spam roster creation) is observed.

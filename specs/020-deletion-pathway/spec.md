# Feature Specification: Real-Account Deletion Pathway

**Feature Branch**: `030-deletion-pathway`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "deletion-pathway"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guardian requests deletion of their learner's account (Priority: P1)

A parent/guardian decides to withdraw their child from the platform and
submits a request to permanently delete the learner's account and every
piece of data tied to it. Today, per `specs/009-privacy-retention/
spec.md` FR-004/FR-005, submitting this request only creates a
`DeletionRequest` row -- no process ever acts on it, so the learner's
mastery state, assessment history, generated questions, roster
membership, and tutoring transcripts all remain in the system
indefinitely. This story closes that gap: the request must actually
result in a hard, irrecoverable deletion within the spec 009 SLA.

**Why this priority**: This is a live Constitution Principle VIII gap,
not a new capability -- every real guardian/learner/instructor account
created since Milestone 7 shipped has no working right-to-erasure path.
It is the reason this feature exists at all, so it is the only story
that must ship for this feature to be worth releasing.

**Independent Test**: Seed a synthetic learner with mastery state,
assessment events, generated questions, roster membership, and (if
Milestone 9 data exists) tutoring transcripts. Submit a deletion
request on that learner's behalf. Confirm every one of those rows is
gone -- not soft-deleted, not anonymized -- within the 30-day SLA, and
that no other learner's or instructor's data was touched.

**Acceptance Scenarios**:

1. **Given** a guardian, instructor, or institution submits a deletion
   request for a specific learner, **When** the request is processed,
   **Then** every row referencing that learner's identity (mastery
   state, assessment events, generated questions, roster/enrollment
   membership, recommendation-report output, and tutoring session/
   exchange transcripts) is permanently removed, and the `DeletionRequest`
   row is marked completed with a timestamp within 30 days of the
   request.
2. **Given** a completed deletion request for a learner, **When** any
   other part of the system (dashboard, roster list, recommendation
   aggregation, instructor review queue) subsequently queries for that
   learner, **Then** the learner does not appear and no request errors
   or returns a dangling/partial record.
3. **Given** a deletion request for a real instructor account,
   **When** the request is processed, **Then** the instructor's own
   identifying data is deleted, and each classroom roster the
   instructor owned is either transferred to a designated successor
   instructor or deleted along with its rosters per spec 009's Edge
   Case -- learner data is never silently deleted as a side effect of
   an instructor's own account deletion.
4. **Given** a deletion request targets an account that does not exist
   or was already deleted, **When** the request is submitted, **Then**
   the system returns a clear, non-crashing rejection rather than a
   partial or duplicate deletion attempt.

---

### User Story 2 - Automatic deletion after a year of inactivity (Priority: P2)

A learner's enrollment ends (e.g. end of an academic term with no
successor enrollment) and nobody ever files an explicit deletion
request. Per spec 009 FR-010, the account's data must still be
hard-deleted automatically once it has been inactive for a year,
through the exact same deletion mechanism as an explicit request --
not a second, separate deletion code path that could drift out of sync
with it.

**Why this priority**: This is spec 009's other deletion trigger and
carries the same Principle VIII urgency, but it depends on User Story
1's deletion mechanism already existing to route into, so it is
sequenced second.

**Independent Test**: Seed a synthetic `RetentionRecord` whose
`became_inactive_at` is more than one year in the past, run the
inactivity sweep, and confirm the linked account is deleted through the
same cascade as a manual request, with no dangling references left
behind.

**Acceptance Scenarios**:

1. **Given** a `RetentionRecord` shows an account inactive for more
   than one year, **When** the inactivity check runs, **Then** the
   account is hard-deleted through the same mechanism as an explicit
   `DeletionRequest`, and a `DeletionRequest` row is created to record
   that this deletion happened and why.
2. **Given** an account has been inactive for less than a year,
   **When** the inactivity check runs, **Then** the account is left
   untouched.
3. **Given** an account regains active enrollment before the one-year
   mark, **When** the inactivity check runs, **Then** the inactivity
   clock is treated as reset and the account is not deleted.

---

### User Story 3 - Guardian or instructor confirms a deletion request was honored (Priority: P3)

Having submitted a deletion request, the requester wants confirmation
it actually completed -- not just that a form was submitted -- since a
right-to-erasure request nobody can verify is functionally the same as
one that was ignored.

**Why this priority**: Valuable for trust and support-ticket reduction,
but the deletion mechanism itself (User Stories 1-2) delivers the
actual compliance value independent of whether a status-check surface
exists yet.

**Independent Test**: Submit a deletion request, then query its status
before and after processing completes, and confirm the status reflects
reality at each point.

**Acceptance Scenarios**:

1. **Given** a deletion request has been submitted but not yet
   processed, **When** the requester checks its status, **Then** the
   system reports it as pending.
2. **Given** a deletion request has completed, **When** the requester
   checks its status, **Then** the system reports it as completed along
   with the completion date, without exposing any of the now-deleted
   person's data.

---

### Edge Cases

- What happens when a deletion request arrives for a learner who has an
  in-progress quiz session, active guardian-mediated session (Milestone
  17), or an open Tutor Agent conversation? The deletion must still
  complete within the SLA; any in-progress session referencing the
  learner is terminated as part of the cascade, not left orphaned.
- How does the system handle a deletion request for a learner enrolled
  in more than one classroom roster? All roster memberships are
  removed, not just the one associated with the requester.
- What happens if the inactivity sweep (User Story 2) and an explicit
  deletion request (User Story 1) target the same account at nearly the
  same time? The second request to reach the deletion mechanism finds
  the account already gone and is treated as the "already deleted"
  case in User Story 1's Acceptance Scenario 4, not an error.
- How does the system handle a request targeting a demo account
  (`is_demo = true`)? Rejected -- demo accounts are reset on their own
  schedule (spec 009 FR-009), never through the real-account deletion
  SLA, since they carry no real person's data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a way for a guardian, instructor,
  or institution to submit a deletion request against a specific real
  learner, guardian, or instructor account, recorded as a
  `DeletionRequest` row per spec 009's data model.
- **FR-002**: The system MUST execute every pending `DeletionRequest`
  to completion within 30 days of submission, performing a hard delete
  (never anonymize-and-retain) of every row referencing the target
  identity, per spec 009 FR-004/FR-005's cascade scope: mastery state,
  assessment events, generated questions, roster/enrollment membership,
  recommendation-report output, and tutoring session/exchange
  transcripts (Milestone 9) where applicable.
- **FR-003**: The system MUST mark a `DeletionRequest` as completed,
  with a completion timestamp, only after every referencing row has
  actually been removed -- never optimistically before the cascade
  finishes.
- **FR-004**: The system MUST leave no dangling reference (a row
  pointing at a now-deleted identity) and no denormalized copy of the
  deleted person's data anywhere else in the system after a deletion
  completes.
- **FR-005**: The system MUST run an automatic check that identifies
  any `RetentionRecord` inactive for more than one year (per spec 009
  FR-010) and routes it through the same deletion mechanism as an
  explicit request (FR-001-FR-004), creating a `DeletionRequest` row to
  record that the deletion was inactivity-triggered rather than
  requester-initiated.
- **FR-006**: The system MUST reject a deletion request targeting an
  account that is already deleted or does not exist, returning a clear
  outcome rather than attempting a partial or duplicate deletion.
- **FR-007**: The system MUST reject a deletion request targeting a
  demo account (`is_demo = true`); demo accounts are reset per spec 009
  FR-009's own schedule, not this SLA.
- **FR-008**: When an instructor account is deleted, the system MUST
  resolve each classroom roster the instructor owned by either
  transferring ownership to a designated successor instructor or
  deleting the roster, without deleting the learner accounts enrolled
  in it as a side effect (spec 009's Edge Case).
- **FR-009**: The system MUST allow the original requester to check a
  submitted deletion request's status (pending or completed, with
  completion date once done) without exposing any data belonging to the
  deletion's target.
- **FR-010**: Every deletion request's submission and completion MUST
  be logged in a way that is traceable after the fact (Constitution
  Principle V), even though the target's own data no longer exists to
  cross-reference -- the `DeletionRequest` row itself is this record
  and is retained indefinitely as proof the SLA was met (never itself
  subject to this feature's own deletion mechanism).

### Key Entities *(include if feature involves data)*

- **DeletionRequest** (existing model, `specs/009-privacy-retention`):
  This feature is what finally acts on it. Adds no new fields; this
  spec is scoped to making `completed_at` a real, earned timestamp
  rather than one nothing ever sets.
- **RetentionRecord** (existing model, `specs/009-privacy-retention`):
  Read by this feature's inactivity check to decide when FR-010's
  automatic deletion trigger fires. No new fields required.
- **Deletion cascade scope**: Not a new entity, but the concrete set of
  existing tables (mastery, assessment events, generated questions,
  roster/enrollment membership, recommendation output, tutoring
  transcripts, and any table added by a later milestone that FK's to a
  learner/guardian/instructor identity) that a completed deletion must
  reach. This set grows as the schema grows and is not exhaustively
  fixed by this spec.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of submitted deletion requests, across every target
  type (learner, guardian, instructor) and every entity type in the
  cascade scope, complete within the 30-day SLA with zero dangling
  references or denormalized leftover data, verified by an automated
  check that queries for any row still referencing a deleted identity.
- **SC-002**: A learner account inactive for more than one year is
  auto-deleted without any explicit deletion request ever having been
  submitted, verified against a simulated inactive `RetentionRecord`.
- **SC-003**: A deletion request targeting an already-deleted or
  nonexistent account is rejected without side effects, 100% of the
  time in automated testing.
- **SC-004**: An instructor account deletion never results in an
  enrolled learner's data being deleted as an unintended side effect,
  verified by an automated check.
- **SC-005**: A requester can confirm a deletion request's completion
  status without needing to inspect the database directly.

## Assumptions

- This feature implements spec 009's already-approved FR-004/FR-005/
  FR-010 requirements and data model (`DeletionRequest`,
  `RetentionRecord`); it does not reopen or change the 30-day SLA, the
  1-year inactivity ceiling, or the hard-delete-only policy those
  requirements already settled.
- The cascade scope (which tables get reached) is defined as "every
  table that FK's or otherwise references a learner/guardian/instructor
  identity, as it exists at the time this feature is built" -- it is
  expected to need updates as future milestones add new tables that
  reference an account, the same way `data-classification.md` is
  already a living document for this reason.
- Roster ownership transfer on instructor deletion (FR-008) assumes a
  designated-successor mechanism can be a manual/instructor-provided
  choice at request time rather than an automatic algorithm; this spec
  does not need to invent a successor-selection heuristic.
- The one-year inactivity check (FR-005) runs on a periodic schedule
  rather than in real time; this spec does not mandate a specific
  cadence, only that it fires reliably within the compliance window
  spec 009 already established.
- Deletion-request submission in this spec covers the guardian,
  instructor, and institution actors already named in spec 009 FR-004;
  it does not add a new self-service learner-initiated path, since
  spec 009's provisioning model has the parent/guardian holding the
  learner's login credential.

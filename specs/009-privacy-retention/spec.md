# Feature Specification: Privacy & Retention Spec -- the Real Learner Data Gate

**Feature Branch**: `009-privacy-retention`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "milestone 7"

## Clarifications

### Session 2026-08-22

- Q: How does a real learner (a minor, provisioned per FR-003) actually authenticate, and who may enroll them? → A: A parent/guardian always creates the account and sets the child's login credentials directly (COPPA verifiable-parental-consent path, not a school-official-only model). Every classroom is configured as either **open** (a parent may enroll their child via a join code without instructor approval) or **closed** (the instructor must approve/invite each enrollment before it completes) -- this open/closed distinction governs enrollment gating only, not who holds the credential. (The open/closed distinction's *content-curation* difference -- LLM-curated for open classrooms vs. human-approved for closed -- is a separate, content-review-workflow concern, not part of this privacy/retention spec; tracked as a new `roadmap.md` backlog item instead.)
- Q: When a deletion request is honored, is a learner's data hard-deleted or anonymized-and-retained for aggregate research? → A: Hard delete, no exceptions -- every row tied to the deleted identity is permanently removed, never de-identified and kept for mastery-model/eval-harness research. This is the stronger compliance posture (true right-to-erasure); it also means a deleted learner's contribution to any future aggregate training/eval corpus (Milestones 3, 11) is lost, not retained.

## User Scenarios & Testing *(mandatory)*

This feature is the dedicated privacy/retention spec that Constitution
Principle VIII requires to exist and be approved before this project
may ingest any real (non-synthetic) learner or instructor data. Per
Milestone 7's own Definition of Done, it MUST be approved before the
rest of Milestone 7's classroom-building work (auth, rosters,
dashboard, content review) begins -- not written in parallel with it.
Its "users" are therefore the people whose data this policy protects
(real students and instructors, once Milestone 7 proper creates
accounts for them) and the people who must be able to trust the
platform enforces it (the instructor/institution granting access, and
anyone auditing the platform's data-handling posture).

### User Story 1 - No real learner or instructor data can exist before this spec is approved (Priority: P1)

Before this spec is approved and its controls are live, the system
must remain technically incapable of persisting a real (non-demo,
non-synthetic) learner or instructor account anywhere -- the same
guarantee `check_no_subject_conditionals.py` gives Constitution
Principle III, applied here to Principle VIII.

**Why this priority**: This is the gate itself. Every other user story
in this spec assumes the gate holds; if it doesn't, approving the rest
of this spec after the fact doesn't undo any real data already
ingested.

**Independent Test**: Run the automated check (FR-001) against the
current codebase at any commit -- it passes today (no real-account code
path exists yet) and must keep passing until Milestone 7 proper's
implementation explicitly satisfies every other requirement in this
spec first.

**Acceptance Scenarios**:

1. **Given** the current codebase, **When** the automated real-account
   gate check runs, **Then** it finds zero code paths that can create or
   persist a non-demo learner or instructor account.
2. **Given** a future PR that adds a real-account-shaped model (its
   table name matching a learner/instructor/guardian/account pattern),
   **When** that PR's CI runs, **Then** the gate check fails unless that
   model also carries a non-nullable `is_demo` column. (This is a
   necessary, not sufficient, condition -- the gate script verifies
   `is_demo` presence only; it cannot verify retention-policy fields,
   access control, or a working deletion path exist, since none of
   those tables are in this spec's own scope to check against. Full
   verification of this spec's other requirements is Milestone 7
   proper's own review responsibility when it actually builds those
   tables.)

---

### User Story 2 - A real learner's or instructor's data can be deleted on request (Priority: P1)

Once real accounts exist (Milestone 7 proper), a learner, instructor,
or the institution acting on a learner's behalf can request deletion of
that person's data, and the platform honors it completely within a
locked timeframe -- not as a manual, ad hoc database operation, but as
a defined, repeatable process.

**Why this priority**: FERPA/COPPA-scoped data carries a legal deletion
obligation, not just a product-quality one. This is as load-bearing as
User Story 1 -- a gate that gets real data in but has no path to get it
back out again is only half a privacy control.

**Independent Test**: Simulate a deletion request against a synthetic
account carrying the same data shape a real account would (roster
membership, assessment events, mastery state, generated questions) and
confirm every referencing row is hard-deleted within the locked SLA,
with no orphaned foreign-key references left behind.

**Acceptance Scenarios**:

1. **Given** a learner account with roster membership, assessment
   history, and mastery state, **When** a deletion request is submitted
   and processed, **Then** all of that learner's data and activity
   history is permanently deleted (not merely de-identified) within the
   locked SLA (FR-004).
2. **Given** a deletion request is in progress, **When** any other part
   of the system (dashboard, recommendation report, audit log) queries
   for that learner's data, **Then** it returns nothing for that
   learner -- never a partial, inconsistent view.

---

### User Story 3 - An instructor can only ever see their own roster's data (Priority: P1)

An instructor's dashboard, roster view, and any aggregated
weak-area/recommendation report are scoped strictly to the learners
enrolled in that instructor's own classroom(s) -- never another
instructor's roster, even if both exist in the same deployment.

**Why this priority**: Multi-tenancy access control is the specific,
concrete form Principle VIII's "access-control requirements" takes once
more than one instructor exists in the system. Getting this wrong is a
cross-tenant data leak, not a cosmetic bug.

**Independent Test**: Seed two instructor accounts with non-overlapping
rosters and confirm every read path (dashboard, roster list,
recommendation aggregation) scoped to instructor A returns zero rows
belonging to instructor B's roster, across every such read path in the
system.

**Acceptance Scenarios**:

1. **Given** two instructors each with their own roster, **When**
   instructor A requests their dashboard/roster data, **Then** no
   learner belonging to instructor B's roster appears anywhere in the
   response.
2. **Given** an instructor's session, **When** that instructor attempts
   to directly request another instructor's roster or a learner not on
   their own roster by ID, **Then** the request is denied, not silently
   filtered client-side.

---

### User Story 4 - A demo account is always, unmistakably distinguishable from a real account (Priority: P2)

Every seeded demo account (learner or, from Milestone 7 onward,
instructor) carries an explicit, non-nullable `is_demo` flag set at
creation time, a persistent and unmissable UI indicator while active,
and is reachable only through a dedicated demo entry point -- never
through the same path as real sign-up, and never inferable from naming
convention or activity pattern alone.

**Why this priority**: Already partially established by Milestone 1's
`DemoLearnerProfile` and `tech-stack.md`'s Demo account strategy table;
this spec is what makes it Constitution Principle VIII's formally
binding requirement (not just a design choice) once real accounts exist
alongside demo ones, when the two could otherwise be confused for the
first time.

**Independent Test**: Attempt to reach a demo account through the real
sign-up/login flow (must be impossible) and confirm the UI badge
renders on every screen while a demo session is active, including
after navigation.

**Acceptance Scenarios**:

1. **Given** the real sign-up/login flow, **When** any user completes
   it, **Then** the resulting account never has `is_demo` set to `true`.
2. **Given** an active demo session, **When** the user navigates to any
   screen in the product, **Then** the "DEMO ACCOUNT" indicator is
   visibly present.

---

### Edge Cases

- What happens when a deletion request arrives for a learner whose
  mastery state is still referenced by an in-progress quiz session or a
  not-yet-generated recommendation report? (Deletion must not silently
  fail or leave a dangling reference -- the deletion path must handle
  or block on in-flight dependent state, not race it.)
- What happens if an instructor's own account is deleted while their
  roster's learners still have active data? (Learner data outlives an
  individual instructor's account deletion unless the learners
  themselves are also deleted -- ownership of the *account* is not the
  same as ownership of the *underlying learner data*.)
- What happens if a real user pastes genuinely real personal
  information (e.g. their actual name) into a free-text answer on a
  *demo* account? (Out of scope for this spec to prevent at the content
  level -- demo accounts are seeded and reset on a schedule per
  `tech-stack.md`, which bounds how long such content could persist, but
  this spec does not add new content-scanning requirements beyond the
  existing moderation guardrails.)
- What happens when a parent joins an **open** classroom the instructor
  didn't specifically invite? (The enrollment completes immediately per
  FR-003a; the instructor's roster and every access-control scope
  (FR-006) update to include that learner right away -- there is no
  separate "pending instructor review" state for an open classroom by
  definition, since that would make it a closed one.)
- What happens to audit-log rows (Constitution Principle V's
  "why was this learner shown this" trail) for a learner whose data is
  deleted? (They must be hard-deleted along with everything else this
  learner's identity is attached to -- Principle V's explainability
  requirement does not override Principle VIII's deletion requirement;
  see FR-005. Explainability for a since-deleted learner's past
  decisions is no longer possible after deletion, which is the
  expected, accepted tradeoff of a real erasure request.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an automated, CI-runnable check
  (in the spirit of `check_no_subject_conditionals.py`) that fails if
  any code path can create or persist a real (non-`is_demo`) learner or
  instructor account, until every other requirement in this spec is
  satisfied by the implementation that introduces real accounts
  (Milestone 7 proper).
- **FR-002**: The system MUST maintain a written data classification
  listing every field collected about a real learner and a real
  instructor, each field's retention period, and the event that triggers
  its deletion.
- **FR-003**: A real learner account's login credentials MUST always be
  created and controlled by a parent/guardian, never by the learner
  (a minor) independently and never by an instructor on the learner's
  behalf -- this is the verifiable-parental-consent action itself, not
  a formality. A learner never has a login credential their parent/
  guardian didn't set.
- **FR-003a**: Every classroom MUST be configured as either **open**
  (a parent/guardian may enroll their child by joining a class code
  without instructor approval) or **closed** (the instructor MUST
  approve or send an individual invite for each enrollment before it
  completes). This governs who may create the *enrollment link* between
  a learner and a classroom -- it does not change FR-003: the parent
  still creates the login credential in both cases.
- **FR-004**: The system MUST support a deletion request (submitted by
  the parent/guardian, the instructor, or the institution on the
  learner's behalf) that permanently, irrecoverably deletes all of that
  person's data and activity history -- a hard delete, never a
  de-identify-and-retain operation -- within 30 days of the request.
- **FR-005**: A deletion request MUST cascade to every table
  referencing that person's identity, including audit-log
  (`AssessmentEvent`) rows, mastery state, generated questions, roster
  membership, and any recommendation-report output -- no referencing row
  may be left pointing at a deleted identity in a way that either
  breaks (dangling reference) or silently un-deletes (denormalized copy
  elsewhere) the deletion.
- **FR-006**: Every read path that returns learner or roster data
  (dashboard, roster list, recommendation aggregation, mastery state)
  MUST be scoped to the requesting instructor's own roster -- enforced
  server-side, never only in client-side filtering.
- **FR-007**: Every seeded demo account (learner or instructor) MUST
  carry an explicit, non-nullable `is_demo` boolean set at creation
  time, MUST display a persistent, visible "DEMO ACCOUNT" indicator in
  the UI for the duration of an active demo session, and MUST be
  reachable only via a dedicated demo entry point separate from real
  sign-up.
- **FR-008**: The system MUST provide an automated check confirming no
  account reachable via the real sign-up/provisioning flow can ever
  have `is_demo` set to `true`.
- **FR-009**: Seeded demo accounts MUST be reset to a known-good seeded
  state on a defined schedule (per `tech-stack.md`'s Demo account
  strategy table), independent of this spec's real-account retention
  rules -- demo data is never subject to the same retention/deletion SLA
  as real data, since it carries no real person's information.
- **FR-010**: The system MUST retain a real account's data for as long
  as the account remains enrolled/active, and for up to 1 year after
  the account becomes inactive (e.g. end of an academic term with no
  successor enrollment), after which it MUST be automatically
  hard-deleted under the same FR-004/FR-005 process, independent of
  whether an explicit deletion request was ever submitted.
- **FR-011**: Every real learner account, at creation time, MUST record
  which party authorized the *enrollment* (not the login credential,
  which is always the parent/guardian per FR-003): the consenting
  parent/guardian's own join action for an open classroom, or the
  approving instructor's action for a closed classroom. This is the
  system's audit record of which enrollment path (FR-003a) was actually
  followed for that specific learner.

### Key Entities *(include if feature involves data)*

- **RealGuardianAccount**: A real parent/guardian's account -- the
  actual authenticating identity and credential holder (FR-003). Not a
  learner-facing concept; this is who logs in and who consent legally
  attaches to.
- **RealLearnerAccount**: A real (non-demo) student's profile, linked to
  and controlled by exactly one `RealGuardianAccount`, distinct from
  Milestone 1's synthetic `DemoLearnerProfile`. Carries the same
  mastery-state/assessment-event relationships `DemoLearnerProfile`
  does today, plus the retention/authorization metadata this spec
  requires. Has no independent login credential of its own.
- **RealInstructorAccount**: A real educator's account, owning one or
  more classroom rosters. Introduced by Milestone 7 proper; this spec
  defines the data-handling obligations it must carry from the moment
  it can be created.
- **ClassroomRoster**: The enrollment relationship scoping a set of
  `RealLearnerAccount`s to one `RealInstructorAccount`, carrying an
  **open**/**closed** enrollment-gating mode (FR-003a), and the
  boundary every access-control check (FR-006) is enforced against.
- **DeletionRequest**: A record of a submitted deletion request, its
  target identity, submission time, and completion time -- proof the
  30-day SLA (FR-004) was met, and the audit trail for the deletion
  itself.
- **RetentionRecord**: Per-account metadata tracking enrollment/active
  status and the authorizing instructor/institution (FR-010, FR-011),
  used to drive automatic post-inactivity deletion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The automated real-account gate check (FR-001) has zero
  failures at every commit until Milestone 7 proper's implementation
  satisfies this spec's other requirements.
- **SC-002**: 100% of simulated deletion requests, across every entity
  type listed in FR-005, complete within the 30-day SLA with zero
  orphaned references afterward.
- **SC-003**: Across a cross-tenant test suite of at least 2 instructors
  with non-overlapping rosters, 0 of the tested read paths ever return
  another instructor's roster data.
- **SC-004**: 100% of real accounts created in testing carry a complete
  `RetentionRecord` (enrollment status, authorizing party -- parent for
  an open classroom, instructor for a closed one) at creation time --
  no account can be created without one.
- **SC-005**: 100% of manual/automated UI checks confirm the demo
  indicator is visible on every screen during an active demo session,
  and the automated check (FR-008) finds zero real-sign-up-reachable
  accounts with `is_demo: true`.

## Assumptions

- This spec defines this project's data-handling *policy* and the
  technical controls/gates that enforce it; it is a product/engineering
  specification, not a substitute for actual legal review before this
  product is used with real minors' data in a real institution. Given
  the stated FERPA/COPPA scope, real-world deployment should still get
  independent legal sign-off before onboarding a real institution --
  this spec makes the platform *capable* of meeting that bar, not a
  legal certification that it does.
- This spec scopes compliance to U.S. federal law (FERPA, COPPA) only,
  consistent with the grade 1-12 framing used elsewhere in this
  project's roadmap. International regulations with materially
  different requirements (e.g. GDPR's variable age-of-consent by EU
  member state) are out of scope until a specific non-U.S. institution
  is being onboarded, at which point this spec would need a dedicated
  addendum, not a silent extension.
- The product operates under COPPA's verifiable-parental-consent path:
  a parent/guardian always creates the account and consents directly
  (FR-003), rather than the product relying solely on a school/
  institution's own FERPA "school official" authorization as a stand-in
  for consent. The open/closed classroom distinction (FR-003a) then
  layers FERPA-style institutional control on top for closed classrooms
  (the instructor gates enrollment) without changing who holds consent
  (always the parent).
- Instructor accounts (adults) and learner accounts (plausibly minors)
  are held to the same retention/deletion mechanics in this spec (FR-004
  /FR-005/FR-010) for implementation simplicity, even though COPPA's
  heightened protections apply specifically to learners under 13 --
  applying the stricter bar uniformly is a reasonable default rather
  than building two separate retention regimes for v1.
- The 30-day deletion SLA (FR-004) and 1-year post-inactivity retention
  ceiling (FR-010) are reasonable defaults chosen for this spec in the
  absence of a specific institutional contract dictating otherwise;
  revisit if Milestone 7 proper's instructor/institution onboarding
  surfaces a different contractual requirement.
- Milestone 7 proper (auth, rosters, dashboard, content review) is a
  separate spec that depends on this one being approved first, per this
  milestone's own Definition of Done -- this spec does not itself
  implement account creation, roster CRUD, or the instructor dashboard.

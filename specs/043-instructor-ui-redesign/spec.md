# Feature Specification: Instructor-Facing UI Redesign

**Feature Branch**: `043-instructor-ui-redesign`

**Created**: 2026-10-07

**Status**: Draft (tracked as `roadmap.md` Milestone 25)

**Input**: User description: "Redesign and extend the instructor-facing screens (Dashboard, Review, Rosters) to match new mockups provided at /home/raja/cognivo_instructor_screens, and implement a new Instructor Settings screen that doesn't exist yet today."

## Context

Four reference mockups (static `.dc.html` artboards, not production code) were provided for the instructor experience: `InstructorDashboard`, `Review`, `Rosters`, and `InstructorSettings`. The first three correspond to live pages today (`frontend/src/app/instructor/{dashboard,review,rosters}`) and this feature restyles them in place, the same category of work as the already-shipped `specs/027-learner-ui-redesign` (a design-system update, not a new milestone). `InstructorSettings` has no live counterpart — it is genuinely new functionality, but almost everything it needs already exists in the backend from prior milestones:

- Password change: `POST /api/auth/guardian/change-password` already exists; this feature adds the instructor-account equivalent.
- Display preferences (theme/larger text/reduce motion): already shipped for guardians (spec 041 FR-011, `AccountDisplayPreferences.tsx`) as columns on `RealGuardianAccount` only; this feature extends the same pattern to `RealInstructorAccount`.
- Deletion requests (an instructor's own account, or a learner enrolled in one of the instructor's own rosters): `POST /api/deletion-requests` and `can_request_deletion` (spec 020) already authorize exactly these two cases for an instructor session — this feature only adds the UI entry points, no new deletion logic.
- Per-roster "who can join" (`enrollment_mode`): already exists on `ClassroomRoster`. What's new is an instructor-level *default* so the create-roster form doesn't start from scratch every time.
- Quiz due date: `QuizAssignment.due_at` already exists and is nullable. What's new is an instructor-level default for whether a new quiz assignment starts with a due date or not.
- Notifications: Cognivo has no notification-sending system today (no email service, no in-app notification model, no background job runner, and the Vercel serverless constraint rules out a persistent delivery worker). Per user decision, this feature adds a persisted preference toggle only — visually complete, functionally inert until a future feature wires up real delivery.

A second clarification session (same day) expanded this feature's scope beyond the four mockups: Cognivo should always have a usable class and quiz-assignment path for a guardian's learner in every subject, independent of whether any real instructor has registered at all. Rather than building new guardian-enrollment or review infrastructure, this reuses two things that already exist: `ClassroomRoster` is just a normal instructor-owned row (so a seeded, real, non-demo `RealInstructorAccount` can own one per subject), and spec 041's guardian class directory already lists any open, listed roster regardless of which instructor owns it. The one genuinely new piece is letting a guardian assign a quiz themselves, scoped narrowly to this seeded account's own rosters.

## Clarifications

### Session 2026-10-07

- Q: What should the "default due-date behavior" classroom default actually store and apply? → A: Boolean + fixed offset — instructor picks "no due date" or "N days from assignment date"; the default is a nullable day-count (`null` = no due date), and applying it means adding that many days to the assignment's creation date each time a new quiz is assigned.

### Session 2026-10-07 (second pass — default instructor)

- Q: Is "a default instructor guardians can enroll in / assign quizzes through when no real instructor is registered" in scope for this UI-redesign spec, or a separate feature? → A: Fold into this spec, per explicit user direction, even though it's a cross-cutting capability rather than a restyle.
- Q: What roster structure backs the default instructor for each subject? → A: One shared, system-owned roster per subject (not per-guardian, not per-learner, not roster-less) — a real `ClassroomRoster` row like any other, just owned by a seeded account. Matches "enroll class" literally; guardians never see other learners' data through this (that view is instructor-only).
- Q: Who reviews flagged questions on the default instructor's rosters, given there's no real instructor to log in? → A: No new account type and no auto-approval. The default instructor is itself a real, credentialed `RealInstructorAccount` (`is_demo=false`) whose login is known only to the Cognivo operator — the operator can sign in with it and use the existing, unmodified Review/Dashboard/Rosters screens exactly like any other instructor. No new review logic.
- Q: Is the default-instructor roster only a fallback that disappears once a real instructor registers for that subject? → A: No. It is always available for every subject, regardless of whether a real instructor exists for that subject. A guardian chooses freely among every open, listed roster for a subject — the default instructor's roster alongside any real instructor's.
- Q: Who triggers the actual quiz assignment under the default instructor — the guardian, or the Cognivo operator via the default instructor's login? → A: Both. A guardian gets a new, narrowly-scoped capability to assign a quiz to their own enrolled learner on a default-instructor-owned roster directly from their own session; the Cognivo operator can also do it the existing way, by signing in with the default instructor's real credentials and using the existing instructor-side Rosters "Assign a quiz" action — no conflict between the two paths.

### Session 2026-10-07 (third pass — default instructor credentials)

- Q: How does the Cognivo operator actually set and know the default instructor's real password, given a seed script can't commit a real secret to the repo? → A: Environment variables at seed time (e.g. `DEFAULT_INSTRUCTOR_EMAIL`/`DEFAULT_INSTRUCTOR_PASSWORD`, set in Vercel's env config and a local, never-committed `.env`) — the same pattern this project already uses for `DATABASE_URL` and other secrets. The seed script hashes the password the same way normal instructor registration does; the operator "knows" the login simply by being the one who set those env vars.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An instructor sees the refreshed visual design on existing screens with no change in behavior (Priority: P1)

An instructor using the Dashboard, Review, or Rosters screens sees the new visual language from the mockups, while every existing interaction (viewing class weak areas, approving/rejecting/reactivating a flagged question, creating a roster, approving a join request, assigning a quiz) behaves exactly as it did before the redesign.

**Why this priority**: This is a pure restyle of live, working pages. Behavioral parity is the one thing a design-system update must never break.

**Independent Test**: Load each of the three screens before and after the redesign with the same demo-instructor state and confirm identical data, navigation targets, and interactive outcomes, with only visual presentation differing.

**Acceptance Scenarios**:

1. **Given** the Dashboard, Review, and Rosters screens, **When** each renders, **Then** its colors, typography, spacing, corner radii, and component shapes match the corresponding mockup's values.
2. **Given** an instructor performs any existing action on one of the three screens (approve/reject/reactivate a flagged question, create a roster, approve a pending join request, assign a quiz to a whole roster or selected learners, open/close a roster), **When** the action completes, **Then** the outcome is identical to the pre-redesign behavior for the same submitted inputs (a create-roster/assign-quiz form's pre-filled *starting* values may differ per FR-009's classroom defaults — FR-002's explicit exception — but submitting the same inputs still produces the same result).
3. **Given** a screen outside these three (e.g. learner-facing screens, guardian/auth flows), **When** this redesign ships, **Then** its layout, component shapes, and structure are unchanged, aside from any shared color-token values already established as global by prior redesigns.

---

### User Story 2 - An instructor manages their account from a new Settings screen (Priority: P1)

An instructor opens a new Settings screen and can change their password, set a display theme (light/dark/system matching device), set a notification preference, set classroom defaults (default join policy for new rosters, default due-date behavior for new quiz assignments), see what Cognivo stores about them and what they can see about their learners, request deletion of a specific enrolled learner's data, and request deletion of their own instructor account — with a persistent demo-account indicator if the signed-in instructor is a demo account.

**Why this priority**: This is the one genuinely new capability in the feature; without it the mockup's fourth screen has no live counterpart at all.

**Independent Test**: As a non-demo instructor, change the password and confirm the next login requires the new one; change the theme and confirm it applies immediately; set classroom defaults and confirm a newly created roster/quiz assignment starts from those defaults; submit a learner-deletion request and an own-account deletion request and confirm each appears via the existing deletion-request status check.

**Acceptance Scenarios**:

1. **Given** an instructor on the Settings screen, **When** they submit their current password and a new one, **Then** the password is changed and a session using the old password no longer authenticates.
2. **Given** an instructor picks a theme (light/dark/system), **When** the choice is saved, **Then** it applies to the current session immediately and persists across future sign-ins, the same way it already does for a guardian.
3. **Given** an instructor sets a default "who can join" policy and a default due-date behavior, **When** they later create a roster or assign a quiz, **Then** the creation form is pre-filled from that default and remains overridable per roster/assignment.
4. **Given** an instructor requests deletion of a learner enrolled in one of their own rosters, **When** the request is submitted, **Then** it is accepted and its status is visible, using the existing deletion-request pathway with no new authorization rule.
5. **Given** an instructor requests deletion of their own account, **When** the request is submitted, **Then** it is accepted the same way, using the existing deletion-request pathway.
6. **Given** a demo instructor account, **When** they view Settings, **Then** a persistent "this is a demo account" indicator is visible, and the account-deletion action is unavailable or clearly inert for the demo account (Constitution Principle VIII: a demo account must not be deletable through the same real-account pathway).
7. **Given** an instructor toggles the notifications preference, **When** the choice is saved, **Then** it persists across sign-ins; no notification is ever actually sent as a result (Context: inert by design, per user decision).

---

### User Story 3 - A guardian enrolls and assigns a quiz with no real instructor involved (Priority: P1)

A guardian whose learner has no real instructor for a subject finds that subject's class already listed in the existing guardian class directory — owned by Cognivo's own seeded "default instructor" account — joins it the same way they'd join any other open class, and then assigns a quiz to their own enrolled learner directly from their own guardian session, with no real instructor ever needing to exist or act.

**Why this priority**: Without this, a guardian whose learner has no real instructor for a subject has no way to get a quiz assigned at all, since quiz assignment has always required an instructor-owned roster.

**Independent Test**: For a subject with zero real-instructor rosters, confirm a default-instructor-owned class is listed and joinable in the class directory, join it, assign a quiz to the enrolled learner from the guardian's own session, and confirm the learner sees it as a normal assigned quiz.

**Acceptance Scenarios**:

1. **Given** a subject with zero real-instructor rosters, **When** a guardian opens the class directory, **Then** a default-instructor-owned, open class for that subject is listed and joinable, exactly as any other open/listed class would be.
2. **Given** a subject where a real instructor also has an open, listed roster, **When** a guardian opens the class directory, **Then** both the real instructor's roster and the default instructor's roster are listed, and the guardian may join either.
3. **Given** a learner enrolled in a default-instructor-owned roster, **When** their guardian assigns a quiz to that learner from the guardian's own session, **Then** the assignment is created exactly as if a real instructor had created it, and the learner can take it normally.
4. **Given** the same enrolled learner is also enrolled in a real instructor's roster, **When** the guardian attempts to assign a quiz on that real instructor's roster, **Then** the attempt is denied — a guardian may only assign quizzes on a default-instructor-owned roster.
5. **Given** the Cognivo operator signs in directly with the default instructor's real credentials, **When** they view Dashboard/Review/Rosters, **Then** those screens work exactly as they would for any other real instructor account, with no special-cased behavior.

---

### Edge Cases

- What happens when an instructor tries to request deletion of a learner who is not enrolled in any of their rosters? The existing `can_request_deletion` check already denies this; Settings must only let an instructor pick from their own rosters' enrolled learners in the first place, with the backend denial as the final guard either way.
- What happens on a screen state the mockups didn't depict (empty states, loading states, error states) across Dashboard/Review/Rosters/Settings? These must still render using the shared design-token system even though no mockup explicitly covers them. Review's own empty state ("Nothing to review right now.") is depicted and must be preserved.
- What happens if a demo instructor opens Settings? Password-change and account-deletion are unavailable/inert for a demo account (no real credential to change, no real account to delete through this pathway); theme, notification preference, and classroom defaults remain available since they're harmless per-session/per-account preferences, not account lifecycle actions.
- What happens to a roster or quiz assignment created before classroom defaults existed? Unaffected — defaults only pre-fill the creation form going forward; they are never retroactively applied to existing rosters or assignments.
- What happens when a new Subject is added to the content catalog? A default-instructor-owned roster for it must be seeded as part of adding the subject (FR-016), so the class directory and guardian self-service quiz assignment work for it immediately, never lagging behind.
- What happens when a guardian tries to assign a quiz on a roster their learner isn't enrolled in, or that isn't owned by the default instructor? Denied, mirroring the existing instructor-ownership check already used for instructor-triggered assignment — evaluated here as "guardian owns the learner, learner is enrolled in the roster, and the roster is default-instructor-owned" instead of "instructor owns the roster."
- How does the default instructor's data appear on the instructor-facing Dashboard/Review/Rosters screens (FR-001-FR-003)? Identically to any other instructor's — no special UI treatment, consistent with FR-018.
- What happens if someone repeatedly fails to log in as the default instructor? The same per-account lockout FR-006 adds for every instructor applies (`LOCKOUT_THRESHOLD` failures locks the account for `LOCKOUT_DURATION_MINUTES`, mirroring the guardian login lockout's already-accepted no-IP-component trade-off, `lockout.py`). Accepted as a known, documented risk specifically because the default instructor's email is effectively public (shown to every guardian as the roster owner in the class directory): anyone can keep this one operationally-critical account locked out indefinitely by repeating a bad login every `LOCKOUT_DURATION_MINUTES`. No IP-keyed or other additional throttle is added in this feature; revisiting this trade-off (e.g. an IP-keyed component) needs its own spec decision, same reasoning `lockout.py`'s own docstring already gives for the guardian case.
- What happens to an instructor's other active sessions when they change their password (FR-006)? Invalidated, exactly like the guardian equivalent — `RealInstructorAccount` gained its own `password_changed_at` column during PR #111 review (FR-013), so a session token issued before the change is rejected on its next use, the same `current_session_claims` mechanism (`instructor_session_revoked`, mirroring `guardian_session_revoked`) already enforces for guardians.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Dashboard, Review, and Rosters screens MUST visually match the provided mockups' color palette, typography, spacing, corner radii, and component shapes.
- **FR-002**: The redesign of Dashboard/Review/Rosters MUST NOT alter any existing data, navigation target, or submitted-outcome of any action on those screens — what gets created, approved, rejected, or changed when a form is submitted stays identical for the same inputs. **Exception**: FR-009's classroom-defaults pre-fill MAY change a create-roster or assign-quiz form's *initial* field values (pre-filled from the instructor's own saved defaults); this is not an altered interactive outcome, since the form remains fully overridable before submission, the same precedent FR-004 already sets for the guardian-directory exception.
- **FR-003**: Shared visual values introduced by the redesign MUST be defined in the project's existing shared design-token system, not duplicated as one-off literals per component, consistent with `specs/027-learner-ui-redesign` FR-006.
- **FR-004**: Screens and components outside Dashboard/Review/Rosters/Settings are out of scope for layout, component-shape, and structural changes — with one narrow functional exception: the existing guardian class directory and "My learners" screens (spec 041) gain the new guardian-facing quiz-assignment action FR-017 requires, with no visual/layout change to either screen beyond adding that one new action.
- **FR-005**: A new Settings screen MUST exist at an instructor-facing route, matching the `InstructorSettings` mockup's sections: Account, Classroom defaults, Display, Notifications, Privacy.
- **FR-006**: Instructors MUST be able to change their password from Settings, given their current password, via a new instructor-account password-change endpoint mirroring the existing guardian one (`POST /api/auth/guardian/change-password`).
- **FR-007**: Instructors MUST be able to set a display theme (light / dark / system) from Settings, applied immediately and persisted across sign-ins, by extending the existing guardian-only display-preferences pattern (spec 041 FR-011) to instructor accounts.
- **FR-008**: Instructors MUST be able to set a notification preference from Settings. Per user decision, this preference is persisted but MUST NOT trigger any actual notification delivery — no notification-sending capability exists in this product and none is introduced by this feature.
- **FR-009**: Instructors MUST be able to set two classroom defaults from Settings: a default "who can join" policy for newly created rosters (one of the existing `EnrollmentMode` values, `OPEN` or `CLOSED` — no new enum value), and a default due-date behavior for newly assigned quizzes, stored as a nullable day-count (`null` = no due date; a positive integer = "due N days after the assignment is created"). These defaults MUST only pre-fill the corresponding creation form (computing an actual `due_at` by adding the stored day-count to the assignment's creation date, when set) and MUST remain overridable per roster/assignment; they must never be retroactively applied to existing rosters or quiz assignments.
- **FR-010**: Settings MUST display, in plain language, what Cognivo stores about the instructor and what the instructor can see about their enrolled learners (informational content, no new data access).
- **FR-011**: Instructors MUST be able to request deletion of a learner enrolled in one of their own rosters, and of their own instructor account, from Settings — using the existing `POST /api/deletion-requests` endpoint and existing `can_request_deletion` authorization (spec 020) with no new deletion rule. The learner picker MUST only offer learners enrolled in one of the requesting instructor's own rosters.
- **FR-012**: A demo instructor account MUST see a persistent, visible indicator that it is a demo account on the Settings screen (Constitution Principle VIII), and MUST NOT be able to change its password or request its own account's deletion through this screen — both actions MUST be unavailable or clearly inert for a demo account.
- **FR-013**: The redesign MUST introduce no new database table or column beyond the narrow additions FR-006/FR-007/FR-008/FR-009 require (FR-006's password-change endpoint needs two lockout columns — `failed_login_attempts`/`locked_until` — mirroring the guardian endpoint's own PR #109 brute-force fix, since mirroring the endpoint's behavior without mirroring its lockout protection would reintroduce a gap already fixed once on the guardian side; FR-006 also needs `password_changed_at`, mirroring `RealGuardianAccount`'s own session-invalidation-on-password-change column (added during PR #111 review — a stolen session surviving the one action meant to end its validity undercut the endpoint's purpose, which outweighed holding this feature's schema addition to the originally-scoped eight columns); FR-007 needs theme/larger-text/reduce-motion columns on `RealInstructorAccount` mirroring `RealGuardianAccount`'s; FR-008 needs one notification-preference column; FR-009 needs two default-preference columns on `RealInstructorAccount` — nine new columns total), plus the one new backend endpoint FR-017 requires. No other new backend surface is permitted under this feature.
- **FR-014**: Cognivo MUST seed and maintain exactly one real, non-demo instructor account (the "default instructor") and exactly one open (`EnrollmentMode.OPEN`), listed (`is_listed=true`) `ClassroomRoster` per `Subject` owned by that account — always present regardless of whether any other instructor has registered or created a roster for that subject.
- **FR-015**: The default instructor's per-subject rosters MUST appear in the existing guardian class directory (spec 041 FR-017–FR-021) exactly like any real instructor's own open, listed roster for that subject, with no special-casing beyond always existing — a guardian chooses freely among all available rosters for a subject.
- **FR-016**: When a new `Subject` is added to the content catalog (spec 040's pattern), a corresponding default-instructor-owned roster for it MUST be seeded as part of adding that subject — no manual, subject-specific step beyond what adding a subject already requires (Constitution Principle III: no subject-id-keyed conditional logic).
- **FR-017**: A guardian MUST be able to assign a quiz to their own enrolled learner on a default-instructor-owned roster directly from their own guardian session, via one new, narrowly-scoped backend endpoint. This endpoint MUST only succeed when (a) the target roster is owned by the default instructor specifically, and (b) the target learner belongs to the requesting guardian and is enrolled in that roster. A guardian MUST NOT be able to assign a quiz on any roster not owned by the default instructor.
- **FR-018**: The default instructor account MUST also work as an ordinary real instructor account on the existing, unmodified instructor sign-in and Dashboard/Review/Rosters screens (FR-001–FR-003) — the Cognivo operator may sign in with it directly to review flagged questions or assign quizzes manually. No new review or assignment logic is introduced for this path.
- **FR-019**: The default instructor account MUST have `is_demo = false` (Constitution Principle VIII) — it is a real, operationally-used account, not a demo/showcase account, and MUST NOT be presented to end users as one.
- **FR-020**: The default instructor's email and password MUST be supplied via environment variables at seed time (never committed to the repository), hashed the same way normal instructor registration hashes a password. The seed step MUST be idempotent — re-running it against an already-seeded environment MUST NOT create a duplicate account or silently overwrite an operator-changed password.

### Key Entities

- **RealInstructorAccount** (existing, extended): gains theme/larger-text/reduce-motion display-preference columns (mirroring `RealGuardianAccount`), a default roster join-policy column (`EnrollmentMode`, `OPEN`/`CLOSED`), a default quiz due-date-offset column (nullable integer day-count; `null` = no due date), a notification-preference column, two lockout columns (`failed_login_attempts`/`locked_until`, mirroring `RealGuardianAccount`'s own PR #109 brute-force fix — needed because FR-006's password-change endpoint mirrors the guardian endpoint's lockout protection, not just its happy path), and `password_changed_at` (mirroring `RealGuardianAccount`'s own session-invalidation-on-password-change column, added during PR #111 review). Nine new columns total. No new entity.
- **Default instructor account**: one seeded `RealInstructorAccount` row, `is_demo=false`, credentials held only by the Cognivo operator. Owns exactly one `ClassroomRoster` per `Subject` (`enrollment_mode=OPEN`, `is_listed=true`), seeded alongside each subject (FR-014/FR-016). No new entity type — a normal instructor account and normal rosters, just seeded rather than self-registered.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of Dashboard, Review, and Rosters, reviewed side by side against its mockup, matches the mockup's color, typography, spacing, radius, and shape values with zero unintentional deviations.
- **SC-002**: 100% of the existing frontend automated test suite for Dashboard/Review/Rosters passes unchanged after the redesign, with no test requiring a behavioral (non-visual-selector) change to keep passing.
- **SC-003**: An instructor completes each of the five new Settings actions (change password, change theme, set a classroom default, request a learner's data deletion, request own-account deletion) successfully in a single visit, using only the existing/extended endpoints named in FR-006/FR-007/FR-009/FR-011.
- **SC-004**: The demo-account indicator is present and visible on 100% of demo-instructor Settings views, and password-change/account-deletion are confirmed unavailable for that account in the same view.
- **SC-005**: Zero notifications are ever sent as a result of toggling the Settings notification preference, confirmed by the absence of any notification-sending code path in this feature's implementation.
- **SC-006**: Every subject in the content catalog has at least one joinable class available to any guardian at all times, regardless of real-instructor registration — verified for every subject currently in the catalog.
- **SC-007**: A guardian completes "join a default-instructor class, then assign a quiz to their enrolled learner" in a single session, with zero real-instructor-account involvement.
- **SC-008**: Zero guardian sessions can create a quiz assignment on any roster not owned by the default instructor — verified by attempting it and confirming denial.

## Assumptions

- The four mockups are reference-only (styling values to replicate; markup, component structure, and any sample copy/data are not meant to be copied as-is), the same treatment `specs/027-learner-ui-redesign` gave its own mockups.
- The Dashboard/Review/Rosters restyle and the new Settings screen (User Stories 1-2) are a design-system update plus one bounded new screen, the same category as the unnumbered `specs/027-learner-ui-redesign`/`specs/041-guardian-public-ui-redesign`. The default-instructor capability (User Story 3) is a genuine new product capability, not a content/presentation addition — per user direction, this feature as a whole is tracked as **Milestone 25** in `roadmap.md` (added 2026-10-07), rather than splitting the restyle and the new capability across a milestone entry and an unnumbered note.
- "Classroom defaults" affect only the pre-filled state of the roster-creation and quiz-assignment forms; they are never enforced or retroactively applied, per the Edge Cases above.
- The Notifications section persists a preference with no delivery mechanism, per explicit user decision — a future feature would need its own spec (and a `tech-stack.md` update, given the Vercel serverless constraint on background delivery) before anything is actually sent.
- No real learner data is newly exposed; the learner-deletion picker in Settings only lists learners already visible to the instructor via their own rosters today.
- The default instructor's display name is a clear, non-personal name (e.g. "Cognivo") so it reads as a platform-owned class wherever it appears in instructor- or guardian-facing UI; the exact copy is a presentation detail, not a literal requirement.
- "All subjects" (FR-014/FR-016) means every `Subject` row in the content catalog, present and future, kept true as the catalog grows (spec 040) by tying default-roster seeding to subject addition itself, with zero subject-id-keyed conditional logic (Constitution Principle III).
- The default instructor's password is set and held by the Cognivo operator via environment variables (FR-020), the same operational posture as any other seeded credential (e.g. `DATABASE_URL`); this spec does not define a separate recovery/reset flow for it beyond what already exists for any instructor account. If the operator changes the password later via the normal instructor change-password flow (FR-006), the seed step's idempotency (FR-020) must not revert it on a later re-run.

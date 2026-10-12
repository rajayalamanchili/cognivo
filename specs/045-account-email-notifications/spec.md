# Feature Specification: Account Email Notifications

**Feature Branch**: `045-account-email-notifications`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Guardian and instructor accounts can request a password reset via an emailed link when locked out (not just change password while logged in), and the platform gains a general transactional-email capability also used to notify on registration and on account-deletion-request submission."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A locked-out guardian or instructor resets their password by email (Priority: P1)

A guardian or instructor who has forgotten their password, and therefore cannot use the existing logged-in "change password" control, requests a reset from the sign-in page using just their email address. They receive an email with a link; following it lets them set a new password and signs them in.

**Why this priority**: Today there is no recovery path at all for a locked-out account -- only an authenticated change-password flow exists. A forgotten password is currently a dead end requiring a support/manual intervention. This is the gap that motivated the feature.

**Independent Test**: As a guardian (and separately as an instructor) with a known account email, submit a reset request, retrieve the emailed link, set a new password, and confirm sign-in succeeds with the new password and fails with the old one.

**Acceptance Scenarios**:

1. **Given** a real guardian account exists, **When** the guardian submits a reset request for that account's email from the guardian sign-in page, **Then** an email with a reset link is sent to that address.
2. **Given** an instructor received a valid reset link, **When** they follow it and set a new password, **Then** they are signed in and can subsequently sign in again using the new password.
3. **Given** a reset link has already been used once, **When** it is used again, **Then** the system rejects it and explains the link is no longer valid.
4. **Given** a reset link is older than its expiry window, **When** it is used, **Then** the system rejects it and explains it has expired, with a way to request a new one.
5. **Given** someone submits a reset request for an email with no matching account, **When** the request is submitted, **Then** the response looks the same as a successful request (no email is sent, and nothing in the response reveals whether an account exists).

---

### User Story 2 - A new guardian or instructor receives a registration confirmation (Priority: P2)

Immediately after a guardian or instructor successfully creates a real account, they receive an email confirming the account was created.

**Why this priority**: A lower-stakes convenience/trust signal compared to US1's recovery gap, but it is the most natural second use of the same new email-sending capability and was explicitly requested alongside it.

**Independent Test**: Register a new real guardian account (and separately a new real instructor account) and confirm a registration-confirmation email is sent to the address used.

**Acceptance Scenarios**:

1. **Given** a prospective guardian submits valid registration details, **When** the account is created, **Then** a confirmation email is sent to that address.
2. **Given** a prospective instructor submits valid registration details, **When** the account is created, **Then** a confirmation email is sent to that address.
3. **Given** registration fails validation (e.g., duplicate email), **When** no account is created, **Then** no confirmation email is sent.

---

### User Story 3 - A guardian or instructor is notified when they submit an account/learner-data deletion request (Priority: P3)

When a guardian or instructor submits a request to delete their own account, or a guardian submits a request to delete a learner they manage, the requester receives an email confirming what was requested and that it is now pending.

**Why this priority**: Lowest priority of the three -- useful confirmation, but the existing deletion-request flow already shows a pending status in-app (spec 020); email is a redundant, secondary channel for the same information.

**Independent Test**: Submit a self-account deletion request (and separately a learner-data deletion request as that learner's guardian) and confirm a confirmation email reaches the requester.

**Acceptance Scenarios**:

1. **Given** a guardian submits a request to delete their own account, **When** the request is accepted, **Then** they receive an email confirming the request and that it is pending.
2. **Given** a guardian submits a request to delete a managed learner's data, **When** the request is accepted, **Then** the guardian (not the learner, who has no email of their own) receives a confirmation email.
3. **Given** a deletion request is rejected because one is already pending for that same target, **When** the duplicate request is rejected, **Then** no additional confirmation email is sent.

### Edge Cases

- A reset request for an email that matches a demo account: no email is sent (demo accounts are excluded from all notification types in this feature, consistent with how demo accounts are already treated as a distinct, flagged category elsewhere in the product).
- A reset request for an email that happens to match both a real guardian account and a real instructor account (the two account tables allow the same email in each independently): the request is scoped to whichever sign-in page it was submitted from, since the forgot-password entry point lives on each role's own sign-in page.
- Multiple reset requests for the same account in quick succession: the most recently issued link remains valid; any earlier still-unused link for that account becomes invalid, and requests are rate-limited to prevent abuse of the email-sending capability.
- The outbound email provider is unavailable or the send fails: see FR-012 for how this must not block the triggering action.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Guardians and instructors MUST be able to request a password reset by submitting their account's email from the sign-in page, without being signed in.
- **FR-002**: A reset request MUST deliver a time-limited, single-use reset link by email to the account's address, and the requester-facing response MUST be identical whether or not that email matches a real, non-demo account (no account-enumeration signal).
- **FR-003**: A reset link MUST expire a short, fixed time after being issued (on the order of an hour) and MUST become permanently invalid immediately after its first successful use.
- **FR-004**: Issuing a new reset link for an account MUST invalidate any earlier still-valid, unused reset link for that same account.
- **FR-005**: Completing a reset (following a valid, unused, unexpired link and submitting a new password) MUST set that password and sign the user in, equivalently to a normal login.
- **FR-006**: A completed password reset MUST end the account's other existing signed-in sessions, the same way an authenticated password change already does.
- **FR-007**: The system MUST send a registration-confirmation email to a guardian or instructor immediately after their real (non-demo) account is successfully created; a failed registration MUST NOT send one.
- **FR-008**: The system MUST send a confirmation email to the requester when a deletion request is accepted for their own guardian/instructor account or for a learner they manage; a rejected (e.g., duplicate-pending) deletion request MUST NOT send one.
- **FR-009**: The system MUST also send this deletion-request confirmation when the deletion request is created automatically by the system's own inactivity-based cleanup, not only when the guardian or instructor submits one themselves -- this is the account holder's only advance notice that their inactive account is about to be deleted, so it must reach them regardless of which path created the request.
- **FR-010**: This feature covers notifying when a deletion request is *submitted/accepted* only; it does not add a second notification when that request later actually completes, since the target account's email address is not retained past that point today (data-model.md's own design decision for `/speckit-plan` to confirm or revisit).
- **FR-011**: Demo accounts (guardian, instructor, or demo-learner-owning guardian) MUST NOT receive any notification email defined by this feature.
- **FR-012**: If an outbound notification email fails to send for any reason, the triggering action (registration, reset request, or deletion-request submission) MUST still succeed; the failure MUST be logged for support/audit purposes rather than surfaced to the end user as an error in that action.
- **FR-013**: Every outbound notification email attempt (registration, password-reset, deletion-request) MUST be logged with its type, target account, timestamp, and delivery outcome (sent/failed), independent of whether the send itself succeeded.

### Key Entities

- **Password Reset Token**: A single pending reset request for one guardian or instructor account -- which account and role it belongs to, when it was issued, when it expires, and whether it has already been used. At most one valid (unused, unexpired) token exists per account at a time (FR-004).
- **Notification Log Entry**: A record of one attempted outbound email -- its type (registration / password-reset / deletion-request-confirmation), the target account, when it was attempted, and whether it was delivered or failed (FR-012, FR-013).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A guardian or instructor who has forgotten their password can regain access to their account using only their registered email address, with no support/manual intervention required.
- **SC-002**: 100% of password-reset links that are either expired or already used are rejected when someone attempts to use them.
- **SC-003**: Observing the forgot-password flow's responses alone cannot distinguish an email address that has a real account from one that does not.
- **SC-004**: Every successful real-account registration results in a confirmation email being attempted within seconds of account creation.
- **SC-005**: Every accepted deletion request (self-submitted, guardian-submitted for a learner, or system/inactivity-generated) results in a confirmation email being attempted to the responsible guardian/instructor within seconds of acceptance.
- **SC-006**: A failed or delayed email delivery never prevents or rolls back the registration, reset-request, or deletion-request action it was attached to.

## Assumptions

- Demo accounts are excluded from every notification type this feature defines, matching the project's existing practice of treating demo accounts as a distinct, explicitly flagged category rather than extending real-account-facing capabilities to them by default.
- A guardian's managed learner has no email of their own (confirmed: `LearnerProfile` holds no credential/contact fields); any notification about a learner's data goes to the managing guardian instead.
- The forgot-password entry point is reached from each role's own existing sign-in page (guardian vs. instructor), so which of the two account tables a reset applies to is already known from context and never needs to be guessed or disambiguated.
- Reset links are single-use with a short, fixed expiry (on the order of an hour); the reset-request endpoint is rate-limited per account to deter abuse of the new email-sending capability.
- A successful password reset invalidates the account's other active sessions, reusing the same session-invalidation behavior that an authenticated password change already has.
- This feature's "general transactional-email capability" is sized for exactly the three trigger points named here (password reset, registration, deletion-request submission); building a general-purpose notification-template system for future, as-yet-unspecified email types is explicitly out of scope.
- Which outbound email provider/technology sends the email is a `/speckit-plan` decision -- no choice exists today in `tech-stack.md`, and none is fixed by this spec.
- Account-deletion *completion* (as opposed to the request being accepted) does not get its own notification in this feature (FR-010); the target's email address is not retained once the account row is cascade-deleted, and retaining a snapshot purely to support this would be a data-model change this spec defers to `/speckit-plan` to evaluate, not one it requires.

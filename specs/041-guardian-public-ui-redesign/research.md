# Phase 0 Research: Guardian & Public-Facing UI Redesign

All decisions below resolve a design question the spec deliberately left
to `/speckit-plan` (per its Assumptions section). No `NEEDS CLARIFICATION`
markers remain in the Technical Context -- every row there is already
locked by `tech-stack.md` or directly inherited from spec 027's precedent.

## 1. Real-learner session mechanism (spec FR-016/FR-022)

**Decision**: Extend `frontend/src/lib/visitor-state.ts`'s existing
demo-learner-mode pattern with a second, parallel client-side signal:

```ts
const REAL_LEARNER_SESSION_KEY = "cognivo:real-learner-session"; // JSON: {learnerId, displayName}

getRealLearnerSession(): {learnerId: string; displayName: string} | null
enterRealLearnerSession(learnerId: string, displayName: string): void  // sets localStorage, calls notifySessionChanged()
exitRealLearnerSession(): void                                         // clears localStorage, calls notifySessionChanged()
```

`Nav.tsx`'s `useVisitorState`/`bucketFor` gains a `"real-learner"` bucket,
checked when `accountType === "guardian"` AND a real-learner session is
active (otherwise falls back to today's plain `"guardian"` bucket). A new
`REAL_LEARNER_LINKS` array (Dashboard, Practice, Mastery, AI Tutor -- no
Placement, since real placement stays out of scope per spec Clarifications)
renders through the *existing* plain-link code path (`bucket !== "demo-learner"`
branch), not the demo-learner-only pill-styled branch -- this is what keeps
FR-014's "no new layout/shape on out-of-scope screens" guarantee intact
with zero new styling code. The real-learner identity renders next to the
existing guardian Sign-Out control, with a new "Exit learner view" action
that calls `exitRealLearnerSession()` and navigates to `/guardian/learners`
(satisfying FR-022's clean-session-end requirement).

**Rationale**: `visitor-state.ts`'s own comment already states exactly the
problem this reuses: "a same-tab 'session changed' event... anything that
changes the visitor's identity... must explicitly notify [Nav] to refetch."
A real-learner session is the same *kind* of signal (no session cookie of
its own -- the guardian's own cookie still authenticates every request;
this is purely "which learner is the guardian currently acting for")
as demo-learner-mode, which exists for the structurally identical reason
(no session cookie for an anonymous demo flow). Reusing the mechanism
costs zero new infrastructure and zero new concepts for a future reader.

**Alternatives considered**:
- *A new server-side "active learner" session field on the guardian's JWT*: rejected. It would require re-issuing the guardian's session cookie every time they switch learners (an extra round trip per switch) for a signal that's purely a UI-routing concern, not an authorization one -- every actual data request is still authorized by `require_learner_ownership_if_real` checking the guardian's own session against that specific `learner_id`, regardless of which "mode" the nav thinks it's in.
- *A URL query param (`?learnerId=...`) on each of the four routes*: rejected as the sole mechanism -- it would need to be threaded through every internal link on Dashboard/Practice/Mastery/Tutor (including ones rendered by shared sub-components that don't currently take a learner-aware prop), multiplying the diff for no behavioral gain over a single localStorage signal the same four flow components already read directly.

## 2. Guardian account-edit, password-change, and preference storage (FR-009/FR-011)

**Decision**: Add seven new flat columns directly onto existing tables,
zero new tables:

- `real_guardian_accounts`: `name: str | None`, `read_aloud_default: bool default False`, `larger_text: bool default False`, `reduce_motion: bool default False`, `theme: str default 'system'`, `quiz_finished_email_enabled: bool default True`, `weekly_summary_enabled: bool default False`.
- `learner_profiles`: `practice_reminders_enabled: bool default False` -- the one genuinely per-learner toggle the mockup shows (`"Practice reminders for Eli"`), not per-guardian.

New routes in `auth.py`: `PATCH /api/auth/guardian/me` (name/email/all six
preference fields in one call -- email-uniqueness-checked the same way
`register_guardian` already is) and `POST /api/auth/guardian/change-password`
(verifies `current_password` via the existing `verify_password`, re-hashes
via the existing `hash_password`). `whoami`'s `WhoAmIOut` gains the guardian's
`name` and preference fields so the Settings page has one GET to hydrate
from, instead of a second new endpoint.

**Rationale**: `LearnerProfile.career_connections_enabled` is this
codebase's own existing precedent for exactly this shape of
need (a small, per-account boolean toggle) -- a flat column on the owning
entity, not a separate preferences table. Seven columns across two
already-existing tables is a smaller, more consistent diff than a new
`guardian_preferences` table plus the join every read of it would then
need, for no normalization benefit (nothing here is repeated-per-row data).
Reusing `whoami` for the read side avoids a second "get my settings"
endpoint duplicating logic `whoami` already has for resolving `claims` to
an account row.

**Alternatives considered**:
- *A new `guardian_preferences` table (one row per guardian)*: rejected -- normalization has no payoff here (each guardian has exactly one preferences row, 1:1 with `real_guardian_accounts`, so it's really just a vertical table split with no independent lifecycle).
- *A single JSON/JSONB column for all six toggles*: rejected -- loses column-level type-checking and makes a future individual-field migration (e.g. adding a NOT NULL constraint to one toggle) harder than altering one typed column; six booleans/one string is not remotely wide enough to justify JSON's flexibility trade-off.

## 3. Instructor display name and the class directory (FR-017-FR-021)

**Decision**: Add `display_name: str | None` to `real_instructor_accounts`
(mirrors `real_guardian_accounts.name` above -- same column shape, same
nullable-until-set treatment). Add `is_listed: bool default False` to
`classroom_rosters`. Extend `rosters.py`'s existing `UpdateRosterIn` to
accept `is_listed: bool | None`, with `update_roster_enrollment_mode`
(or a new sibling helper called alongside it) rejecting `is_listed=True`
when `enrollment_mode == CLOSED`, and forcing `is_listed=False` whenever
`enrollment_mode` is set to `CLOSED` (FR-018's mutual-exclusion rule,
enforced at the application layer, not a DB constraint -- same precedent
`LearnerProfile`'s own docstring already establishes for a structurally
identical "no portable cross-column DB check without a trigger" case),
and rejecting `is_listed=True` whenever the owning instructor's
`display_name IS NULL` (`instructor_display_name_required`), applied
identically to a brand-new and a pre-existing instructor account --
`register_instructor` itself is not changed to require `display_name`
(`/speckit-analyze` finding G1): requiring it there would reject every
existing instructor-registration call site (roughly three dozen test
files, plus any direct API caller) for a guarantee that only actually
needs to hold at the one moment it matters, listing a roster. The
frontend's "List in directory" toggle (`rosters-flow.tsx`) surfaces the
`instructor_display_name_required` error as an inline prompt calling
`PATCH /api/auth/instructor/me` right there, so a new instructor sets
it the first time they need it instead of at an earlier point nothing
can actually enforce.

New route: `GET /api/rosters/directory`, gated by `current_guardian` (same
auth dependency `join_roster_route` already uses), returning every roster
where `is_listed = true` and `enrollment_mode = OPEN`, joined to its
`real_instructor_accounts.display_name`, including that roster's
`join_code`. No new join endpoint: the frontend's "join from directory"
action calls the *existing* `POST /api/rosters/join` with the code the
directory response already handed it -- satisfying FR-020's "identical
outcome, not a second enrollment path" literally, not just in spirit.

**Rationale**: Once a roster is `is_listed = true`, its `join_code` is no
longer a secret by the instructor's own explicit choice (FR-018) -- there
is no privacy reason left to withhold it from the directory response, and
doing so would force inventing a second, parallel join mechanism
(`roster_id`-based) purely to avoid showing a value the instructor already
agreed to make discoverable. Reusing the existing code-based join is the
smaller diff and the one the spec's own FR-020 points at directly.

**Alternatives considered**:
- *A new `roster_id`-based join endpoint, keeping `join_code` out of the directory response*: rejected -- doubles the enrollment code path for a code that isn't actually secret anymore once listed, contradicting FR-020's explicit "not a second enrollment code path with different semantics."
- *Making the directory endpoint public (no auth)*: rejected -- the spec frames this as a guardian-facing capability throughout (User Story 5), and every other roster-adjacent read (`list_learner_enrollments_route`, `join_roster_route`) is already guardian-gated; an unauthenticated listing endpoint would be the only exception with no stated need for one.

## 4. Settings page route

**Decision**: `(auth)/guardian/settings/page.tsx`, a new route alongside
the existing `(auth)/guardian/learners/page.tsx` -- not the existing
top-level `/settings` route, which is a *different*, pre-existing,
demo-learner-only page (`CareerConnectionsToggle`, spec 039 FR-011)
entirely unrelated to this feature's guardian Settings.

**Rationale**: The two "Settings" concepts belong to different roles and
different data (a demo learner's one toggle vs. a guardian's account,
preferences, and managed learners) and must not collide at the same URL.
`(auth)/guardian/learners/page.tsx` is the direct structural precedent for
where a new guardian-role page under this auth group belongs.

**Alternatives considered**: Reusing `/settings` and branching its content
on session type was considered and rejected -- it would conflate two
unrelated features' routing logic in one file for no shared benefit, where
the existing `(auth)/guardian/*` route group already exists specifically
to keep guardian pages together.

## 5. Guardian learner-listing endpoint (FR-023)

**Decision** (added during `/speckit-analyze`): Add `GET /api/learners/mine`
to `backend/src/api/routes/learners.py` (the file `POST /api/learners`
already lives in), guardian-only (`current_guardian`). Returns every
`LearnerProfile` where `guardian_id == guardian.guardian_id`, each with
`learner_id`, `display_name`, and `enrollment: {roster_id, subject_id,
grade} | null` -- the enrollment join is the same `Enrollment`-joined-to-
`ClassroomRoster` pattern `list_learner_enrollments_route`
(`rosters.py`) already uses, extended with `ClassroomRoster.grade`. No
pagination (bounded by one guardian's own learner count).

**Rationale**: Guardian · My learners (FR-008, FR-016), Settings' Learners
section (FR-010), and the class directory's "pick a learner to enroll"
step (FR-019) all need the guardian's *persisted* learner set, not just
the ones added in the current browser tab -- `addedLearners` in
`learners/page.tsx` is `useState` only, lost on reload. No existing
endpoint returns this (`/speckit-analyze` finding I1/U1): the closest is
`list_learner_enrollments_route`, which is per-`learner_id` and so
already presupposes the caller knows which learners exist. This is the
smallest addition that closes the gap -- one read endpoint on an
already-existing router file, reusing an already-existing join pattern,
with the demo learner naturally excluded (its `guardian_id` is always
`NULL`, never equal to a real guardian's id).

**Alternatives considered**:
- *Extend `whoami` to embed the learner list*: rejected -- `whoami` is called on every page load by `Nav`/`DemoBadge` regardless of which page is showing; embedding a guardian's full learner-plus-enrollment list in every one of those calls is unnecessary payload for pages that never render it (Dashboard, Practice, Mastery, Tutor, Settings' non-Learners sections).
- *Leave this out of scope and keep today's session-only list*: rejected -- it would make Story 4's and Story 5's own Independent Test criteria ("open that learner's session from their card" for an already-enrolled learner) untestable after a reload, the exact gap `/speckit-analyze` flagged.

## 6. Guardian password-change session invalidation (Edge Cases, FR-022)

**Decision** (added during `/speckit-analyze`): Add
`password_changed_at: datetime | None` to `real_guardian_accounts`, set
to `now()` inside `POST /api/auth/guardian/change-password`'s existing
handler. Extend `tokens.py`'s `SessionClaims` with an `issued_at`
field, populated in `verify_token` from the JWT's own `iat` claim
(already written by `issue_token`, previously decoded and discarded).
`dependencies.py`'s `current_guardian` rejects (`AuthenticationError`)
whenever `guardian.password_changed_at` is not `None` and is newer than
`claims.issued_at` -- i.e. any session token issued before the most
recent password change is treated as invalid on its very next use.

**Rationale**: This app's guardian session is a stateless, 30-day JWT
cookie with no server-side session store (`tokens.py`'s own docstring,
Constitution Principle IX) -- so "changing a password invalidates other
sessions" cannot mean revoking a token server-side; it has to mean
rejecting any token that predates the change. Comparing against the
token's own `iat` reuses a claim that already exists on every token
today, at the cost of one new nullable timestamp column and one new
dataclass field -- no server-side token/session registry, no
denylist, nothing that would reintroduce the in-memory state Principle
IX rules out.

**Alternatives considered**:
- *A server-side session/token-denylist store*: rejected -- exactly the persistent, stateful mechanism Constitution Principle IX's serverless constraint exists to avoid; also strictly more mechanism than comparing two timestamps already on hand.
- *Shortening the JWT TTL instead*: rejected -- even a same-day TTL would still leave a window where "change your password because you think your old one leaked" doesn't actually stop a session already open elsewhere, which is the entire point of the Edge Case; TTL and invalidation-on-change solve different problems and aren't substitutes for each other.
- *Leave unaddressed, treat 30-day exposure as acceptable*: rejected -- the spec's own Edge Case already states the requirement in MUST-adjacent language ("should not silently keep working"); a 30-day window is long enough that this isn't a edge case worth waiving.

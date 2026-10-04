# Research: STEM-Career Connections

No `NEEDS CLARIFICATION` markers remained in `spec.md`'s Technical Context --
every decision below picks between options already fully determined by
reading the existing codebase (`tech-stack.md`, `Topic`/`LearnerProfile`
models, `mastery.py`, `GuardianLearnerStandards.tsx`, `Nav.tsx`), not by new
external research.

## Decision 1: Career-connection storage shape

**Decision**: A single nullable JSON column, `topics.career_connection:
dict | None`, mirroring `Topic.image_asset`'s existing shape exactly
(`{filename, alt_text}` -> here `{career, description}`).

**Rationale**: Spec's Key Entities explicitly scope this to "zero or one
per topic." `StandardsTag` (spec 038) needed its own table because a topic
can carry *several* standards tags; this feature has no equivalent
many-per-topic need, so a second table would be unjustified complexity.
`image_asset` is the exact existing precedent for an optional, single,
per-topic authored object.

**Alternatives considered**: A new `career_connections` table (rejected --
one-to-one, not one-to-many, so a table adds a join for no benefit); a list
field allowing multiple careers per topic (rejected -- not asked for, and
spec's Key Entities already commit to zero-or-one).

## Decision 2: No grade-gating on authoring

**Decision**: A `career_connection` may be authored on any topic regardless
of `grade` -- unlike `standards_tags` (spec 038 FR-003), which rejects a tag
on an ungraded topic at validation time.

**Rationale**: The grade-gate on standards tags exists because a Common
Core/NGSS code is itself defined per grade band -- tagging an ungraded
topic with one would be a category error. A STEM-career connection carries
no such grade dependency. FR-010 requires real coverage across *both*
existing subjects, including `biology`, which is deliberately ungraded
(spec 038 Scale/Scope) -- a grade-gate here would make FR-010 impossible to
satisfy for `biology`.

## Decision 3: Preference storage and default

**Decision**: A new non-nullable boolean column, `learner_profiles.
career_connections_enabled`, `server_default=sa.true()` -- one flag per
existing `LearnerProfile` row (demo or real), no new table.

**Rationale**: Mirrors `mastery_states.has_been_mastered`'s own
add-boolean-column-with-server-default migration shape exactly. Default
`true` matches spec's Assumptions (content visible unless explicitly
turned off) and needs no backfill logic beyond the column default itself,
since no learner has an existing opinion to preserve.

## Decision 4: Who can read/write the preference

**Decision**: One new endpoint pair, `GET` and `PATCH
/api/learners/{learner_id}/career-connections-preference`, gated by the
existing `require_learner_ownership_if_real()` dependency -- the same
function `mastery.py`/`recommendation.py`/`sequencing_preview.py` already
use for every other learner-scoped read.

**Rationale**: `require_learner_ownership_if_real` is already a no-op for a
demo (or nonexistent) `learner_id`, and already raises `ForbiddenError` for
a real learner when the caller isn't that learner's owning guardian
(`SessionClaims` via `optional_session_claims`). That is *exactly* the
access rule Clarifications settled on: the demo learner is self-service
(no session needed), a real learner's preference is guardian-controlled.
Reusing this dependency for a write, not just existing reads, needs no new
authorization concept.

**Alternatives considered**: Two separate endpoints (one demo-only, one
guardian-only) -- rejected, since the ownership check already
discriminates correctly inside one endpoint, and a future third actor
(e.g. an instructor) would need the same no-new-concept reasoning anyway.

## Decision 5: Where the content surfaces

**Decision**: Extend `MasteryStateResponse` (the response
`GET /api/learners/{learner_id}/mastery-state` already returns, and the
one response both `DashboardSubjectSection.tsx` -- demo learner -- and
`GuardianLearnerStandards.tsx` -- guardian -- already fetch) with
`career_connections: list[CareerConnectionOut]`. Populated only when the
owning learner's `career_connections_enabled` is `true`; empty otherwise.

**Rationale**: Matches spec 038's own `standards` field precedent on this
exact response, which already serves both the demo-learner and
guardian-facing surfaces identically from one computation. Server-side
gating (not a frontend-only hide) is what makes FR-006 ("MUST NOT render
... anywhere") actually true regardless of which frontend code runs --
the same reasoning `standards`'s empty-list-when-no-tags behavior already
establishes, just driven by the preference flag instead of tag absence.

**Alternatives considered**: A frontend-only toggle (fetch always, hide
conditionally) -- rejected, weaker than a server-enforced guarantee and
inconsistent with there being a real backend preference at all (Decision
3/4 already require a backend round-trip to read it).

## Decision 6: Frontend components

**Decision**:
- `CareerConnectionsList.tsx` (new, presentational): renders the matched
  `career_connections` entries against a topic list. Reused, unmodified,
  by both surfaces below.
- `DashboardSubjectSection.tsx` (extended): renders `CareerConnectionsList`
  using the `career_connections` field off its *already-fetched*
  `getMasteryState` call -- no new fetch.
- `GuardianLearnerCareerConnections.tsx` (new, sibling to
  `GuardianLearnerStandards.tsx`): same `listLearnerEnrollments` +
  `getMasteryState`-per-subject fetch shape, extracting
  `.career_connections` instead of `.standards`, rendering
  `CareerConnectionsList`.
- `CareerConnectionsToggle.tsx` (new): fetches/patches the Decision-4
  endpoint for a given `learnerId`, renders a checkbox/switch.
- A new `/settings` page (demo-learner-only, same no-direct-auth-gate
  precedent as `/dashboard`/`/mastery`): resolves the demo learner's id via
  the existing `getDemoLearner()` call, then renders
  `CareerConnectionsToggle`. Linked from `Nav.tsx`'s existing demo-learner
  avatar-menu dropdown (new "Settings" item alongside "Exit Demo"/"Sign
  In").
- `(auth)/guardian/learners/page.tsx` (extended): renders
  `CareerConnectionsToggle` inside the existing per-added-learner `<li>`
  block, alongside `JoinRosterForm`/`GuardianLearnerStandards`/
  `LearnerAssignments` -- same per-session-added-learner scope those three
  already have (this page has no "list my existing learners" endpoint
  today; that gap predates this feature and is not this feature's to
  close).

**Rationale**: `GuardianLearnerStandards.tsx` is deliberately not
overloaded with a second, unrelated responsibility (career-connection
display is a different concern from standards-coverage rollup) -- a
sibling component matching its exact fetch shape is the established
precedent for "two independent cards reusing the same per-subject fetch,"
not a reason to merge them. `CareerConnectionsList`/`CareerConnectionsToggle`
are not plumbed into `MasteryView.tsx` (which backs Placement's
in-session summary too) -- spec's Assumptions explicitly keep this feature
out of assessment-moment UI.

## Decision 7: Migration

**Decision**: One Alembic revision, two `op.add_column` calls (`topics.
career_connection` JSON nullable; `learner_profiles.
career_connections_enabled` boolean, `server_default=sa.true()`,
`nullable=False`). No data backfill needed for either column beyond the
boolean's own server default.

**Rationale**: Both are pure additive schema changes to existing tables,
same shape as `824e2c5a0678_mastery_state_has_been_mastered_column.py`.

# Research: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review

**Feature**: `010-instructor-classroom` | **Date**: 2026-08-23

## §1. Authentication: Argon2id + stateless JWT-in-httpOnly-cookie, no third-party provider

**Decision**: Password hashing via `argon2-cffi` (Argon2id); sessions
are a `pyjwt`-signed token in an `httpOnly`, `Secure`, `SameSite=Lax`
cookie, verified per-request by a FastAPI dependency with no
server-side session store. Locked in `tech-stack.md`'s new
Authentication section (this is the "Instructor auth/identity
approach" decision that file had explicitly deferred since Milestone
1).

**Rationale**: Stateless verification is a direct fit for Vercel's
serverless execution model (Constitution Principle IX) -- no session
store to provision, keep warm, or garbage-collect. Argon2id is OWASP's
current recommended default for new systems (ahead of bcrypt), and this
codebase has no existing hashing dependency to stay consistent with
instead. A third-party auth provider (Clerk, Auth0, Supabase Auth) was
considered and rejected for the same reason this project already
rejected Supabase as its database: the backend owns its own logic
rather than delegating to a client SDK, and a two-role (guardian,
instructor) password-based auth need doesn't approach the complexity
(enterprise SSO, social login, MFA) that would justify an external
provider's cost and dependency surface.

**Alternatives considered**:
- *DB-backed session table*, mirroring the ADK session-service pattern
  already used for agent state: rejected -- that pattern exists because
  ADK's session abstraction needs durable state across agent *turns*;
  a login session has no equivalent turn-by-turn state, so a durable
  store buys nothing beyond what a signed, expiring JWT already
  provides, at the cost of an extra table and query per request.
- *bcrypt* (via `passlib`): a reasonable, widely-used alternative:
  rejected only because Argon2id is the more current recommendation and
  this is a greenfield choice with no existing bcrypt usage to match.

## §2. Two separate account tables, not one polymorphic `users` table

**Decision**: `RealGuardianAccount` and `RealInstructorAccount` stay
two distinct tables (spec 009's data model), each enforcing email
uniqueness independently rather than through one shared table.

**Rationale**: Resolved during `/speckit-clarify` on this spec: the
same person/email may hold both roles (a parent who also teaches). A
single `users` table with a `role` column and a globally-unique email
constraint would block that outright; relaxing it later would need a
migration touching live account data, a materially worse position than
paying one extra "which table did these credentials match" resolution
step at sign-in time now.

## §3. Why spec 009 shipped no migration, and this spec does

**Decision**: This feature's Alembic migration creates all eight new
tables spec 009's `data-model.md` described as forward-looking
(`data-model.md` there: "None of the entities below are persisted by
this spec").

**Rationale**: Spec 009 deliberately deferred the actual schema to
"whoever writes Milestone 7 proper" (its own research.md §4) rather
than create dead tables with no code path using them. This spec is that
consumer -- every table in spec 009's `data-model.md` maps directly to
a model in `backend/src/models/` here, with `ClassroomRoster` gaining
the `subject_id` field spec 009 explicitly left undetermined.

## §4. Dashboard aggregation needs no async fan-out

**Decision**: The instructor dashboard calls
`build_weak_area_report(db, learner_id=..., subject_id=...)` once per
enrolled learner, in a plain synchronous loop -- no `asyncio.gather`,
no background job, no caching layer.

**Rationale**: `build_weak_area_report` makes no LLM or network call
(`recommendation.py`'s own docstring: "makes no LLM/ADK invocation") --
it's pure Postgres-query topic classification. A 30-learner roster (the
realistic class-size ceiling this spec's Performance Goal is set
against) is 30 in-process function calls each doing a handful of
indexed queries, not 30 external round trips. Introducing async
parallelization for calls that are already fast and CPU/DB-bound rather
than I/O-blocked-on-a-remote-service would be complexity this feature
doesn't need -- revisit only if real class sizes or query cost turn out
larger than assumed here.

## §5. Content-review queue query: join through `Enrollment`, not a denormalized instructor reference on `GeneratedQuestion`

**Decision**: "Every flagged question belonging to a learner on this
instructor's roster" (FR-011) is computed by joining `GeneratedQuestion`
(filtered to `validation_status = flagged`) through `Enrollment` to the
instructor's `ClassroomRoster` rows -- `GeneratedQuestion` itself gains
no new instructor-facing column.

**Rationale**: A learner's roster membership can change (enrollment,
unenrollment, FR-007a) after a question was already generated and
flagged; a denormalized `instructor_id` snapshotted onto
`GeneratedQuestion` at generation time would go stale the moment that
learner's enrollment changes, silently misrouting review visibility.
Joining live through `Enrollment` at query time means the access-control
boundary (spec 009 FR-006, this spec's FR-010) is always correct as of
right now, matching how the dashboard itself (§4) is also computed
live rather than from a cached/denormalized snapshot.

## §6. Content-review action scope: triage only, confirmed

**Decision**: Confirms spec.md's Assumption -- an instructor can mark a
flagged question reactivated or permanently rejected (FR-012); this
milestone builds no content-authoring UI (writing new questions from
scratch) and no in-place editing of a flagged question's own text.

**Rationale**: Restated here (not re-litigated) because it's a real
implementation-scope boundary: `content_review/resolution.py` (Project
Structure) needs no rich-text editor, no re-validation-against-rubric
pipeline for edited content, and no new LLM call -- it's a two-state
status transition plus an audit event (FR-013). A future authoring
feature, if ever needed, would be a distinctly larger, separate spec
per `roadmap.md`'s own convention of not folding unrelated axes into
one milestone.

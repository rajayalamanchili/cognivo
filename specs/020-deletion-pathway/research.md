# Research: Real-Account Deletion Pathway

**Feature**: `020-deletion-pathway` | **Date**: 2026-09-21

Every item below resolves a design question the spec deliberately left
to planning (its Assumptions section flags each one). None reopen
spec 009's already-approved policy (30-day SLA, 1-year inactivity
ceiling, hard-delete-only, guardian/instructor/institution as
requesters) -- that stays exactly as decided.

## R1. Execution mechanism: Vercel Cron, not inline-on-request

**Decision**: The submission endpoint (`POST /api/deletion-requests`)
only creates a `DeletionRequest` row (`completed_at = NULL`). A new
Vercel Cron job, `GET /api/cron/execute-deletions`, processes pending
requests on a schedule and performs the actual cascade delete.

**Rationale**: Matches `tech-stack.md`'s already-locked Misconception
Classifier pattern (`/api/cron/classify-misconceptions`) exactly: no
persistent background process exists on Vercel (Deployment-target
section), and a cascade across ~10 tables for an account with a long
history could plausibly approach the shared `maxDuration: 30` budget if
run inline on the submission request. The 30-day SLA gives enormous
scheduling slack -- a daily cron clears any single request in at most
24 hours, two orders of magnitude inside the deadline.

**Alternatives considered**: Synchronous deletion on the submission
request -- rejected, risks the request itself timing out on a
data-heavy account and offers no batching/backoff if many requests
arrive at once (e.g. an instructor deleting a whole roster's worth of
inactive learners in one sweep).

## R2. Cascade implementation: explicit application-level walk, not DB `ON DELETE CASCADE`

**Decision**: A new service (`backend/src/services/deletion/execute.py`)
deletes rows in explicit dependency order inside one DB transaction per
target -- either the whole cascade commits and `completed_at` is set,
or it rolls back and the request stays pending for the next cron run.
No new `ondelete="CASCADE"` FK options are added.

**Rationale**: Two reasons DB-level cascade doesn't fit here:
1. **Constitution Principle V** (every decision logged and explainable)
   has no hook point in a database-cascade delete -- an application-level
   walk can log what was removed per table, a blanket `ON DELETE
   CASCADE` cannot.
2. **Not every FK should cascade the same way.** `generated_questions.
   flagged_by` (nullable, spec 001 FR-011) points at the learner who
   flagged a question -- not necessarily the learner who owns it. A
   blanket cascade would delete a still-owned-by-another-learner
   question just because a different learner who once flagged it was
   deleted. This needs `SET NULL`, not `DELETE`, and a single DB-level
   cascade policy can't express that distinction per-column the way
   explicit code can.

**Alternatives considered**: Adding `ondelete="CASCADE"` across every
learner/instructor/guardian-referencing FK -- rejected for the two
reasons above; also would touch nearly every existing migration's FK
definitions for a one-time win that a transaction-wrapped application
walk achieves just as reliably.

## R3. Deletion order per target type

Documented as ordered table lists in `data-model.md`, derived by
walking the actual FK graph in `backend/src/models/` (not re-derived
from scratch -- this is exactly the graph spec 009's FR-005 already
promised to cascade across).

## R4. Guardian-targeted deletion cascades to that guardian's learners

**Decision**: An explicit `DeletionRequest` targeting a
`RealGuardianAccount` cascades to hard-delete every `LearnerProfile`
linked to that guardian (`learner_profiles.guardian_id`), not only the
guardian's own `email`/`password_hash`.

**Rationale**: Spec 009 FR-003 makes the guardian the sole holder of
the learner's login credential -- there is no "transfer the credential
to someone else" option the way an instructor's roster can transfer
ownership (R5). Deleting only the guardian row would leave an
unreachable, permanently-locked-out learner record behind, which is
neither a genuine erasure (the learner's data still exists) nor a
usable account (nobody can ever log in as that learner again). This is
also consistent with `data-classification.md`'s existing statement that
a guardian is auto-deleted once their *last* linked learner is deleted
-- treating the guardian and their learners as one linked deletion unit
in the guardian-initiated direction too, rather than only in the
learner-initiated direction, keeps the rule symmetric.

**Alternatives considered**: Deleting only the guardian's own identity
fields and leaving learner rows orphaned -- rejected per the rationale
above. Requiring a guardian to request deletion once per linked learner
first -- rejected as needless friction for what is functionally one
family's exit from the platform.

## R5. Instructor-targeted deletion: roster disposition via an optional successor at submission time, no schema change

**Decision**: `POST /api/deletion-requests` accepts an optional
`transfer_rosters_to` instructor id when `target_type = "instructor"`.
If provided, roster ownership (`classroom_rosters.instructor_id` --
already a plain, non-FK column per its own existing docstring) is
reassigned synchronously as part of handling the submission, before the
`DeletionRequest` is created. If omitted, the async cascade deletes the
instructor's rosters (and the roster-scoped `quiz_assignments`/
`quiz_assignment_targets` rows -- instructor-owned scheduling metadata)
without touching any enrolled learner's own account, mastery state, or
quiz history (FR-008).

**Rationale**: The spec's own Assumptions section already ruled out
inventing a successor-selection heuristic -- a human (the instructor,
their institution) picks the successor if one exists. Doing the
reassignment synchronously at submission time, rather than adding a
`transfer_target_id` column to `DeletionRequest`, keeps spec.md's Key
Entities claim true ("adds no new fields") and avoids a schema change
for a value that's only ever needed once, immediately, not something
the async cascade needs to remember across a cron run.

**Alternatives considered**: Adding a `transfer_target_id` column to
`DeletionRequest` -- rejected as an unnecessary schema change for a
value with no reason to outlive the single request that uses it.

## R6. "Institution" requester (spec 009 FR-004): no new auth role

**Decision**: An institution-initiated deletion request is submitted
through the same instructor-session-authenticated endpoint an
instructor already uses. No fourth `SessionClaims.account_type` is
added.

**Rationale**: `src/services/auth/dependencies.py`'s `SessionClaims.
account_type` today only has `guardian` / `instructor` /
`demo_instructor` -- this product exercises institutional
administration through an instructor account, not a distinct role.
Spec 009 named "institution" as a possible requester in FR-004's text,
but nothing in this codebase's actual auth model treats it as a fourth
identity, and inventing one is out of proportion to what this milestone
needs to close the Principle VIII gap.

**Alternatives considered**: A new `institution` account type -- deferred
indefinitely; no current feature depends on it existing, and Milestone
7's classroom model already routes institutional actions through the
instructor role.

## R7. Demo-account guard checked at both submission and execution

**Decision**: `POST /api/deletion-requests` rejects a request whose
target has `is_demo = true` (FR-007) at submission time -- the primary
guard, giving the caller an immediate, clear rejection. The cron
executor (`execute-deletions`) re-checks `is_demo` immediately before
acting on any request it processes, as a second gate.

**Rationale**: Matches this codebase's existing pattern of the same
Principle VIII check appearing at more than one layer rather than
trusting a single call site forever (e.g. FR-008 elsewhere in spec 009
is its own dedicated automated check, not just a submission-time
guard). The gap between submission and a cron run reaching that request
is small (R1: daily) but non-zero, and the cost of re-checking one
boolean column is negligible next to what a wrongly-deleted demo
seed would cost to notice and repair.

**Alternatives considered**: Checking only at submission time --
rejected as a single point of failure for a Principle VIII guarantee
this project treats as non-negotiable elsewhere.

## R8. Inactivity sweep folded into the same cron job, not a second one

**Decision**: `GET /api/cron/execute-deletions` runs two phases in one
invocation: first, it scans `RetentionRecord` rows inactive for more
than a year (per spec 009 FR-010) that don't already have a pending
`DeletionRequest`, and creates one for each; then it processes pending
`DeletionRequest` rows, oldest-first, up to a batch cap
(`MAX_DELETIONS_PER_RUN`), mirroring the Misconception Classifier's
existing `MAX_PAIRS_PER_RUN`/watermark pattern (`tech-stack.md`'s
Misconception classifier table).

**Rationale**: One cron entry, one auth check, one batch-cap knob --
simpler than registering a second `vercel.json` cron path and a second
`CRON_SECRET`-gated route for what is, functionally, just a second way
a `DeletionRequest` row gets created before the same executor drains
the queue.

**Alternatives considered**: A separate `/api/cron/sweep-inactive-
accounts` job -- rejected as an unnecessary second moving part; nothing
about the inactivity check needs to run on a different schedule than
the executor that would immediately act on what it finds.

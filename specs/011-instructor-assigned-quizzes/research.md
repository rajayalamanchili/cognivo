# Research: Instructor-Assigned Quizzes

**Feature**: `011-instructor-assigned-quizzes` | **Date**: 2026-08-23

## §1: Assignment tracking as a join entity, not new columns on `QuizSession`

**Decision**: Add two new tables (`quiz_assignments`, `quiz_assignment_targets`)
rather than adding `assignment_id`/`due_at` columns directly to the
existing `quiz_sessions` table. `QuizSession`, `GeneratedQuestion`, and
the `answer_question` grading/mastery-update path (`questions.py`) are
not modified at all.

**Rationale**: FR-007/FR-008 (spec.md) require the exact same
difficulty-adaptation and grading mechanism Milestone 5 established, no
new logic path. Keeping `QuizSession` structurally untouched makes that
a structural guarantee, not just a stated intent -- there is no
"assignment-aware" branch inside the quiz/grading code for a reviewer
to have to verify is actually behaviorally identical, because the code
that runs is literally the same code. An assignment attempt is just an
ordinary `QuizSession` (created via the existing `start_quiz()`) that
happens to be linked, via the new join row, to a `QuizAssignment`.

**Alternatives considered**: Adding `assignment_id`/`target_learner_id`
columns to `quiz_sessions` directly -- rejected because it conflates two
different lifecycles (a quiz session's own in-progress/completed state,
already fully modeled by `QuizSessionStatus`, versus an assignment's
per-student targeting, which needs to exist *before* any `QuizSession`
row does, e.g. a learner who was targeted but never started). The
existing `quiz_session_id` nullable-FK-on-`GeneratedQuestion` pattern
(spec 005) is precedent in this codebase for exactly this shape of
"optional linkage added via a nullable FK on the many side," reused
here as "optional linkage via a nullable FK on the join row" instead.

## §2: Guardian-mediated access, added as a conditional check on existing routes

**Decision**: `POST /api/quizzes` is not modified. A new endpoint,
`POST /api/assignments/{assignment_id}/learners/{learner_id}/start`,
requires `current_guardian` (existing dependency, `services/auth/
dependencies.py`), verifies the guardian owns the targeted learner and
the learner is actually targeted, then calls the exact same
`start_quiz()` / `generate_quiz_question()` service functions
`POST /api/quizzes` already calls. The two existing continuation
routes, `GET /api/quizzes/{quiz_session_id}/next-question` and
`POST /api/questions/{question_id}/answer`, gain one additional check
each: if the `QuizSession`/`GeneratedQuestion` in question is linked to
a `QuizAssignmentTarget` row, the request must carry a valid guardian
session matching that target's learner's `guardian_id` (`Cookie`-based,
same `current_session_claims` primitive `rosters.py`'s
`delete_enrollment_route` already uses for an either/or authorization
check) -- if it is *not* assignment-linked (the existing demo/M5 quiz
path), behavior is completely unchanged, no auth required.

**Rationale**: Spec.md's FR-006/FR-013 require only the targeted
learner's own guardian be able to start *or continue* an assigned
attempt -- Milestone 5's quiz endpoints were originally built
capability-URL-style (possession of the UUID is the only check, an
acceptable trust model for the demo-only learner they were built for)
and have no session concept at all today. Duplicating
`next-question`/`answer` into assignment-specific copies would violate
research.md §1's "exact same mechanism" guarantee at the route layer
even if the underlying service calls stayed shared. A conditional check
gated on "is this session assignment-linked" preserves both: zero
behavior change for the pre-existing demo/M5 path, and a real
authorization boundary for the new real-guardian path.

**Alternatives considered**: A new learner-facing login/session
(rejected in spec.md's Clarifications -- out of scope, real scope
increase for no stated need this milestone). Leaving assignment
continuation fully unauthenticated, relying only on `quiz_session_id`'s
UUID-unguessability (rejected -- acceptable for a synthetic demo
learner per Constitution Principle VIII's framing, not for a real
minor's account once a real guardian session exists to check against).

## §3: Single attempt and due-date enforcement at start-time, backed by a DB constraint

**Decision**: `quiz_assignment_targets` carries a unique constraint on
`(assignment_id, learner_id)` and a nullable `quiz_session_id`. Starting
an attempt is only permitted when that row's `quiz_session_id` is still
`NULL`; the start endpoint sets it in the same transaction it creates
the `QuizSession`. The due-date check (`now() > quiz_assignments.due_at`)
is a plain comparison in the start endpoint, not a scheduled job or a
stored "is this assignment closed" flag.

**Rationale**: FR-014 requires at most one attempt per learner per
assignment. A DB-level uniqueness constraint on the target row (already
created once per targeted learner at assignment-creation time, per
FR-005) makes "no second attempt" an invariant the database itself
enforces under concurrent requests, not just an application-layer check
racy under a double-click -- the same reasoning `uq_enrollments_learner_
roster` (`services/roster/enrollment.py`) already documents for the
comparable "no duplicate enrollment" case in this codebase. A due-date
check needs no background job or status flag because it is only ever
evaluated at the one moment it matters (someone attempting to start),
consistent with Constitution Principle IX's serverless/stateless
constraint -- no assumption of a persistent process to "close"
assignments on a timer.

**Alternatives considered**: A scheduled Vercel Cron job (the pattern
`tech-stack.md`/Milestone 7 already uses for demo-data reset) that
flips assignments to a `closed` status at their due date -- rejected as
unnecessary complexity; the check is a single timestamp comparison
already available at the only request path that needs it.

## §4: Assignment's target list is a snapshot, computed once at creation

**Decision**: `POST /api/rosters/{roster_id}/assignments` writes one
`quiz_assignment_targets` row per selected (or, for "all," per
currently-enrolled) learner at creation time. No code path later
re-derives or updates that target list from `Enrollment` rows.

**Rationale**: Directly implements FR-005/spec.md Acceptance Scenario
1.4 (a learner enrolled after assignment creation is not retroactively
targeted). Snapshotting at creation is also simpler than tracking a
live "roster membership at time T" query for reporting purposes later.

## §5: Per-assignment reporting is a new, separate query -- not routed through the Recommendation Agent

**Decision**: `GET /api/rosters/{roster_id}/assignments/{assignment_id}`
computes each targeted learner's status/score directly from
`quiz_assignment_targets` joined to `quiz_sessions` (reusing
`compute_quiz_summary`, `services/quiz/session.py`, for the score
breakdown of a completed attempt). It does not call
`build_weak_area_report`/the Recommendation Agent at all.

**Rationale**: This is a genuinely different question ("did this
learner complete this specific assignment, and what was their score")
from the Recommendation Agent's weak-area analysis, which
`instructor_dashboard.py`'s existing `GET /api/rosters/{roster_id}/
dashboard` already answers per Milestone 7/Constitution Principle IV.
Routing assignment-completion status through the Recommendation Agent
would be forcing an unrelated concern through an agent boundary that
doesn't own it -- the roadmap's own Milestone 8 framing ("no new
grading logic, only assignment and reporting") is about reusing
Milestone 5/6's grading mechanism, not about reusing Milestone 2's
agent for an unrelated reporting need.

## §6: Cancellation is a soft flag; already-recorded mastery updates are structurally untouched

**Decision**: `quiz_assignments` gets a nullable `cancelled_at` column.
Cancelling sets it; it does not delete the assignment or its target
rows, and does not touch any `QuizSession`/`GeneratedQuestion`/
`AssessmentEvent` row a learner's already-completed attempt created. A
cancelled assignment simply becomes ineligible for any *new* attempt
(the start endpoint checks `cancelled_at IS NULL` alongside the
due-date check); an attempt already in progress when cancellation
happens is left alone -- consistent with `QuizSession`'s own existing
"an abandoned quiz is simply one left `in_progress` forever" semantics
(spec 005 data-model.md), so no new "was this attempt interrupted by
cancellation" state is needed.

**Rationale**: FR-012 (spec.md) forbids retracting or altering a
learner's already-recorded mastery-state updates on cancellation --
since those updates live entirely in `MasteryState`/`AssessmentEvent`
rows this feature never touches, that requirement is met by
construction rather than by an explicit "don't delete mastery data"
check somewhere.

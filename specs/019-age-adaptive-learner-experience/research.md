# Research: Age-Adaptive Learner Experience

**Feature**: `019-age-adaptive-learner-experience` | **Date**: 2026-09-20

Three `/speckit-clarify`/`/speckit-plan`-time decisions are already
recorded in `spec.md`'s `## Clarifications` (read-aloud via browser
TTS; opt-in-nudges notification in-app-only; "session" means quiz
session). This file resolves the remaining implementation-shape
decisions, including the hand-off-token mechanism spec.md's third
Clarification named but didn't design.

## Decision 1: Read-aloud is a single shared frontend component change

**Decision**: Add read-aloud controls to `QuestionCard.tsx`
(`frontend/src/components/QuestionCard.tsx`), the one component already
shared by `practice-flow.tsx`, `quiz-flow.tsx`, and `placement-flow.tsx`.
Gate visibility on a new `readAloudEnabled` prop the page-level flow
computes once from the learner's `unlocked_grade` (already fetched for
placement/practice) and passes down -- no new API call, no new backend
route.

**Rationale**: FR-001 requires read-aloud "across every subject and
question type" wherever a question is shown -- since every flow already
renders questions through this one component, this is the only change
needed to cover all three flows identically. Matches the ladder's rung
2 ("already in this codebase") exactly.

**Alternatives considered**: A new `<ReadAloudQuestion>` wrapper
component (rejected -- an unrequested abstraction around a component
that already exists and already receives the question text/options as
props).

## Decision 2: Read-aloud usage is logged via the existing answer-submission event, not a new endpoint

**Decision**: Add one boolean field, `read_aloud_used`, to the payload
already written by `ANSWER_SUBMITTED` events (`services/audit_log/writer.py`
callers in `questions.py`/`quiz.py`). The frontend sets this from
whether the learner triggered read-aloud at least once for that
question, sent alongside the existing answer-submission request body --
no new field on `GeneratedQuestion` or `AssessmentEvent` schema, no new
`AssessmentEventType`.

**Rationale**: SC-007 requires read-aloud usage be "reconstructable
after the fact from the audit log" -- it does not require a live,
per-toggle event stream (the learner replaying audio five times before
answering is not a distinct fact worth its own row). Folding one field
into the request/response the learner was already about to make avoids
a new round-trip per toggle and a new audit-log write path for a
low-stakes, boolean fact.

**Alternatives considered**: A dedicated `READ_ALOUD_TOGGLED`
`AssessmentEventType` fired on every play/replay (rejected -- one row
per toggle for a fact that only ever needs a yes/no answer is
disproportionate, and adds a new network call inside the read-aloud
control itself, working against FR-002's "replay as many times as
needed" with zero added friction).

## Decision 3: Guardian-mediation tier is a pure function of `GradeProgress.unlocked_grade`, returning `None` when ungraded

**Decision**: `determine_mediation_tier(unlocked_grade: int | None) ->
MediationTier | None` (new pure function, `services/mediation/tier.py`),
mapping 1-2→`CO_PRESENT`, 3-5→`CHECK_IN`, 6-8→`OPT_IN_NUDGES`,
9-12→`INDEPENDENT`. Returns `None` when the quiz's subject has no
`GradeProgress` row for that learner (an ungraded subject like
`biology`, or a subject the learner hasn't been placed into yet). A
`None` tier is handled identically to `CO_PRESENT` at every call site
(guardian-session-required, no hand-off token) -- not because ungraded
subjects are co-present by policy, but because that is exactly today's
existing behavior, and FR-013/SC-008 require zero behavior change for
them.

**Rationale**: Mirrors `starting_grade.py`/`grade_entry_topics()`'s
existing "pure, DB-free function reused unmodified" shape (per
Milestone 15's own plan.md), keeping tier determination trivially unit
-testable and independent of request/session plumbing. Collapsing
`None` into `CO_PRESENT`'s behavior (rather than inventing a fifth,
"ungated" tier) means every call site has exactly one conditional
("is this CO_PRESENT-or-None, or one of the other three") instead of
two.

**Alternatives considered**: A fifth explicit `UNGRADED` tier value
(rejected -- would require every call site to handle five cases instead
of a binary split, for a distinction that behaves identically to
`CO_PRESENT` everywhere it matters).

## Decision 4: The hand-off token is a scoped, short-lived JWT, verified alongside (not instead of) the guardian's own session

**Decision**: Extend `services/auth/tokens.py` with `issue_handoff_token
(quiz_session_id: uuid.UUID) -> str` and `verify_handoff_token(token: str)
-> uuid.UUID | None`, using the same `pyjwt` dependency and signing key
already locked for guardian/instructor session JWTs (`tech-stack.md`'s
Authentication section), with its own short claim shape (`{quiz_session_id,
token_type: "quiz_handoff", exp}}`) and expiry bound to a fixed ceiling
(e.g. 2 hours -- long enough for one quiz session, short enough to
bound leaked-token exposure) rather than the login session's own
lifetime. `start_assignment_attempt` (`services/quiz_assignment/assignment.py`)
mints and returns this token whenever `determine_mediation_tier(...)`
is anything other than `CO_PRESENT`/`None`; the route layer
(`quiz_assignments.py`) includes it in the start response as
`handoff_token: str | None`.

`assert_guardian_owns_assignment_session` (renamed
`assert_quiz_session_access`, same call sites in `quiz.py`/`questions.py`)
gains one new parameter, `handoff_token: str | None` (read from a new
optional `X-Quiz-Handoff-Token` request header). Its logic becomes: no-op
if the session isn't assignment-linked (today's demo/ad-hoc behavior,
completely unchanged); otherwise, look up the tier; if
`CO_PRESENT`/`None`, require guardian claims exactly as today; otherwise,
accept *either* valid guardian claims *or* a `handoff_token` whose
decoded `quiz_session_id` matches and whose quiz session status is still
`IN_PROGRESS`.

**Rationale**: Reuses this project's one existing signed-token mechanism
(`pyjwt`, already a dependency, already the pattern for guardian/
instructor sessions) rather than introducing a second credential
technology for a single, narrow purpose. Scoping the claim to
`quiz_session_id` (not `learner_id`) means a leaked token's blast radius
is exactly what spec.md's edge case requires: the remaining questions of
one already-in-progress quiz session, nothing broader. Layering this as
an *additional* accepted credential on the existing check -- rather than
a new endpoint or a new account type -- keeps the "guardian starts every
quiz session, is never fully locked out" property from spec.md's
Assumptions true by construction.

**Alternatives considered**: A real, standalone learner account/login
(rejected at `/speckit-clarify`-equivalent decision time during
`/speckit-plan` -- correct long-term, but a much larger, separate
capability with no other consumer yet; would belong in its own spec per
Constitution Principle VII, not bundled into this one as a side effect
of Story 2). An opaque random token stored in a new database table
(rejected -- `pyjwt` verification is stateless and free; a stored-token
table would need its own cleanup/expiry job for no added security
value at this scope).

## Decision 5: Tier determination and hand-off-token issuance are logged via one new `AssessmentEventType`

**Decision**: Add `GUARDIAN_MEDIATION_APPLIED` to `AssessmentEventType`
(`models/enums.py`), written once per quiz-session start attempt
(inside `start_assignment_attempt`, alongside the existing
`QUIZ_ASSIGNMENT`-family events), with payload `{quiz_session_id, tier,
handoff_token_issued: bool}`. No new table -- follows the same
"extend the existing append-only audit log" precedent Milestones 2, 6,
11, and 16 all already established (per those milestones'
`tech-stack.md` rows).

**Rationale**: Directly satisfies FR-012/SC-007's requirement that every
tier determination be reconstructable after the fact, at the one point
(session start) where the tier is actually decided -- no need to log it
again on every subsequent next-question/answer call, since the tier is
fixed for the quiz session's lifetime (per spec.md's tier-boundary edge
case).

**Alternatives considered**: Logging tier on every next-question call
(rejected -- the tier doesn't change mid-session, so this would be pure
duplication of the one fact already captured at start).

## Decision 6: Session-pacing checkpoints are frontend-only, driven by a static per-grade-band lookup table

**Decision**: `frontend/src/lib/pacing.ts` (new, small) exports a pure
function mapping grade band → `{ recommendedQuestionCount:
number, reinforcementEveryN: number }`, consulted by `quiz-flow.tsx`
after each answered question to decide whether to show a positive-
reinforcement stopping-point prompt. No backend change, no new
`QuizSession` column -- the quiz already knows its own `question_count`
and in-progress answer count client-side.

**Rationale**: FR-009 explicitly scopes this to UI/UX pacing, not a
change to mastery computation, quiz scoring, or server-enforced limits
(spec.md Assumptions) -- a client-side lookup keeps this genuinely
"soft" (a suggested stopping point, not a hard cutoff a learner can't
pass), matching Story 3's Acceptance Scenario 2 ("no early stopping
point is imposed").

**Update (code-review fix, post-implementation)**: the initial
implementation only ever consumed `recommendedQuestionCount` (the
one-time, end-of-session stopping point) -- `reinforcementEveryN` was
computed and unit-tested but never wired to anything, leaving FR-009's
"more frequent positive reinforcement for younger bands" half
unimplemented. Both `quiz-flow.tsx` and `LearnerAssignments.tsx` now
also show a brief, non-blocking encouragement message
(`data-testid="reinforcement-message"`) every `reinforcementEveryN`
answered questions, suppressed on any count that also reaches the
stopping point (no double reinforcement on the same answer).

**Alternatives considered**: A new `SessionPacingProfile` database table
(rejected -- four grade bands' worth of two static numbers each doesn't
need a table; a code constant is simpler and there is no per-learner
customization requirement to justify persistence).

## Decision 7: The opt-in-nudges "new activity" indicator is one nullable column on `QuizAssignmentTarget`, gated to that tier alone

**Decision**: Add `guardian_viewed_at: datetime | None` to
`QuizAssignmentTarget` (`models/quiz_assignment_target.py`), set the
first time a guardian loads that attempt's summary
(`LearnerAssignments.tsx`'s existing `goToSummary`, via a small addition
to the summary-fetch call) -- for *any* tier, unconditionally; recording
"was this viewed" is harmless and tier-independent. The existing
assignment list (`listLearnerAssignments`, already polled/refreshed
today) renders a badge/dot next to an assignment only when **all** of:
`status` is `completed`/`ended_early`, `guardian_viewed_at` is still
null, **and** `determine_mediation_tier(...)` (re-derived live from the
target's current `GradeProgress`, same as `assert_quiz_session_access`)
equals `OPT_IN_NUDGES`.

**Correction (`/speckit-analyze`, 2026-09-20)**: the tier check above
was missing from this decision's first draft, which gated the badge on
completion/unviewed status alone. That would have shown the badge for
check-in and independent-tier learners too -- the latter directly
violating FR-008's "MUST NOT produce ... a notification" for the
independent tier. The column and its write path (set on view, any tier)
are unchanged; only the *read-side* exposure gained the tier condition.

**Rationale**: The guardian-facing assignment list and its status field
already exist (`STATUS_LABEL` in `LearnerAssignments.tsx`) -- a
completed-but-unviewed distinction is one nullable timestamp, not a new
notification table or delivery pipeline. This is the concrete mechanism
behind FR-007's "in-app indicator," and it's also exactly the seam
FR-007a requires: adding email later means reading this same column
(plus the same tier gate) to decide whether an email is still owed, not
rebuilding tier logic. Gating the *badge* (not the column) on tier
keeps FR-006 (check-in gets a summary, not a badge) and FR-008
(independent gets neither) both true from the same underlying data,
without a second column or a second write path.

**Alternatives considered**: A separate `GuardianNotification` table
(rejected -- one column on an existing, already-per-target row is
smaller and needs no new foreign keys or cleanup job). Gating the
*write* (only set `guardian_viewed_at` for opt-in-nudges targets)
instead of the *read* (rejected -- tracking "viewed" for every tier is
harmless and keeps the column's meaning simple and uniform; only the
UI-facing badge needs to know about tier).

## Summary of new surface area

| Concern | New? | Where |
|---|---|---|
| `MediationTier` enum + `determine_mediation_tier()` | New, pure function | `backend/src/services/mediation/tier.py` |
| Hand-off token issue/verify | New | `backend/src/services/auth/tokens.py` |
| `assert_quiz_session_access` (renamed/extended) | Extends existing | `backend/src/services/quiz_assignment/assignment.py` |
| `GUARDIAN_MEDIATION_APPLIED` event type | New enum value, no new table | `backend/src/models/enums.py` |
| `read_aloud_used` field | New field on existing event payload | `questions.py`/`quiz.py` answer-submission handlers |
| Read-aloud UI | New | `frontend/src/components/QuestionCard.tsx` |
| Pacing lookup | New, static | `frontend/src/lib/pacing.ts` |
| Guardian-facing summary/indicator | New UI + one new nullable column | `frontend/src/components/LearnerAssignments.tsx`; `QuizAssignmentTarget.guardian_viewed_at` |

No new database table (one new nullable column on an existing table).
No new `tech-stack.md` entry (JWT/`pyjwt` and the append-only audit log
are both already-locked patterns being extended, not new technology
choices).

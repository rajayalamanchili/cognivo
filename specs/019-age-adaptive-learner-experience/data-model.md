# Data Model: Age-Adaptive Learner Experience

**Feature**: `019-age-adaptive-learner-experience` | **Date**: 2026-09-20

One new column, zero new tables, one new enum, one new derived
(non-persisted) concept. See `research.md` for the rationale behind
each choice below.

## Schema change

### `QuizAssignmentTarget.guardian_viewed_at` (new, nullable)

```python
guardian_viewed_at: Mapped[datetime.datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

- `NULL` until a guardian loads that attempt's summary for the first
  time; set once, never cleared, **for any tier** -- the write side is
  tier-independent (research.md §7).
- Backs FR-007's "new activity" indicator, but only when **all three**
  hold: the linked `QuizSession.status` is `completed`/`ended_early`,
  `guardian_viewed_at` is still `NULL`, **and** the target's current
  `determine_mediation_tier(...)` is `OPT_IN_NUDGES`. The tier check is
  what keeps this indicator from also appearing for check-in (FR-006)
  or independent (FR-008) targets -- corrected during `/speckit-analyze`
  (research.md §7's Correction note); the column itself has no tier
  concept baked in, only its API-level exposure does.
- Additive, nullable, no backfill needed for existing rows (all treated
  as unviewed, which is correct -- nothing has been marked viewed yet).

## New enum

### `MediationTier` (`models/enums.py`)

```python
class MediationTier(enum.StrEnum):
    CO_PRESENT = "co_present"
    CHECK_IN = "check_in"
    OPT_IN_NUDGES = "opt_in_nudges"
    INDEPENDENT = "independent"
```

Never persisted as a column -- always derived at read time from
`GradeProgress.unlocked_grade` via `determine_mediation_tier()`
(research.md §3), consistent with FR-011's "never a second,
independently maintained copy of grade." Used only:

- As an in-memory value at quiz-session-start time, to decide whether to
  mint a hand-off token (FR-005a/b).
- As the `tier` field in the `GUARDIAN_MEDIATION_APPLIED` audit-log
  event payload (research.md §5) -- the *record* of a past
  determination is what's persisted, in the existing
  `AssessmentEvent.payload` JSON column, not the tier itself as a
  first-class column anywhere.

## New `AssessmentEventType` value

`GUARDIAN_MEDIATION_APPLIED = "guardian_mediation_applied"`, written
once per quiz-session start attempt. Payload shape:

```json
{
  "quiz_session_id": "<uuid>",
  "tier": "co_present" | "check_in" | "opt_in_nudges" | "independent" | null,
  "handoff_token_issued": true | false
}
```

`tier: null` covers the ungraded-subject/no-`GradeProgress` case
(research.md §3) -- logged explicitly rather than omitted, so "no tier
applied" is itself a reconstructable fact, not a silent gap in the
audit trail.

## New non-persisted concept: hand-off token

Not a database row. A signed JWT (research.md §4), verified statelessly
via the existing `pyjwt` dependency:

```json
{ "quiz_session_id": "<uuid>", "token_type": "quiz_handoff", "exp": <unix ts> }
```

- Minted by `issue_handoff_token(quiz_session_id)` inside
  `start_assignment_attempt`, only when
  `determine_mediation_tier(...)` returns `CHECK_IN`, `OPT_IN_NUDGES`,
  or `INDEPENDENT`.
- Returned to the caller (guardian) in the start-attempt response as
  `handoff_token: str | None`; never persisted server-side.
- Verified by `verify_handoff_token()` against the `X-Quiz-Handoff-
  Token` request header on every subsequent next-question/answer call
  for that `quiz_session_id`, in addition to (not instead of) the
  existing guardian-session check (`research.md` §4).
- Expiry: a fixed ceiling (2 hours) independent of the guardian's own
  login-session lifetime, and implicitly invalid once the
  `QuizSession.status` it names is no longer `IN_PROGRESS` (checked
  against live DB state at verification time, not encoded in the token
  itself, since a quiz ending early can't be predicted at mint time).

## Existing entities this feature reads, never writes elsewhere

| Entity | Field(s) used | Purpose |
|---|---|---|
| `GradeProgress` | `unlocked_grade` | Input to `determine_mediation_tier()` and to FR-001/FR-003's read-aloud gate (grade 1-2). Read-only -- this feature never advances or otherwise mutates it (Milestone 15 owns that). |
| `QuizSession` | `status`, `quiz_session_id`, `subject_id`, `learner_id` | Hand-off token scope/validity check; pacing checkpoint (client-side, reads `question_count`/answered-so-far already in the existing next-question response shape). |
| `QuizAssignmentTarget` | `quiz_session_id` (existing), `guardian_viewed_at` (new) | Links a quiz session back to its assignment for the tier/hand-off/indicator logic; the only real-learner quiz-session-creation path today (research.md §4). |
| `LearnerProfile` | `guardian_id`, `is_demo` | Unchanged use, same as the existing `assert_guardian_owns_assignment_session` check it's renamed from. |

## State transitions

No new state machine. `QuizSession.status`'s existing three-state
lifecycle (`IN_PROGRESS` → `COMPLETED` | `ENDED_EARLY`, spec 005) is
unchanged and is exactly what both the hand-off token's validity window
and the pacing checkpoint's "session complete" trigger key off of.
`QuizAssignmentTarget.guardian_viewed_at` is a one-way `NULL` →
timestamp transition, set exactly once, never reset.

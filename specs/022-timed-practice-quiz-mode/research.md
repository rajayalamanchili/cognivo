# Phase 0 Research: Timed Practice and Quiz Mode

**Feature**: `022-timed-practice-quiz-mode` | **Date**: 2026-09-23

## §1. Expiry enforcement mechanism (resolves the Vercel/stateless Constraint)

**Decision**: Expiry is evaluated lazily, on the server, the next time
any request touches a timed session -- never by an active background
process counting down. `expires_at = started_at + time_limit_seconds`
is derivable from data already on the row (no new "remaining time"
column needed). Every endpoint that reads or mutates a timed session
(`next-question`, `answer`, the summary route) MUST first check
`now() >= expires_at`; if true and the session is still `in_progress`,
it transitions the session to `ended_early`, writes the
`timed_session_ended` audit event (`end_reason=timer_expired`,
research.md §3), and rejects the triggering mutation (e.g. an answer
submitted after expiry is rejected, not silently scored) before doing
anything else.

**Rationale**: `tech-stack.md`'s Deployment target section is explicit
-- no persistent, long-running background process is available on
Vercel, and any cross-request state must be re-derived from the
database, not held in memory. A naive "countdown timer" implementation
(a scheduled job actively ending sessions at the instant they expire)
would need exactly that kind of process. Lazy, per-request expiry
checking is the same pattern this codebase already uses for two other
"a thing becomes invalid after a duration" problems: the JWT session
cookie (`tech-stack.md`'s Authentication table) and the Milestone 17
quiz-session hand-off token both encode their own expiry and are
checked statelessly per request, never actively revoked by a running
process. This feature reuses that same shape rather than inventing a
second one.

**Alternatives considered**:
- *Vercel Cron job, matching the Misconception Classifier's pattern
  (`tech-stack.md`'s Misconception classifier table)* -- rejected.
  Cron granularity is minutes, not seconds; a learner mid-answer when a
  cron tick lands would be cut off imprecisely, and the classifier's
  job exists for a batch enrichment task with no per-second correctness
  requirement, unlike a session's actual completion state.
- *Client-driven expiry (the frontend calls an "end session" endpoint
  when its own countdown hits zero)* -- rejected as the sole mechanism
  per FR-006 (spec.md): a client that goes offline, closes the tab, or
  has a slow/stopped clock must not be able to keep a session open past
  its real limit. The frontend countdown (FR-002) is a *display* built
  from the same server-provided `expires_at`, not the authority for
  when the session actually ends -- that authority is the lazy
  server-side check above, which fires on whatever request happens
  next regardless of what the client's own clock believes.

**Accepted limitation**: If a learner starts a timed session and never
makes another request at all (closes the tab, walks away), the lazy
check never fires, so the session row stays `in_progress` past its
`expires_at` until *some* later request touches it (or forever, if
none ever does). This is not a regression: it is the exact same
"abandoned" behavior `quiz_sessions`' own docstring already documents
for untimed quizzes today (`backend/src/models/quiz_session.py`'s
class docstring) -- an abandoned session is simply left as-is, nothing
actively sweeps it. SC-002 ("100% of timed sessions end at or before
their configured limit") holds for every session a learner actually
returns to; it does not claim to actively terminate a session nobody
ever interacts with again, matching the pre-existing precedent rather
than introducing a new background-sweep requirement this feature's
spec never asked for.

## §2. Session model: extend `QuizSession`, add a narrowly-scoped `PracticeSession`

**Decision**: Add one nullable `time_limit_seconds: int` column to the
existing `quiz_sessions` table (null = untimed, unchanged from today).
Add one new table, `practice_sessions`, created only when a learner
opts into timed practice (spec.md FR-008) -- structurally a thin header
row matching `quiz_sessions`' own shape (reusing `QuizSessionStatus`'s
three existing values: `in_progress`/`completed`/`ended_early`, no new
enum member needed here), scoped to one `subject_id` per session
(matching `GET /next-question`'s existing required `subject_id` query
param -- confirmed during `/speckit-plan` that practice is already
single-subject per call, topic hopping only within that subject via
the Sequencing Agent). `GeneratedQuestion` gains one new nullable
`practice_session_id` FK column, parallel to its existing
`quiz_session_id` column -- a question is tagged to at most one of the
two (or neither, for ordinary untimed practice), never both.

**Rationale**: Matches this codebase's own established precedent
exactly: `QuizAssignment`/`QuizAssignmentTarget` (Milestone 8) reused
`QuizSession` outright rather than inventing a parallel attempt record,
and `quiz_sessions`' own docstring already establishes the
"thin header row, everything else derived at read time from
`GeneratedQuestion`/`AssessmentEvent`" shape this feature's new table
follows. `time_limit_seconds` nullable on the existing table (rather
than a new `timed_quiz_sessions` side table) is the smallest change
that satisfies FR-009's "zero behavior change when absent" requirement
-- every existing query, index, and code path that doesn't know about
timers keeps working unmodified.

**Alternatives considered**:
- *One shared `timed_sessions` table covering both quiz and practice*
  -- rejected. Would require either a polymorphic type discriminator
  pointing back at `quiz_sessions`/a-new-practice-concept anyway
  (no real simplification) or merging quiz's `topic_ids`+
  `question_count` shape with practice's single-`subject_id`,
  open-ended shape into one table with several always-null columns
  depending on session type -- more accidental complexity than the two
  small, purpose-shaped tables this decision picks.
- *General-purpose practice-session boundary (spec.md FR-008's Option
  B, not chosen at the spec-clarification stage)* -- already rejected
  in spec.md itself; not re-litigated here.

## §3. Recording how a timed session ended

**Decision**: One new `AssessmentEventType` enum member,
`timed_session_ended`, written exactly once when a timed session
transitions out of `in_progress` (whether by completion, timer expiry,
or manual early-end) -- never for untimed sessions, which get no new
event at all. Payload: `{"session_type": "quiz" | "practice",
"session_id": "...", "time_limit_seconds": int, "elapsed_seconds": int,
"end_reason": "completed" | "timer_expired" | "manually_ended_early"}`.

**Rationale**: Directly matches the Misconception Classifier's own
precedent (`tech-stack.md`'s Classification storage row): "a new
`AssessmentEventType` value, zero new tables" for a new kind of
loggable fact, rather than a bespoke `session_timing_records` table.
Satisfies spec.md FR-007 (pedagogical audit log, Constitution Principle
V) and gives User Story 3's post-session summary (spec.md) a single
row to read, the same way existing dashboards already read
`quiz_difficulty_adjusted`/`recommendation_report_generated` events
rather than a dedicated summary table per feature.

## §4. Manual early-end is new, not a reuse of existing behavior

**Decision**: A new endpoint per session type (`POST
/api/quizzes/{quiz_session_id}/end`, `POST
/api/practice-sessions/{practice_session_id}/end`), gated to `in_progress`
timed sessions only, transitioning to `ended_early` and writing the
`timed_session_ended` event with `end_reason=manually_ended_early`.

**Rationale**: `/speckit-plan` research found spec.md's original FR-010
draft incorrectly assumed today's untimed quiz already supports a
learner-initiated "end now" action -- grep against
`backend/src/api/routes/quiz.py` shows its only `ended_early` trigger
is automatic dedup-retry exhaustion (`quiz.py:141,206`), never a
learner-facing endpoint. spec.md's FR-010 has been corrected in place
to state this plainly: manual early-end is new, and scoped to timed
sessions only, since an untimed session has no time pressure that
would motivate a learner wanting to stop early via a dedicated action
(they can simply stop requesting the next question).

## §5. No auth/identity changes

**Decision**: Timed sessions use whatever identity mechanism their
underlying endpoint already uses -- unauthenticated `learner_id` path
param for practice (`GET /next-question` has no auth dependency today),
guardian-session-cookie/hand-off-token gating for any quiz session
linked to a `quiz_assignment_targets` row (Milestone 8/17, unchanged).
This feature adds no new credential type and does not touch
`tech-stack.md`'s Authentication table.

**Rationale**: Nothing about adding a timer changes who is allowed to
answer a question -- it only changes when a session accepts further
answers. Inventing a parallel auth path for "timed" sessions
specifically would be scope creep with no requirement in spec.md
driving it.

## §6. No new dependency, no `tech-stack.md` amendment

**Decision**: Implemented entirely with the already-locked stack
(FastAPI, SQLAlchemy/Alembic, Postgres/Neon, pytest, Next.js/TypeScript,
Vitest). No new library, no new external service.

**Rationale**: `expires_at = started_at + time_limit_seconds` is
`datetime` arithmetic; lazy per-request expiry checking is plain
application code, not a job scheduler. Nothing here needs a rate
limiter, a distributed lock, or a real-time push channel -- the
frontend countdown (FR-002) is a client-side `setInterval` against a
server-provided timestamp, a standard, dependency-free pattern.

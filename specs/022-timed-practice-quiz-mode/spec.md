# Feature Specification: Timed Practice and Quiz Mode

**Feature Branch**: `032-timed-practice-quiz-mode`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "timed practice quiz mode"

## Clarifications

### Session 2026-09-23 (post-plan)

- Q: Every question (timed or untimed, quiz or practice) should record
  how long the learner took to submit an answer. How is that duration
  measured? → A: Server-derived -- `answered_at - shown_at`, computed
  at submission time from timestamps the system already has, no new
  client-reported field.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Timed quiz attempt (Priority: P1)

A learner starting a quiz (Milestone 5) can opt into a fixed time limit
instead of today's untimed, learner-paced default, so they can practice
under exam-like conditions.

**Why this priority**: Lowest-risk, highest-value slice -- quizzes
already have a session boundary (`quiz_sessions`), so this story adds a
duration and expiry behavior to an existing mechanism rather than
inventing a new one. Delivers the core "timed" value on its own.

**Independent Test**: Can be fully tested by starting a quiz with a
timer enabled, letting the clock run out mid-attempt, and verifying the
session ends according to the resolved expiry policy (FR-003) with a
score computed exactly like an untimed quiz would for the same answers.

**Acceptance Scenarios**:

1. **Given** a learner is starting a new quiz, **When** they choose a
   time limit before beginning, **Then** the quiz session starts with a
   visible countdown and the same question-selection/difficulty-
   adaptation behavior as an untimed quiz.
2. **Given** a learner is mid-attempt in a timed quiz with time
   remaining, **When** they answer the final configured question,
   **Then** the session ends immediately (same as today's untimed
   behavior) and any unused time is simply discarded.
3. **Given** a learner is mid-attempt in a timed quiz, **When** the
   configured time limit is reached before all questions are answered,
   **Then** the session auto-submits immediately (FR-003) with
   unanswered questions scored as unanswered, and the resulting score
   is computed exactly as an untimed session's would be (FR-004).

---

### User Story 2 - Timed practice session (Priority: P2)

A learner can opt into a fixed time limit for ordinary practice (not
just quizzes), turning today's open-ended, unbounded practice into a
bounded exam-style session for a chosen duration.

**Why this priority**: Practice has no session boundary at all today
(Milestone 17's own planning explicitly declined to build one), so this
story requires introducing that boundary -- strictly more work than
Story 1, and only valuable once Story 1 proves the timer/expiry
mechanics work.

**Independent Test**: Can be fully tested by starting a timed practice
session, answering questions until time expires, and verifying the
session ends and reports a summary the same way a timed quiz does,
without altering the untimed practice path for learners who don't opt
in.

**Acceptance Scenarios**:

1. **Given** a learner chooses to start timed practice, **When** they
   begin, **Then** a new bounded practice session starts with a visible
   countdown, using the same question sequencing (Sequencing Agent,
   Milestone 1) as untimed practice.
2. **Given** a learner is in a timed practice session, **When** the
   time limit is reached, **Then** the session auto-submits
   immediately (FR-003), identically to a timed quiz.
3. **Given** a learner never opts into a timer, **When** they practice
   normally, **Then** behavior is unchanged from today -- no session
   boundary, no countdown, no expiry.

---

### User Story 3 - Post-session time summary (Priority: P3)

After a timed session (practice or quiz) ends, the learner (and their
guardian, where applicable) can see how much time was used against the
configured limit.

**Why this priority**: A small reporting layer on top of Stories 1-2;
useful but not required to prove the timed mechanism itself works.

**Independent Test**: Can be fully tested by completing a timed session
and confirming the elapsed-time-vs-limit summary appears wherever
session results are already shown (learner dashboard, guardian view).

**Acceptance Scenarios**:

1. **Given** a timed session has ended (by completion or expiry),
   **When** the learner views their result, **Then** they see the
   configured time limit, the actual time used, and how the session
   ended (finished early, auto-submitted/locked at expiry).

---

### Edge Cases

- What happens when a learner's device loses connectivity mid-timed-
  session and reconnects after the configured limit has passed? Expiry
  MUST be evaluated against server time, not client-reported elapsed
  time, so a reconnect after expiry finds the session already ended.
- What happens if a subject/topic combination runs out of available
  questions before the time limit or configured question count is
  reached? The session MUST end early using the same
  `ended_early`-style outcome existing untimed quiz sessions already
  use for this case, not fail or hang waiting for time to run out.
- What happens if a learner opens the same timed session in a second
  tab/device? The session's remaining time MUST stay identical across
  both -- it is a property of the session record, not of any one
  client.
- What happens when a learner starts a timed session with a time limit
  shorter than a single question realistically takes to answer? Out of
  scope for this spec to prevent; the resolved expiry policy (FR-003)
  still applies to whatever answer state exists when time runs out.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a learner choose a fixed time limit from
  a small preset list (e.g. 15/30/45/60 minutes) when starting either a
  practice session or a quiz, as an alternative to today's untimed
  default. Untimed remains the default for both.
- **FR-002**: System MUST show the learner a visible countdown of
  remaining time throughout a timed session.
- **FR-003**: When a timed session's time limit is reached with the
  session still in progress, the system MUST auto-submit the session
  immediately using whatever answers exist at that moment -- any
  unanswered questions are treated as unanswered, exactly as if the
  learner had ended the session early themselves.
- **FR-004**: For a timed session, the system MUST compute scoring
  identically to an untimed session given the same answers -- the timer
  is purely a session-bounding UX constraint and MUST NOT apply any
  penalty, bonus, or cutoff tied to elapsed time.
- **FR-005**: System MUST end a timed session immediately once its
  configured question count is reached, before the time limit, exactly
  as today's untimed quiz already does -- the timer is a ceiling, not a
  floor.
- **FR-006**: System MUST measure a timed session's remaining time from
  server time, never from the client device's clock, so the session
  cannot be extended by client clock manipulation.
- **FR-007**: System MUST record, for every timed session, its
  configured duration, actual elapsed time, and how it ended (learner-
  completed, timer-expired, manually ended early) as part of this
  platform's existing pedagogical audit log (Constitution Principle V)
  -- not a separate, un-traceable timing record.
- **FR-008**: The new bounded-session concept this feature requires for
  practice (User Story 2) MUST be scoped narrowly to timed sessions
  only -- a practice-session record is created only when a learner
  opts into a timer. Ordinary untimed practice MUST remain exactly as
  stateless and unbounded as it is today, with no session record
  created for it (consistent with Milestone 17's own planning, which
  explicitly declined to build a general-purpose practice-session
  boundary).
- **FR-009**: System MUST leave today's untimed, learner-paced practice
  and quiz flows unchanged in session behavior, scoring, and
  question-selection logic for any learner who does not opt into a
  timer -- no session boundary, no countdown, no expiry. This does not
  exempt untimed sessions from FR-011's per-question timing record,
  which applies uniformly regardless of timer opt-in.
- **FR-011**: System MUST record, for every answered question
  (timed or untimed, quiz or practice, no exceptions), how long the
  learner took between the question being shown and their answer being
  submitted, computed server-side from timestamps the system already
  records -- never from a client-reported duration (Clarifications,
  2026-09-23).
- **FR-010**: System MUST let a learner end a timed session manually
  before the time limit or question count is reached. This is a new
  capability scoped to timed sessions only -- neither today's untimed
  quiz nor untimed practice currently offers a learner-initiated "end
  now" action (confirmed during `/speckit-plan`: today's only
  `ended_early` trigger is automatic question-variety exhaustion, never
  a learner action), and untimed sessions have no time pressure that
  would motivate adding one.

### Key Entities *(include if feature involves data)*

- **Timed Session**: A bounded window wrapping either a practice run or
  a quiz attempt -- adds a configured duration, an expiry point, and a
  completion reason (learner-completed, timer-expired, manually-ended-
  early) on top of the session concept each mode already has or gains
  through this feature.
- **Practice Session** *(new for this feature)*: The session boundary
  this feature introduces for timed practice only (FR-008) --
  analogous to the `quiz_sessions` boundary Milestone 5 already
  established for quizzes. Never created for ordinary untimed practice.
- **Session Timing Record**: The audit-log entry (FR-007) capturing a
  timed session's configured duration, actual elapsed time, and
  completion reason -- extends the existing pedagogical audit log
  rather than creating a separate, parallel record.
- **Per-Question Time Spent**: A duration recorded against every
  answered question, timed or untimed (FR-011) -- extends the existing
  answer-submission audit record rather than creating a separate,
  parallel one; unlike the Session Timing Record above, this applies
  even when no timer is involved at all.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A learner starting a timed practice or quiz session sees
  a visibly updating time-remaining countdown throughout the entire
  session.
- **SC-002**: 100% of timed sessions end at or before their configured
  time limit -- no timed session remains open past expiry under normal
  network conditions.
- **SC-003**: Scoring and completion behavior for a timed session
  matches the resolved policy (FR-004) in 100% of sessions, verified by
  comparing timed vs. untimed sessions given identical answer
  sequences.
- **SC-004**: Every existing untimed practice and quiz acceptance
  scenario from Milestones 1-19 continues to pass unchanged -- zero
  regression in session, scoring, or question-selection behavior for
  learners who don't opt into a timer (FR-011's timing record is
  additive audit data, not a behavior change to any of those three).
- **SC-005**: After a timed session ends, a learner (or their guardian,
  where applicable) can find the configured time limit, actual time
  used, and how the session ended, without needing to ask anyone.
- **SC-006**: For 100% of answered questions across every Milestone
  1-19 flow (placement, untimed practice, untimed quiz, timed practice,
  timed quiz), a per-question time-spent value is recorded and
  retrievable (FR-011).

## Assumptions

- Reuses `quiz_sessions` (Milestone 5) as the underlying session record
  for timed quizzes, adding duration/expiry fields to it rather than
  introducing a parallel model -- consistent with how Milestone 8's
  assigned-quiz attempts already reuse the same record instead of
  inventing their own.
- Because Milestone 8's assigned-quiz attempts link to a `QuizSession`
  record, enabling a timer on quizzes makes it available to assigned
  quizzes too at no extra cost; this spec does not add a separate
  instructor-facing "assign a timed quiz" requirement, since the
  underlying attempt mechanism is unchanged.
- The "Per-question time-spent tracking" item already named in
  `roadmap.md`'s backlog (a `time_spent_seconds` field on
  `ANSWER_SUBMITTED`) is now in scope here per the 2026-09-23
  post-plan Clarification (FR-011) -- absorbed into this milestone
  rather than left as a separate future item, since it shares this
  feature's exact timing/audit-log surface.
- Time-limit choices default to a small fixed preset list (e.g.
  15/30/45/60 minutes) rather than an arbitrary custom-duration input,
  keeping the UI simple; no evidence of a real need for arbitrary
  durations was found.
- Timed mode is learner-opted-in only in this milestone -- an
  instructor or guardian cannot force a timer onto a learner's session.
  A forced/assigned timer is a plausible future extension, not required
  to prove this feature works.
- No new mobile/tablet-specific design is required; the countdown UI
  follows whatever responsive patterns the existing quiz/practice UI
  already uses.

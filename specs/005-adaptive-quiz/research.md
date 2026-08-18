# Phase 0 Research: Adaptive Difficulty Quiz

**Feature**: `005-adaptive-quiz` | **Date**: 2026-08-18

Most of this feature's design decisions were already pinned down during
`/speckit-clarify` (see spec.md's Clarifications section). This
research resolves the remaining implementation-level questions
`/speckit-clarify`'s 5-question budget was deliberately not spent on,
plus records how the clarified decisions map onto existing code.

## 1. In-quiz difficulty is re-derived on every request, never persisted as a counter

**Decision**: A topic's current in-quiz difficulty band and streak are
not stored as mutable columns anywhere. They are recomputed on each
request by replaying that quiz's ordered (correct/incorrect) history
for the topic -- starting at `easy` with a zero streak -- through a
single pure step function, `next_difficulty` (research.md §
Clarifications' streak rule: 2 consecutive same-direction answers move
one band, per-topic, resetting the streak to zero whenever the 2-streak
threshold is reached, whether or not the band actually moved).

**Rationale**: Matches `QuizSession`'s own Clarifications decision (a
thin persisted header row; per-question detail derived from
`GeneratedQuestion`/`AssessmentEvent` rows) and the platform's existing
convention of computing derived state at read time rather than caching
it (e.g. `mastery_band_for` is explicitly never cached, per
`data-model.md`'s Milestone-1 precedent). A replay function is also
directly unit-testable against a plain list of booleans, no DB needed --
same style as `rank_eligible_topics`/`classify_topic_status`.

**Streak-reset-on-hold decision**: When 2 consecutive answers would push
the band past `easy` or `hard`, the band holds at the bound (FR-007) and
the streak still resets to zero (not left at the threshold) -- the
2-in-a-row attempt has been resolved either way. Not itself a
Clarifications question (below the bar for the 5-question budget), but
recorded here since it's a real behavioral choice: the alternative
(leaving the streak pinned at the threshold while held at a bound) would
mean every subsequent correct answer at `hard` immediately "moves" a
zero-width step, which is observably indistinguishable from a reset but
more complex to reason about.

**Alternatives considered**: Persisting `current_difficulty`/streak as
mutable columns on a per-(quiz_session_id, topic_id) row. Rejected:
adds a second source of truth that could drift from the replay-derived
value if a bug ever wrote one without the other; the replay is cheap
(a quiz's per-topic history is small, bounded by `question_count`).

## 2. Round-robin topic selection is a pure function over a generated-count

**Decision**: The next topic for a quiz's next question is
`topic_ids[questions_generated_so_far % len(topic_ids)]`, where
`questions_generated_so_far` is a count of `GeneratedQuestion` rows
already tagged with this `quiz_session_id` (across all topics, not
per-topic). No separate "whose turn" counter is persisted.

**Rationale**: `QuizSession.topic_ids` already stores the selection
order (Clarifications); round-robin position is fully determined by how
many questions this session has generated so far, which is already
derivable by counting existing rows -- no new state needed, consistent
with §1's re-derivation approach.

## 3. Quiz-scoped near-duplicate check reuses `recent_stems_for_topic` unchanged, with a wider lookback

**Decision**: Generating a quiz question calls the existing
`services/dedup/checker.recent_stems_for_topic(db, learner_id=,
subject_id=, topic_id=, limit=...)` exactly as Milestone 1's
`generate_next_question` does, but with `limit` set to
`quiz_session.question_count` (the quiz's own upper bound) instead of
the default `DEFAULT_LOOKBACK=5`. Since this function already queries
by `learner_id`+`topic_id` with no session filter, it inherently
includes both this quiz's own already-generated questions on that topic
*and* the learner's pre-quiz history -- exactly the "at least as strict
as Milestone 1's cross-session rule" bar from FR-008/Edge Cases, with
zero new dedup code.

**Rationale**: A 20-question quiz on one topic (the Edge Cases example)
needs a lookback covering all 20, not just the last 5 -- capping at
`question_count` is the smallest change that guarantees full-session
coverage without an unbounded query.

**Ended-early on retry exhaustion**: Mirrors `generate_next_question`'s
existing `max_dedup_attempts=3` retry loop, but where Milestone 1
"gives up and returns the last draft" after exhausting attempts
(best-effort), the quiz path raises `QuizEndedEarlyError` instead --
the caller (the quiz route) catches this, sets
`QuizSession.status = "ended_early"` with no new `GeneratedQuestion`
row, and returns that state rather than ever serving a near-duplicate
(Clarifications, FR-008). `max_dedup_attempts=3` is kept the same value
as Milestone 1's for consistency, not re-derived -- no evidence exists
yet that 3 is too few or too many in practice, and this is trivially
tunable later without a contract change.

**Alternatives considered**: A quiz-specific dedup function scoped
*only* to this session's own questions (excluding the learner's
pre-quiz history on that topic). Rejected: FR-008 explicitly says "at
least as strict as" the cross-session rule, not a narrower same-session-
only rule -- excluding pre-quiz history would be a *weaker* guarantee
than Milestone 1 already provides outside quizzes.

## 4. The existing `POST /api/questions/{question_id}/answer` endpoint is reused unmodified in its response contract, extended internally

**Decision**: Quiz questions are graded and mastery-updated through the
exact same `answer_question` route Milestone 1 already has -- no new
answer endpoint, no change to `AnswerIn`/`AnswerOut`. Internally, after
its existing grade + `apply_mastery_update` + `ANSWER_SUBMITTED`/
`MASTERY_UPDATED` event-logging (all unchanged), the route additionally
checks whether `question.quiz_session_id is not None`; if so, it logs a
new `quiz_difficulty_adjusted` event (FR-009) and checks whether this
quiz's answered-count has reached its `question_count`, marking
`QuizSession.status = "completed"` if so.

**Rationale**: This is the most literal possible implementation of
FR-004 ("updates ... via the exact same mechanism as a non-quiz
question, ... not a separate code path") -- there is no second grading
or mastery-update path to keep in sync. The added quiz-specific
bookkeeping is a conditional *addition* after the shared logic, not a
fork of it, so it doesn't reintroduce the kind of subject-id-keyed
branching Constitution Principle III prohibits (this is a feature-type
check -- "is this question quiz-linked" -- not a subject-id check).

**Alternatives considered**: A separate `POST /api/quizzes/.../answer`
endpoint wrapping the same grading logic. Rejected: would require
extracting the grading/mastery-update logic into a shared helper anyway
(no reuse savings) while adding a second endpoint surface and a second
place `AnswerOut`'s contract could drift, for no benefit FR-004 asks
for.

## 5. Difficulty bounds are the platform-wide `easy`/`hard` range, not a per-topic-narrower one

**Decision**: FR-007's "content artifact's defined bounds" means the
existing fixed three-band scale (`easy`/`medium`/`hard`) everywhere
else in the engine already uses, not a per-topic subset. A topic's
`difficulty_calibration` dict (validator.py) may legally omit a band's
guidance text, but that only means the Assessment-Generation Agent's
prompt gets less specific guidance for that band -- it does not remove
that band from the selectable range.

**Rationale**: Every other difficulty-aware code path in this codebase
(`_DIFFICULTY_BY_BAND` in `agents/sequencing/agent.py`,
`preferred_question_type`, placement's fixed `easy`) already treats the
three bands as a global constant, never per-topic-configurable.
Introducing a per-topic-narrower bound here would be a new concept this
milestone doesn't need and no FR asks for -- `_validate_difficulty_calibration`
only constrains calibration *guidance text* keys to be a subset of the
three bands, it does not define a topic-specific min/max.

**Alternatives considered**: Deriving bounds from which bands a topic's
`difficulty_calibration` dict actually has keys for. Rejected: no FR
motivates this, and it would silently produce inconsistent bounds
across topics within the same subject depending on how thoroughly each
topic's calibration text was authored -- an authoring-completeness
accident, not a deliberate design choice.

## 6. New `AssessmentEventType.QUIZ_DIFFICULTY_ADJUSTED`, added via the existing enum-extension migration pattern

**Decision**: One new event type, `quiz_difficulty_adjusted`, logged
once per in-quiz question generated (FR-009), with a payload capturing
`quiz_session_id`, `topic_id`, the prior and new difficulty band, the
streak count at decision time, and whether a bound was held. Added via
`ALTER TYPE assessment_event_type ADD VALUE`, the exact same technique
spec 002's `533736af33d7_recommendation_event_types` migration already
used to add its three event types.

**Rationale**: Reuses an established, working migration pattern rather
than inventing a new one; keeps `AssessmentEvent` as the single
pedagogical-decision log (Constitution Principle V) rather than a
parallel quiz-specific audit table.

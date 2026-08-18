# Feature Specification: Adaptive Difficulty Quiz

**Feature Branch**: `005-adaptive-quiz`

**Created**: 2026-08-14

**Status**: `/speckit-clarify` complete (4 questions resolved); pending
`/speckit-plan`

**Input**: User description: "A bounded, named quiz session with
difficulty that adapts within the session based on in-quiz performance,
feeding results back into the learner's persistent mastery state on
completion"

## Clarifications

### Session 2026-08-18

- Q: When a learner answers a question correctly in a quiz, should the next question for that topic move up exactly one difficulty band on the existing easy→medium→hard scale (and down one band on an incorrect answer), rather than some other step size or streak-based rule? → A: Streak-based -- requires 2 consecutive correct/incorrect answers (per topic, independent of other topics in the quiz) before moving one band, holding at the edge per FR-007. The streak counter resets to zero every time the band changes, so each subsequent band move again requires 2 fresh consecutive answers in the new direction.
- Q: Should `QuizSession` be a new, real Postgres table (with a migration), rather than being inferred purely from tagging existing `GeneratedQuestion`/`AssessmentEvent` rows with a generated session id the way placement's `placement_session_id` already works? → A: Yes -- a new `quiz_sessions` table (id, learner_id, topic_ids, question_count, status, started_at, completed_at), with `GeneratedQuestion` gaining a nullable `quiz_session_id` FK so its questions can be grouped, since a quiz's configuration must persist across multiple stateless requests before its first question even exists (unlike placement, which is single-shot).
- Q: For a quiz spanning multiple topics, should questions cycle through the chosen topics in round-robin order rather than finishing all of one topic's questions before moving to the next? → A: Round-robin -- cycle through the chosen topics in the order selected, one question per topic per cycle, so every topic's per-topic streak stays live throughout the quiz rather than only mattering within an uninterrupted block.
- Q: If the near-duplication check keeps failing after a bounded number of retries for a topic, should the quiz end early in a defined "ended early" state rather than ever serving a near-duplicate question? → A: Yes -- the quiz session moves to a new `ended_early` status once retries are exhausted for a topic; questions already answered before that point still count normally toward mastery state (FR-006), keeping SC-004's zero-near-duplicate guarantee absolute rather than falling back to Milestone 1's best-effort behavior.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Take a quiz that gets harder or easier as you go (Priority: P1)

A learner starts a quiz on a chosen topic with a fixed question count.
Each subsequent question's difficulty adjusts based on how they did on
the prior question within that same quiz -- correct answers escalate
difficulty, incorrect answers de-escalate it -- and the quiz ends with a
score and summary.

**Why this priority**: This is the entire point of the milestone -- a
bounded, adaptive assessment session is a genuinely different product
surface from the one-question-at-a-time flow Milestone 1 established,
and it's the direct answer to "does the product support quizzes."

**Independent Test**: Given a scripted sequence of correct and incorrect
answers within a quiz, confirm the difficulty of each subsequent
question moves in the expected direction and the quiz reaches a defined
completion state with a score.

**Acceptance Scenarios**:

1. **Given** a learner starts a quiz on a topic with a chosen question
   count, **When** they answer a question correctly, **Then** the next
   question in the quiz is generated at an equal or higher difficulty.
2. **Given** a learner answers a question incorrectly, **When** the next
   question is generated, **Then** it is at an equal or lower
   difficulty.
3. **Given** a quiz reaches its configured question count, **When** the
   last question is answered, **Then** the quiz reaches a defined
   completion state showing a score and a summary of performance by
   topic and difficulty level.
4. **Given** an identical scripted sequence of correct/incorrect answers
   is replayed, **When** the quiz runs again, **Then** the resulting
   difficulty progression and final score are identical every time
   (Constitution Principle I, extended to quiz sessions -- not a new
   exception to it).

---

### User Story 2 - Quiz results count toward your real progress (Priority: P1)

Every question answered within a quiz updates the learner's persistent
mastery state exactly the same way a regular adaptive question would --
a quiz is not a disconnected side activity with its own separate score
that means nothing outside the quiz.

**Why this priority**: Without this, a quiz would be a parallel,
disconnected feature that undermines the "one real mastery model"
principle the whole platform is built on -- this is what keeps the quiz
feature honest rather than becoming a second, inconsistent source of
truth about what a learner knows.

**Independent Test**: Complete a quiz and confirm every question
answered within it appears in the learner's regular assessment-event
history and has updated their persistent mastery state, verifiable via
the same mastery-state read used elsewhere in the platform (e.g. the
learner dashboard).

**Acceptance Scenarios**:

1. **Given** a learner completes a quiz, **When** their mastery state is
   inspected afterward, **Then** every question answered during the quiz
   is reflected in it, updated via the exact same mechanism as a
   non-quiz question (Milestone 1's existing mastery-update logic, not a
   separate code path).
2. **Given** a learner abandons a quiz partway through (e.g. closes the
   browser), **When** their mastery state is inspected afterward,
   **Then** every question they did answer before abandoning has still
   updated their mastery state -- only the quiz's own completion
   summary is missing, not the underlying learning data.

---

### User Story 3 - Difficulty adjustment stays within real bounds (Priority: P2)

A learner who answers every question correctly (or incorrectly) in a row
doesn't cause the system to request a difficulty level that doesn't
exist.

**Why this priority**: A real, if less common, path through the feature
that a naive implementation could mishandle by erroring or requesting an
undefined difficulty level -- worth its own scenario given how easy it
is to overlook boundary behavior until it's hit in practice.

**Independent Test**: Script an "all correct" run and an "all incorrect"
run against a content artifact with known difficulty bounds, and confirm
both runs reach and hold at the maximum/minimum difficulty without
error.

**Acceptance Scenarios**:

1. **Given** a learner answers every question correctly in a quiz,
   **When** difficulty would escalate past the content artifact's
   maximum defined difficulty, **Then** the system holds at the maximum
   and continues generating questions there, rather than erroring or
   requesting an undefined level.
2. **Given** a learner answers every question incorrectly, **When**
   difficulty would de-escalate past the minimum, **Then** the system
   holds at the minimum, symmetrically.

---

### Edge Cases

- What happens if a learner requests a quiz question count that risks
  significant near-duplication for a narrow topic (e.g. 20 questions on
  a topic with limited distinct content)? (The system must apply at
  least as strict a near-duplication check within a single quiz as
  Milestone 1's cross-session rule (FR-008) -- guaranteeing zero
  duplicates within one session, not just "unlikely." If a fresh,
  distinct question genuinely can't be generated for a topic after a
  bounded number of retries, the *entire* quiz session moves to a new
  `ended_early` status -- not just that one topic being dropped from the
  round-robin rotation while the rest of the quiz continues -- rather
  than ever serving a near-duplicate; questions already answered before
  that point are unaffected (FR-006), Clarifications 2026-08-18. Ending
  the whole session (checklist review, 2026-08-18) is the deliberate
  choice: a topic that has run out of distinct questions is a signal the
  learner picked too many questions for that topic's content depth, and
  silently reshuffling the remaining rotation around it would hide that
  from them rather than surface it via a defined, visible state.)
- What happens if a quiz spans multiple topics rather than one? (In
  scope: the in-quiz difficulty adjustment applies per-topic
  independently within the quiz, since difficulty is topic-relative, not
  a single global number across unrelated topics. Questions cycle through
  the chosen topics in round-robin order -- one question per topic per
  cycle, in the order the topics were selected -- rather than completing
  one topic before starting the next, Clarifications 2026-08-18.)
- What happens if the Recommendation Agent's weak-area logic runs while
  a quiz is in progress but not yet complete? (Already-answered
  in-quiz questions count as regular assessment evidence immediately per
  User Story 2 -- no special-casing needed; the Recommendation Agent
  simply sees the same mastery state it always would.)
- Can a learner resume a quiz they left `in_progress` (Key Entities)
  after navigating away? (Out of scope for this milestone, checklist
  review 2026-08-18: nothing in the API prevents continuing to answer an
  `in_progress` session's questions if the client still holds its
  `quiz_session_id`, but no UI flow exists to rediscover or relist a
  past session's id once it's lost -- e.g. after closing the browser tab
  -- so in practice an abandoned quiz is not resumable through the
  product, only through direct API access to an id the client already
  has.)
- What happens if two requests race -- e.g. answering the same in-quiz
  question twice, or requesting the next question twice before the
  first response is recorded? (Answering reuses the existing
  `POST /api/questions/{id}/answer` endpoint unchanged (FR-004), which
  already rejects a second answer to the same question with a conflict
  error -- this guarantee is inherited, not reintroduced. Racing
  next-question requests receive the same handling Milestone 1's
  next-question flow already has, with no new guarantee added by this
  feature; this is an accepted limitation consistent with the platform's
  existing single-learner, no-auth scope, not a gap this milestone
  closes, checklist review 2026-08-18.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support starting a quiz scoped to one or
  more topics, all belonging to the same subject, with a learner-chosen
  fixed question count between 1 and 50 inclusive (checklist review,
  2026-08-18 -- an explicit bound so "learner-chosen" is not implicitly
  unbounded; 50 is a generous but finite ceiling, not derived from a
  measured constraint). Starting a quiz MUST be rejected if `topic_ids`
  is empty, contains a duplicate, spans more than one subject, or if
  `question_count` is outside that range. If `question_count` is less
  than the number of chosen topics, the quiz simply never reaches the
  later topics in the round-robin order (FR-002) before completing --
  this is expected, not an error.
- **FR-002**: Within a quiz, each subsequent question's difficulty MUST
  be chosen using a deterministic, streak-based in-quiz adjustment rule,
  tracked independently per topic: a topic's first question in a quiz is
  always requested at `easy` difficulty (the same "unknown → easy"
  convention placement already uses, checklist review 2026-08-18); two
  consecutive correct answers on that topic within the quiz move its
  difficulty up exactly one band on the existing easy/medium/hard scale,
  two consecutive incorrect answers move it down one band, and the
  per-topic streak counter resets to zero whenever that two-answer
  threshold is reached -- whether or not the band itself actually moved,
  i.e. it also resets when the threshold is reached but the band was
  already held at a bound per FR-007 (Clarifications, 2026-08-18;
  streak-at-a-held-bound behavior added checklist review 2026-08-18) --
  distinct from, and not a replacement for, the Sequencing Agent's own
  cross-session next-topic selection, which operates at a different time
  horizon and is unaffected by this feature.
- **FR-003**: Given an identical sequence of in-quiz answers, the
  resulting difficulty progression and final score MUST be identical
  across repeated runs.
- **FR-004**: Every question answered within a quiz MUST be recorded as
  a regular assessment event and MUST update the learner's persistent
  mastery state via the exact same mechanism as a non-quiz question.
- **FR-005**: A quiz MUST reach a defined completion state (score,
  summary of performance by topic and difficulty) when its configured
  question count is reached. `score` is the raw count of correctly
  answered questions out of the total answered so far, out of
  `question_count` once complete -- not weighted by difficulty
  (checklist review, 2026-08-18). A quiz that ends via `ended_early`
  (FR-008) MUST still produce a score/summary in this same shape,
  covering whatever questions were answered before it ended -- not a
  different or missing representation (checklist review, 2026-08-18).
- **FR-006**: An abandoned, incomplete quiz MUST NOT lose the mastery
  effect of any question already answered before abandonment -- only the
  quiz's own completion summary is affected, never the underlying
  assessment data.
- **FR-007**: In-quiz difficulty adjustment MUST NOT request a difficulty
  level outside the content artifact's defined bounds -- hitting a bound
  MUST be handled by holding at that bound, never by erroring. These
  bounds are the platform-wide easy/medium/hard scale uniformly across
  every topic, not a possibly-narrower range configured per topic --
  a topic's `difficulty_calibration` guidance text may omit a band
  without removing that band from the selectable range (checklist
  review, 2026-08-18; matches every other difficulty-aware code path on
  the platform, none of which treats difficulty bounds as
  per-topic-configurable).
- **FR-008**: Questions within a single quiz session MUST guarantee zero
  near-duplication, at least as strict as Milestone 1's cross-session
  near-duplication rule (FR-008). If a fresh, distinct question cannot be
  generated for a topic after a bounded number of retries, the quiz MUST
  move to a defined `ended_early` state rather than ever serving a
  near-duplicate question (Clarifications, 2026-08-18).
- **FR-009**: Every in-quiz difficulty-adjustment decision MUST be
  logged and traced per Constitution Principle V, the same standard as
  any other agent decision on this platform. The logged record MUST
  capture whether a bound was held (FR-007) as well as the resulting
  band, so "why was this question this difficulty" stays answerable
  even for a held-at-bound decision, not only a decision that moved the
  band (checklist review, 2026-08-18).

### Key Entities *(include if feature involves data)*

- **QuizSession**: a new persisted Postgres entity (Clarifications,
  2026-08-18) -- the topic(s) and configured question count chosen at
  start, its current status (`in_progress` | `completed` | `ended_early`),
  and timestamps for start/completion. An "abandoned" quiz is simply one
  left `in_progress` with no further activity -- nothing actively
  transitions it to a distinct status (FR-006 only requires that
  already-answered questions keep their mastery effect, not that status
  itself changes). The ordered list
  of (question, answer, correctness, difficulty-at-that-step) for the
  session, and its final score/summary once complete, are derived by
  querying the
  `GeneratedQuestion`/`AssessmentEvent` rows tagged with this session's
  id (via a nullable `quiz_session_id` FK on `GeneratedQuestion`) rather
  than duplicated onto the session row itself.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a scripted sequence of correct/incorrect answers,
  the resulting difficulty progression and final score are identical
  across ten repeated runs (this claim is scoped to difficulty
  progression and score only -- generated question *text* is LLM-based
  and is not itself claimed to be deterministic, checklist review
  2026-08-18).
- **SC-002**: 100% of questions answered within quiz sessions in the
  test suite are verified to also appear in the learner's regular
  assessment-event history with a correspondingly updated mastery state
  -- verified by an automated check comparing quiz-session data against
  persisted mastery state, passing when each quiz-answered question's
  `update_count` increment and posterior `p_mastery` exactly match what
  the same answer would have produced via a non-quiz question (checklist
  review, 2026-08-18).
- **SC-003**: A scripted "all correct" run and a scripted "all incorrect"
  run each correctly reach and hold at the content artifact's maximum
  and minimum defined difficulty, respectively, without error.
- **SC-004**: Zero near-duplicate questions occur within any single quiz
  session across the test suite, verified by an automated check using
  the same similarity criteria as Milestone 1's cross-session
  near-duplication check (FR-008, checklist review 2026-08-18).
- **SC-005**: An abandoned quiz session, deliberately stopped partway in
  a test, is confirmed to have already updated mastery state for every
  question answered before the stop.

## Assumptions

- Adaptive difficulty within a quiz reuses the Assessment-Generation
  Agent's existing difficulty-parameterized question generation and adds
  a new, lightweight in-quiz adjustment rule. This does not introduce a
  new agent -- it's a new session/interaction pattern layered on the
  existing agents' responsibilities, not a distinct responsibility with
  its own evaluation criteria in the sense Constitution Principle IV
  requires for a new agent boundary. Concretely (checklist review,
  2026-08-18): the in-quiz rule is a pure, deterministic step function
  over a boolean correct/incorrect stream with no model call, no prompt,
  and no output requiring its own quality evaluation the way a
  generated question or a grading decision does -- unlike the
  Sequencing Agent's mastery-based ranking (which reads a real
  statistical model as its own responsibility), this rule has nothing
  that could independently need re-versioning, re-evaluating, or
  failing in a way separate from the Assessment-Generation Agent call it
  parameterizes. It fails Principle IV's bar for a new boundary on every
  count that bar names, not merely by assertion.
- A completed or abandoned quiz's questions are not given special
  treatment by the Recommendation Agent beyond their normal effect on
  mastery state -- a quiz is simply more assessment evidence, not a
  privileged signal.
- Instructor-configured or instructor-assigned quizzes (an instructor
  building a specific quiz and assigning it to a roster) are out of
  scope for this milestone. This covers a learner-initiated quiz on a
  subject/topic they choose themselves; instructor-assigned quizzes
  would be a natural extension of the instructor-classroom milestone if
  wanted later, not built here.
- This milestone depends on Milestone 1 (Assessment-Generation Agent,
  content-artifact difficulty bands) only. It does not require the
  Recommendation Agent, the personalization-evaluation harness,
  free-text grading, classroom features, the Tutor Agent, or multimodal
  support -- though it is sequenced alongside the Learner Dashboard to
  complete a full, compelling solo-learner experience before the
  platform's scope broadens to grading depth and multi-tenancy.

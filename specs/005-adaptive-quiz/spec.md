# Feature Specification: Adaptive Difficulty Quiz

**Feature Branch**: `005-adaptive-quiz`

**Created**: 2026-08-14

**Status**: Draft -- pending `/speckit-clarify`

**Input**: User description: "A bounded, named quiz session with
difficulty that adapts within the session based on in-quiz performance,
feeding results back into the learner's persistent mastery state on
completion"

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
  duplicates within one session, not just "unlikely.")
- What happens if a quiz spans multiple topics rather than one? (In
  scope: the in-quiz difficulty adjustment applies per-topic
  independently within the quiz, since difficulty is topic-relative, not
  a single global number across unrelated topics.)
- What happens if the Recommendation Agent's weak-area logic runs while
  a quiz is in progress but not yet complete? (Already-answered
  in-quiz questions count as regular assessment evidence immediately per
  User Story 2 -- no special-casing needed; the Recommendation Agent
  simply sees the same mastery state it always would.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support starting a quiz scoped to one or
  more topics with a learner-chosen fixed question count.
- **FR-002**: Within a quiz, each subsequent question's difficulty MUST
  be chosen using a deterministic, documented in-quiz adjustment rule
  based on performance on the prior question in that same topic within
  the same quiz -- distinct from, and not a replacement for, the
  Sequencing Agent's own cross-session next-topic selection, which
  operates at a different time horizon and is unaffected by this
  feature.
- **FR-003**: Given an identical sequence of in-quiz answers, the
  resulting difficulty progression and final score MUST be identical
  across repeated runs.
- **FR-004**: Every question answered within a quiz MUST be recorded as
  a regular assessment event and MUST update the learner's persistent
  mastery state via the exact same mechanism as a non-quiz question.
- **FR-005**: A quiz MUST reach a defined completion state (score,
  summary of performance by topic and difficulty) when its configured
  question count is reached.
- **FR-006**: An abandoned, incomplete quiz MUST NOT lose the mastery
  effect of any question already answered before abandonment -- only the
  quiz's own completion summary is affected, never the underlying
  assessment data.
- **FR-007**: In-quiz difficulty adjustment MUST NOT request a difficulty
  level outside the content artifact's defined bounds -- hitting a bound
  MUST be handled by holding at that bound, never by erroring.
- **FR-008**: Questions within a single quiz session MUST guarantee zero
  near-duplication, at least as strict as Milestone 1's cross-session
  near-duplication rule (FR-008).
- **FR-009**: Every in-quiz difficulty-adjustment decision MUST be
  logged and traced per Constitution Principle V, the same standard as
  any other agent decision on this platform.

### Key Entities *(include if feature involves data)*

- **QuizSession**: the topic(s) and configured question count chosen at
  start, the ordered list of (question, answer, correctness,
  difficulty-at-that-step) for the session so far, its current
  completion state, and its final score/summary once complete.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a scripted sequence of correct/incorrect answers,
  the resulting difficulty progression and final score are identical
  across ten repeated runs.
- **SC-002**: 100% of questions answered within quiz sessions in the
  test suite are verified to also appear in the learner's regular
  assessment-event history with a correspondingly updated mastery state
  -- verified by an automated check comparing quiz-session data against
  persisted mastery state.
- **SC-003**: A scripted "all correct" run and a scripted "all incorrect"
  run each correctly reach and hold at the content artifact's maximum
  and minimum defined difficulty, respectively, without error.
- **SC-004**: Zero near-duplicate questions occur within any single quiz
  session across the test suite, verified by an automated check.
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
  requires for a new agent boundary.
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

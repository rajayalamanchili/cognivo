# Feature Specification: Tutor Agent Answer-Shielding

**Feature Branch**: `023-tutor-answer-shielding`

**Created**: 2026-09-04

**Status**: Draft

**Input**: User description: "Prevent the Tutor Agent from giving a direct final answer to a learner's currently-open, unanswered practice or assessment question" (per `roadmap.md`'s "Out of current roadmap" entry, "Tutor Agent answer-shielding during practice/assessment")

## Clarifications

### Session 2026-09-04

- Q: If the system can't confidently tell whether a learner's tutor question matches their currently-open question, what should the Tutor Agent do? → A: Fail toward shielding — respond with a hint-only answer on any inconclusive determination.
- Q: Should the shielding check be required to fit inside the Tutor Agent's existing 3-second (p95) time-to-first-token target, or is a looser latency allowance acceptable? → A: No latency requirement for this feature — correctness is the only success criterion here; performance is left unmeasured, not a new gate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tutor declines to hand over the answer to an open question (Priority: P1)

A learner has a question displayed on screen that they have not yet
answered -- during practice, a quiz, or placement. In parallel, they
open the Tutor Agent chat and ask something that would, if answered
directly, give away that question's correct answer (e.g. asking the
Tutor to just solve it, or to state the final answer outright). Instead
of answering directly, the Tutor Agent declines to reveal the final
answer and instead offers a Socratic hint -- a nudge toward the
reasoning, not the answer itself.

**Why this priority**: This is the entire reason the feature exists.
Without it, a learner can trivially bypass the mastery model's
diagnostic value by asking the Tutor Agent for the answer to whatever
they're being assessed on, making every subsequent "mastery" reading
for that question meaningless (undermines Constitution Principle I).

**Independent Test**: Can be fully tested by having a learner open a
practice question, leave it unanswered, ask the Tutor Agent a question
that would reveal that answer, and verifying the response contains a
hint rather than the final answer.

**Acceptance Scenarios**:

1. **Given** a learner has a practice question displayed and has not
   yet submitted an answer, **When** they ask the Tutor Agent to solve
   or state the answer to that question, **Then** the Tutor Agent
   declines to state the final answer and instead offers a hint that
   points toward the reasoning without revealing it.
2. **Given** a learner has an in-progress quiz question displayed and
   unanswered, **When** they ask the Tutor Agent something that would
   reveal that question's answer, **Then** the same shielding behavior
   applies as it does during practice.

---

### User Story 2 - Tutor keeps answering normally when nothing is being shielded (Priority: P2)

A learner asks the Tutor Agent a question that has nothing to do with
any question currently displayed and unanswered -- a general concept
question, a question about a different topic, or a question asked while
no question is currently open at all. The Tutor Agent answers exactly
as it does today: grounded, direct, no hint-only hedging.

**Why this priority**: Answer-shielding must not degrade the Tutor
Agent's primary value (Milestone 9) for the common case. Over-shielding
-- declining to give real answers to legitimate conceptual questions --
would be a regression, not a safety improvement.

**Independent Test**: Can be fully tested by asking the Tutor Agent a
question unrelated to any currently open question and confirming the
response is a normal, direct, grounded answer with no hint-only
behavior applied.

**Acceptance Scenarios**:

1. **Given** a learner has no question currently displayed and
   unanswered, **When** they ask the Tutor Agent any in-scope question,
   **Then** the Tutor Agent answers normally.
2. **Given** a learner has a question open and unanswered, **When**
   they ask the Tutor Agent about a different topic entirely, **Then**
   the Tutor Agent answers that question normally rather than shielding
   it.

---

### User Story 3 - Shielding lifts once the question is no longer open (Priority: P3)

A learner submits an answer to their open question (or it stops being
"open" for some other reason -- a quiz ends, the session times out).
They then ask the Tutor Agent about that same question, e.g. "why was I
wrong" or "explain that one to me now." The Tutor Agent answers
normally, since shielding a question that has already been
graded/recorded no longer protects anything and would only block a
legitimate follow-up.

**Why this priority**: Shielding that outlives its purpose would harm
the same conversational-help value Milestone 9 exists to provide, for
no remaining diagnostic benefit -- lower priority than US1/US2 because
it is a boundary condition on an already-working mechanism, not the
mechanism itself.

**Independent Test**: Can be fully tested by answering a previously
shielded question, then re-asking the Tutor Agent about it and
confirming a normal, direct answer is now given.

**Acceptance Scenarios**:

1. **Given** a learner has just submitted an answer to a question that
   was previously shielded, **When** they ask the Tutor Agent about
   that same question, **Then** the Tutor Agent answers normally.

---

### Edge Cases

- What happens when a learner has more than one question open and
  unanswered at once (e.g. an in-progress quiz question and a separate
  stale, never-revisited practice question)? Shielding applies relative
  to whichever open question the learner's tutor question actually
  concerns; an unrelated open question elsewhere does not shield an
  otherwise-normal answer (see User Story 2).
- What happens when the currently-open question gets answered or
  submitted while the Tutor Agent is already mid-response to a shielded
  question? The in-flight response is not retroactively changed; the
  next question the learner asks reflects the now-current (unshielded)
  state.
- What happens when a learner has no question open at all? The Tutor
  Agent answers normally -- shielding only ever narrows behavior
  relative to today, never blocks something that would otherwise be
  answerable.
- What happens when shielding declines to answer -- is that decision
  itself recorded anywhere? Yes: a shielded exchange must be traceable
  after the fact (which open question triggered it), consistent with
  every other personalization/grading decision in this project
  (Constitution Principle V).
- This feature does **not** attempt to detect a learner using an
  external tool (e.g. pasting the question into a different chatbot) --
  that is explicitly out of scope; see Assumptions.
- What happens when the system cannot confidently determine whether the
  tutor question matches the currently-open question (the
  determination errors, times out, or is ambiguous)? The system
  defaults to a hint-only response rather than risking a direct answer
  (FR-010) -- an inconclusive determination is treated the same as a
  confirmed match, not the same as no open question at all.
- What happens when an instructor cancels a quiz assignment while a
  targeted learner has that attempt's question open and unanswered?
  The question stops being "open" (FR-006) -- a tutor question about it
  afterward is answered normally, since the assignment ending is as
  final as the learner having answered it themselves.
- What happens when a learner simply abandons a learner-initiated
  (non-assigned) quiz, leaving its last question open and unanswered
  forever? This system has no "abandoned" signal for that case today
  (an abandoned quiz is already, product-wide, indistinguishable from
  one still in progress) -- that question stays "open," and therefore
  shieldable, indefinitely. This is an existing product characteristic
  this feature inherits, not a new gap it introduces.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST determine, at the time a learner submits
  a question to the Tutor Agent, whether that learner currently has a
  question displayed to them that has not yet had an answer submitted
  for it, in the same subject as the tutor question.
- **FR-002**: The kinds of in-progress question context that count as
  "currently open" for the purposes of FR-001 MUST include in-progress
  practice questions, in-progress quiz questions (learner-initiated or
  instructor-assigned, per Milestone 8), and in-progress placement
  questions -- shielding applies everywhere a question can be
  displayed to a learner without yet having a submitted answer, not
  only learner-initiated sessions.
- **FR-003**: When a currently-open, unanswered question exists (per
  FR-001/FR-002) and the learner's tutor question would, if answered
  directly, reveal that question's correct final answer, the system
  MUST decline to state that final answer and instead respond with a
  hint that guides the learner's reasoning without revealing it.
- **FR-004**: The system MUST decide whether a learner's tutor question
  "would reveal the final answer" to a specific currently-open question
  using a direct-or-paraphrase matching standard: shielding applies
  when the tutor question restates the open question's own content
  (exactly or in recognizably paraphrased form), or directly asks to
  have that open question solved or its answer stated -- MUST NOT
  shield a tutor question merely for being about the same topic as the
  open question when it does not itself ask for or restate that
  question's content, since that would block legitimate conceptual
  questions unrelated to the specific item being assessed.
- **FR-005**: When no currently-open, unanswered question exists for
  the learner in the tutor question's subject, or the tutor question
  does not concern the currently-open question, the system MUST answer
  exactly as it does today (Milestone 9 behavior), with no hint-only
  behavior applied.
- **FR-006**: Once a previously-open question is no longer open, the
  system MUST answer questions about it normally -- shielding MUST NOT
  persist past that point. "No longer open" means either: an answer has
  been submitted for it, or -- for an instructor-assigned quiz attempt
  specifically -- the assignment it belongs to was cancelled while the
  question was still unanswered (the only "ended without an answer"
  signal this system's existing quiz mechanism actually records; a
  plain learner-initiated quiz that's simply abandoned has no such
  signal at all and is already treated as indefinitely in-progress
  everywhere else in this product today, not only here -- see Edge
  Cases).
- **FR-007**: The system MUST record, for every shielded exchange,
  which currently-open question triggered the shielding decision, so
  the decision is inspectable after the fact using the same kind of
  after-the-fact reconstruction Milestone 9's User Story 3 already
  provides for grounding and delegation -- MUST NOT be a decision only
  the Tutor Agent itself can explain.
- **FR-008**: The system MUST NOT attempt to detect or flag a learner's
  use of an external tool outside this platform (e.g. a separate
  chatbot) to obtain an answer -- shielding is scoped only to what the
  Tutor Agent itself is asked and answers.
- **FR-009**: Shielding MUST NOT change how a question is graded, how
  mastery state is updated, or any other mechanism established in
  Milestones 1, 5, and 6 -- it changes only what the Tutor Agent is
  willing to say, never the scoring or personalization pipeline.
- **FR-010**: When the system cannot reach a confident determination of
  whether a tutor question matches a currently-open question (FR-004)
  -- the determination step errors, times out, or returns an ambiguous
  result -- the system MUST default to shielding (a hint-only response)
  rather than answering directly, so an inconclusive determination never
  results in revealing a final answer it should have shielded.

### Key Entities

- **Currently-Open Question**: A question (practice, quiz --
  learner-initiated or instructor-assigned -- or placement) that has
  been displayed to a learner but does not yet have a submitted answer
  recorded for it.
  Derived from existing question-display and answer-submission records
  already tracked elsewhere in the system; not a new persistent
  concept, just a new read against existing state.
- **Shielding Decision**: The record of whether, and why, a given Tutor
  Exchange (Milestone 9) was shielded -- which currently-open question
  (if any) triggered it. Extends a Tutor Exchange's existing
  after-the-fact inspectability rather than introducing a separate
  audit mechanism.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across a defined set of test tutor-questions that
  directly ask for the answer to a currently-open, unanswered question,
  at least 90% receive a hint-only response with no direct final answer
  revealed.
- **SC-002**: Across a defined set of test tutor-questions that are
  unrelated to any currently-open question, 100% receive a normal,
  unshielded answer -- shielding introduces no false positives against
  legitimate conceptual questions.
- **SC-003**: For 100% of shielded exchanges in a sample, an inspector
  can determine after the fact which currently-open question triggered
  the shielding, without asking the Tutor Agent itself to explain.
- **SC-004**: Once a previously-shielded question has been answered, a
  learner asking the Tutor Agent about that same question receives a
  normal, direct answer, verified across a defined set of test cases.
- **SC-005**: Milestones 1-13's full test suites still pass unmodified.

This feature introduces no latency success criterion of its own:
Milestone 9's existing SC-001 (3s p95 time-to-first-token) is neither a
gate nor an exemption for shielding -- correctness (SC-001 through
SC-004 above) is what this feature is measured against; how much time
the shielding determination adds is left unmeasured and unconstrained,
not silently promised to fit inside the existing budget.

## Assumptions

- Detection of "currently open, unanswered" (FR-001) is derived from
  question-display and answer-submission state the system already
  records (Milestone 1 onward) -- this feature does not require a new
  frontend signal (e.g. a heartbeat or "I'm viewing this" ping) or a new
  persistent session-state table; it is a new read against existing
  data, not a new source of truth.
- Access model is unchanged from Milestone 9: a guardian's own session
  acting on a targeted real learner's behalf, or the seeded demo
  learner. No new real-learner-facing login surface is introduced.
- All of Milestone 9's existing mechanisms -- rate limiting, one active
  exchange per session, streaming, and the FR-016 citation channel --
  are unchanged. Shielding is a new decision made as part of producing
  an exchange's answer, not a new gate that runs before or after that
  flow.
- Grading, mastery-state updates, and difficulty adaptation (Milestones
  1, 5, 6) are entirely unaffected -- this feature only ever changes
  what the Tutor Agent says, never how a question is scored or how
  mastery is computed.
- Consistent with the roadmap's own reasoning for this backlog item,
  this feature deliberately does not attempt to detect a learner's use
  of an external tool to get an answer (FR-008) -- unreliable,
  false-positive-prone, and a worse outcome for a real K-12 learner than
  an occasional missed instance.
- A shielded (hint-only) response is not visually or textually flagged
  to the learner as "this was shielded" -- it is simply the answer the
  Tutor Agent gives, worded as a hint. No new frontend indicator is
  introduced; the audit trail (FR-007) is what makes the decision
  inspectable, not a learner-facing label. This is a deliberate choice,
  not an oversight.
- Latency added by the shielding determination is explicitly
  unmeasured and unconstrained by this spec -- Milestone 9's existing
  3s p95 time-to-first-token target is not extended to cover it, and no
  new latency target is introduced for it either. Whether shielding's
  added cost is acceptable in practice is left to be judged when it's
  actually measured, not decided speculatively here.

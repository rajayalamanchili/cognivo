# Feature Specification: Math and Science Notation for Free-Text Answers

**Feature Branch**: `033-stem-notation`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "Proper math/science notation for free-text answers"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Learner enters a notated answer (Priority: P1)

A learner answering a free-text question that requires math or science
notation (e.g. "what is 1/4 + 1/4?", "write the chemical formula for
water") can enter their answer using real fractions, exponents/
superscripts, and subscripts, instead of typing a plain-text
approximation like "1/4" with a slash or "H2O" with no true subscript.

**Why this priority**: Without this, a learner's plain-text
approximation of a correct answer risks being marked wrong purely
because it doesn't match the rubric's notated form -- a correctness
problem, not just a cosmetic one, and the one this feature exists to
close.

**Independent Test**: Can be fully tested by answering a free-text
question that requires a fraction, an exponent, and a subscript, and
confirming each renders and submits as real notation rather than a
plain-text workaround.

**Acceptance Scenarios**:

1. **Given** a free-text question whose rubric-accepted answer is a
   fraction, **When** the learner enters that fraction using the
   notation input, **Then** the submitted answer is graded correct.
2. **Given** a free-text question whose rubric-accepted answer includes
   an exponent, **When** the learner enters the base and exponent using
   the notation input, **Then** the answer displays with the exponent
   rendered as a superscript, not inline text.
3. **Given** a biology question expecting a chemical formula with a
   subscript (e.g. "H₂O"), **When** the learner enters the formula
   using the notation input, **Then** the submitted answer is graded
   correct.

---

### User Story 2 - Grading is unaffected by notation (Priority: P2)

A learner's notated answer is graded exactly as an equivalent
plain-text answer already is today, so adding notation input doesn't
quietly loosen, tighten, or otherwise change grading correctness.

**Why this priority**: Notation input is worthless if grading can't
reliably evaluate it -- this is what makes User Story 1 actually usable,
but the input UI alone is independently demonstrable first.

**Independent Test**: Can be fully tested by submitting the same
correct answer twice -- once with notation, once as today's plain-text
approximation of the same value -- and confirming both grade correct.

**Acceptance Scenarios**:

1. **Given** a free-text question, **When** a learner submits a
   correct answer using notation (e.g. a real fraction character),
   **Then** it is graded correct exactly as the equivalent plain-text
   form already would be.
2. **Given** the same question, **When** a learner submits an
   incorrect answer using notation, **Then** it is graded incorrect
   exactly as the equivalent plain-text form already would be.
3. **Given** an existing plain-text-only free-text question created
   before this feature, **When** a learner answers it exactly as they
   would have before, **Then** grading behavior is unchanged.

---

### Edge Cases

- What happens when a learner leaves an incomplete notated expression
  open (e.g. an unclosed fraction)? Handled by FR-007.
- What happens when a learner pastes plain-text notation typed
  elsewhere (e.g. "1/2" from a text editor) into the notation input?
  It is accepted and treated as plain text, not auto-converted to a
  structured fraction -- consistent with today's answer field never
  having tried to interpret plain-text math.
- What happens on a subject/question that has no notation need at all
  (e.g. a plain short-answer question)? The input behaves exactly as
  today's plain-text field; notation controls are simply unused, not a
  subject-conditional code path (Constitution Principle III).
- What happens for a multi-step process-graded question (Milestone 16)
  where one intermediate step needs notation? That step's input gets
  the same notation support as a single-answer question; grading
  compares that step the same rubric-driven way it compares any other
  step.
- What happens to free-text answers already stored before this feature
  shipped? They remain exactly as stored (plain text) and are not
  retroactively migrated or reformatted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The free-text and multi-step answer inputs MUST let a
  learner insert fractions, exponents/superscripts, and subscripts, in
  addition to plain text, on every question -- available uniformly, not
  conditional on whether a given question's rubric happens to need it
  (no such per-question signal exists or is introduced by this
  feature).
- **FR-002**: As a learner builds a notated answer, the input MUST
  display it with real notation (visually correct fractions/
  superscripts/subscripts) as they type, not as raw markup they'd have
  to mentally decode.
- **FR-003**: Question generation's existing rubric/answer-key authoring
  step MUST be free to express a notated concept using the same
  notation a learner would use, exactly as it already authors any other
  free-text wording today -- this is not a new authoring path.
- **FR-004**: Introducing notation input MUST NOT change how free-text
  or multi-step answers are graded -- grading continues to be the
  existing rubric-criteria evaluation (Constitution Principle II), and
  a learner's notated answer MUST be graded exactly as the equivalent
  plain-text form of the same answer already is today.
- **FR-005**: This capability MUST be available uniformly across all
  subjects (Constitution Principle III) -- a subject whose content
  never needs notation simply never exercises it; there MUST be no
  subject-ID-keyed conditional gating whether notation input is offered.
- **FR-006**: Multi-step, process-level graded questions (Milestone 16)
  MUST support notation on any individual step exactly as a
  single-answer question does, using that same step-comparison grading.
- **FR-007**: The input MUST reject (prevent submission of) a
  structurally invalid notated expression (e.g. an unclosed fraction)
  before it reaches grading.
- **FR-008**: Existing free-text answers stored before this feature
  ships MUST remain valid and unmodified; this feature is additive and
  does not migrate or reformat historical answers.
- **FR-009**: Every notated-answer submission MUST remain covered by
  the existing pedagogical audit log and Langfuse trace requirements
  (Constitution Principle V) exactly as a plain-text answer submission
  is today -- no new gap in "why was this marked wrong" traceability.

### Key Entities

- **Notated Answer**: A learner's existing free-text or multi-step-step
  answer string, now optionally containing math/science notation
  characters entered via the notation input -- the same field and
  storage shape as today's plain-text answer, not a new data type.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Learners answering a free-text question that requires a
  fraction, an exponent, or a subscript can do so without resorting to
  a plain-text workaround, verified across both of today's content
  subjects (algebra-1, biology).
- **SC-002**: Introducing notation causes zero grading regressions on
  existing plain-text-only free-text questions -- full existing
  regression suites (backend + frontend) still pass unchanged.
- **SC-003**: 100% of the notation a learner builds in the input
  displays as real notation, not raw markup, verified by automated
  test.
- **SC-004**: Question generation's existing validation step
  (Milestone 1's FR-011 flagging mechanism) accepts a generated
  question whose rubric criteria contain notation exactly as it accepts
  one that doesn't -- no new validation failure mode or flagged-for-
  review case is introduced by notation appearing in generated text.

## Assumptions

- Notation scope for this milestone is fractions, exponents/
  superscripts, and subscripts -- the set actually needed by today's
  two content subjects (algebra-1's exponents/fractions, biology's
  chemical-formula subscripts). Calculus notation (derivatives,
  integrals) is out of scope until a subject that actually needs it
  exists; adding it later is an additive extension of the same
  mechanism, not a redesign.
- Grading for free-text and multi-step questions continues to use the
  existing rubric-criteria LLM evaluation (Constitution Principle II)
  completely unchanged -- notation is additional input expressiveness,
  not a new grading mechanism, since that evaluation already judges
  semantic correctness rather than exact string matching.
- No new agent boundary: this is an input-widget addition layered on
  the existing free-text/multi-step input handling -- Assessment-
  Generation and Grading logic are untouched (FR-004) -- the same
  pattern Milestone 5's in-quiz difficulty adjustment used to justify
  staying out of a new agent (Constitution Principle IV).
- Applies to every question-answering flow that already has a
  free-text input (placement, untimed/timed practice, untimed/timed
  quiz, instructor-assigned quizzes) -- not a new, separate answer path.
- Historical free-text answers already stored are not backfilled into
  the new notated representation.
- No learner answer-history view or instructor per-answer review view
  exists in the product today (confirmed by reading the current
  instructor review flow and the quiz/practice post-grading feedback,
  which shows rubric-criteria text, never the learner's own submitted
  string echoed back) -- building either is a distinct, larger feature
  and out of scope here. Because notation is plain text, not markup,
  any such view built later renders it correctly automatically, with no
  dependency on this feature.

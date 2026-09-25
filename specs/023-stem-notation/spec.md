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

### User Story 2 - Grading recognizes equivalent notated forms (Priority: P2)

An instructor or the question-generation step authors a rubric's
accepted answer using notation; a learner's notated answer is compared
against that rubric the same deterministic way today's plain-text
answers are, so notation support doesn't quietly loosen or tighten
grading correctness.

**Why this priority**: Notation input is worthless if grading can't
reliably evaluate it -- this is what makes User Story 1 actually usable,
but the input UI alone is independently demonstrable first.

**Independent Test**: Can be fully tested by authoring a rubric with a
notated accepted answer and one notated distractor, then submitting
both and confirming only the accepted form grades correct.

**Acceptance Scenarios**:

1. **Given** a rubric whose accepted answer is a notated fraction,
   **When** a learner submits that exact notated fraction, **Then** it
   is graded correct.
2. **Given** the same rubric, **When** a learner submits a
   differently-notated but rubric-unlisted form (e.g. a decimal instead
   of the authored fraction), **Then** it is graded exactly as it would
   be today for an unlisted plain-text variant (i.e. no new equivalence
   behavior is introduced beyond what the rubric explicitly authors).
3. **Given** an existing plain-text-only free-text question created
   before this feature, **When** a learner answers it exactly as they
   would have before, **Then** grading behavior is unchanged.

---

### User Story 3 - Notated answers render correctly everywhere they're shown (Priority: P3)

A submitted notated answer displays correctly wherever a plain-text
answer displays today: the learner's own question-review/history view,
an instructor's content-review or grading-audit view, and the
pedagogical audit log's record of what was actually submitted.

**Why this priority**: A correct answer that becomes unreadable markup
outside the original answer box undermines Constitution Principle V's
"why was this marked wrong" traceability -- but this is a rendering
consistency concern layered on top of Stories 1-2, not a blocker to
demonstrating either.

**Independent Test**: Can be fully tested by submitting a notated
answer and confirming it renders identically (not as raw markup) in the
learner's review view and in the instructor content-review view.

**Acceptance Scenarios**:

1. **Given** a learner has submitted a notated answer, **When** they
   view it again in their own answer history, **Then** it renders with
   real notation, not raw markup tags.
2. **Given** an instructor opens a flagged or reviewed question that
   was answered with notation, **When** the answer displays in the
   review view, **Then** it renders identically to how the learner saw
   it.

---

### Edge Cases

- What happens when a learner submits an incomplete or malformed
  notated expression (e.g. an unclosed fraction)? The input MUST
  prevent submission of a structurally invalid expression rather than
  passing malformed markup to grading.
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

- **FR-001**: The free-text answer input MUST let a learner enter
  fractions, exponents/superscripts, and subscripts as structured
  notation, in addition to plain text, on any question where the
  rubric's accepted answer requires them.
- **FR-002**: A submitted notated answer MUST render with real
  notation (visually correct fractions/superscripts/subscripts), not
  raw markup, everywhere a plain-text answer renders today: the
  question view at submission time, the learner's own answer-history/
  review view, and any instructor content-review or grading-audit view.
- **FR-003**: Question generation MUST be able to author a rubric's
  accepted answer using the same notation a learner would use, so the
  answer key for a notated concept is unambiguous -- this is an
  extension of Constitution Principle II's existing rubric-authoring
  step, not a new authoring path.
- **FR-004**: Grading comparison for a notated answer MUST remain
  exact-match against the rubric's explicitly authored accepted form(s)
  -- introducing notation input MUST NOT introduce symbolic or
  algebraic equivalence checking (e.g. recognizing "2/4" as equal to
  "1/2") beyond what the rubric explicitly lists as accepted variants.
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

- **Notated Answer**: The canonical structured form of a learner's
  submitted answer when it includes math/science notation -- stored and
  compared in place of today's plain-text answer, but degrading to
  identical plain text when no notation is used.
- **Rubric Accepted-Answer Variant**: One or more notated forms of a
  correct answer authored alongside a question's existing answer
  key/rubric (Principle II), against which a learner's notated answer
  is exact-matched.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Learners answering a free-text question that requires a
  fraction, an exponent, or a subscript can do so without resorting to
  a plain-text workaround, verified across both of today's content
  subjects (algebra-1, biology).
- **SC-002**: Introducing notation causes zero grading regressions on
  existing plain-text-only free-text questions -- full existing
  regression suites (backend + frontend) still pass unchanged.
- **SC-003**: 100% of views that display a learner's notated answer
  (submission view, learner review/history, instructor content-review)
  render it as real notation, not raw markup, verified by automated
  test per view.
- **SC-004**: Rubric authors can specify a notated correct answer with
  the same reliability as today's plain-text rubric -- the FR-011
  flagged-for-review rate is not measurably increased by notation
  ambiguity.

## Assumptions

- Notation scope for this milestone is fractions, exponents/
  superscripts, and subscripts -- the set actually needed by today's
  two content subjects (algebra-1's exponents/fractions, biology's
  chemical-formula subscripts). Calculus notation (derivatives,
  integrals) is out of scope until a subject that actually needs it
  exists; adding it later is an additive extension of the same
  mechanism, not a redesign.
- Grading stays exact-match against explicitly rubric-authored notated
  variants -- no symbolic/algebraic equivalence engine. This keeps
  grading exactly as deterministic and rubric-driven as Principle II
  already requires, rather than introducing a fundamentally new
  correctness-evaluation capability.
- No new agent boundary: this is an input-widget and grading-comparison
  extension layered on the existing Assessment-Generation and Grading
  logic, the same pattern Milestone 5's in-quiz difficulty adjustment
  used to justify staying out of a new agent (Constitution Principle
  IV).
- Applies to every question-answering flow that already has a
  free-text input (placement, untimed/timed practice, untimed/timed
  quiz, instructor-assigned quizzes) -- not a new, separate answer path.
- Historical free-text answers already stored are not backfilled into
  the new notated representation.

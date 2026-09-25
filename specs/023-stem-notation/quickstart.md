# Quickstart: Math and Science Notation for Free-Text Answers

Validates spec.md's Success Criteria end to end. No backend changes
exist for this feature (`contracts/api.md`), so no migration or
backend restart is needed beyond the project's normal dev setup.

## Prerequisites

- Backend and frontend dev servers running (see repo root
  `README.md`/each app's own `AGENTS.md` for the standard `uv run`/
  `npm run dev` commands).
- A synthetic demo learner session (Milestone 1's seeded demo account
  is sufficient -- no real learner data needed).

## Scenario 1 -- Fraction input grades correctly (SC-001, SC-002)

1. Start an untimed practice session on the `algebra-1` subject and
   answer questions until a `free_text` question requiring a fraction
   appears (e.g. "What is 1/4 + 1/4?").
2. Use the notation toolbar's `½` button (or build `1/2` via the
   fraction control) to enter the answer, then submit.
3. **Expected**: graded correct, identically to submitting the
   plain-text string `"1/2"` on an equivalent question.

## Scenario 2 -- Exponent and subscript display while typing (SC-003)

1. On an `algebra-1` question expecting an exponent (e.g. "x squared"),
   use the exponent toolbar control to enter `x²`.
2. **Expected**: the input shows `x²` with a real superscript character
   as it's typed, not `x^2` or any markup tag.
3. Repeat on a `biology` question expecting a chemical formula (e.g.
   "water"), using the subscript control to enter `H₂O`.
4. **Expected**: the input shows `H₂O` with a real subscript character.

## Scenario 3 -- Zero grading regression on plain text (SC-002)

1. Run the existing free-text/multi-step backend test suites
   unchanged: `pytest backend/tests/contract/test_question_api.py
   backend/tests/unit/test_answer_time_spent.py` (and the broader
   suite at Polish time) -- all must still pass with zero changes to
   grading logic.
2. Answer a `free_text` question using only plain ASCII text (no
   notation toolbar use) end to end.
3. **Expected**: grades exactly as it did before this feature shipped.

## Scenario 4 -- Incomplete notation blocks submission (FR-007)

1. Start building a fraction (type a numerator, insert the fraction
   slash) but do not enter a denominator.
2. **Expected**: the Submit button stays disabled until the fraction is
   completed or the partial construct is removed.

## Scenario 5 -- Multi-step question supports notation per step (FR-006)

1. Answer a `multi_step` (process-level, Milestone 16) question whose
   rubric expects notation on one intermediate step.
2. Enter that step's answer using the notation toolbar; enter the
   remaining steps as plain text.
3. **Expected**: graded per-step exactly as an all-plain-text multi-step
   submission would be, with no per-step behavior difference introduced
   by notation.

## Automated coverage

- Frontend: new unit tests on the shared notation-toolbar component
  (button insertion, fraction/exponent/subscript mode state machine,
  submit-disabled-while-incomplete) plus updated
  `free-text-rejection-states.test.tsx`/`multi-step-question.test.tsx`
  assertions that notated input round-trips through `answerQuestion`
  unchanged.
- Backend: no new tests required beyond the existing free-text/
  multi-step contract and integration suites continuing to pass
  unchanged (SC-002) -- there is no new backend behavior to cover.

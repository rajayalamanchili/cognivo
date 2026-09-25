---

description: "Task list for Math and Science Notation for Free-Text Answers"
---

# Tasks: Math and Science Notation for Free-Text Answers

**Input**: Design documents from `/specs/023-stem-notation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Scope note**: Per `research.md` and `plan.md`, this feature is
frontend-only -- zero backend/API changes. `contracts/api.md` records
"no contract changes"; there is nothing to generate a contract test
against.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- File paths are exact and relative to the repo root

## Phase 1: Setup

None needed -- no new project, dependency, or build tooling
(`plan.md`'s Technical Context: no new dependency).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared notation-insertion UI both user stories build on.

**⚠️ CRITICAL**: Must complete before either user story.

- [ ] T001 [P] Add the notation character-set constant (precomposed
      fractions, superscript/subscript digit ranges, fraction-slash
      composition helper -- `data-model.md`) in
      `frontend/src/lib/notation-options.ts`
- [ ] T002 Implement the shared `NotationToolbar` component in
      `frontend/src/components/NotationToolbar.tsx`: renders buttons
      from `notation-options.ts`, inserts the selected glyph/sequence at
      the caller-supplied cursor position, and exposes an
      `isIncomplete` flag (true while a fraction/exponent/subscript
      construct has been started but not finished -- `research.md` §4,
      FR-007) via an `onIncompleteChange` callback (depends on T001)
- [ ] T003 [P] Unit tests for `NotationToolbar`'s insertion and
      incomplete-construct state machine (fraction with no denominator
      yet, exponent/subscript mode toggled with nothing typed) in
      `frontend/tests/unit/notation-toolbar.test.tsx` (depends on T002)

**Checkpoint**: `NotationToolbar` is usable and tested standalone;
either user story can now proceed.

---

## Phase 3: User Story 1 - Learner enters a notated answer (Priority: P1) 🎯 MVP

**Goal**: A learner can enter fractions, exponents, and subscripts in a
free-text or multi-step answer via the notation toolbar, displayed with
real notation as they type (spec.md FR-001, FR-002, FR-005, FR-006,
FR-007).

**Independent Test**: Answer a free-text question requiring a fraction,
an exponent, and a subscript using the toolbar; confirm each renders
with real notation and submits successfully.

### Implementation for User Story 1

- [ ] T004 [US1] Integrate `NotationToolbar` into
      `frontend/src/components/FreeTextAnswerInput.tsx`: render above
      the `<textarea>`, insert at cursor position, and extend the
      existing submit-disabled condition (`text.trim() === ""`) to also
      disable while `NotationToolbar`'s `isIncomplete` is true
- [ ] T005 [US1] Integrate `NotationToolbar` into
      `frontend/src/components/MultiStepAnswerInput.tsx`: one toolbar
      instance per step `<input>`, same cursor-insertion behavior, and
      extend `allStepsFilled` to also require every step's
      `isIncomplete` to be false
- [ ] T006 [P] [US1] Extend
      `frontend/tests/unit/free-text-rejection-states.test.tsx`:
      fraction/exponent/subscript insertion displays the real character
      in the textarea, Submit stays disabled while a construct is
      incomplete, and `answerQuestion` is called with the exact composed
      string on submit
- [ ] T007 [P] [US1] Extend
      `frontend/tests/unit/multi-step-question.test.tsx`: same
      insertion/incomplete-disables-submit/exact-string assertions,
      scoped to one step at a time
- [ ] T008 [US1] Run quickstart.md Scenarios 1, 2, and 4 (fraction
      entry grades correctly, exponent/subscript display while typing,
      incomplete notation blocks submission) against local dev servers

**Checkpoint**: User Story 1 is fully functional and independently
demoable -- this is the MVP.

---

## Phase 4: User Story 2 - Grading is unaffected by notation (Priority: P2)

**Goal**: Prove notation introduces zero grading regression -- a
notated answer grades exactly as its plain-text equivalent already does
(spec.md FR-004, FR-008, FR-009).

**Independent Test**: Submit the same correct answer twice, once with
notation and once as today's plain-text approximation; confirm both
grade correct.

### Implementation for User Story 2

- [ ] T009 [P] [US2] Add a regression test to
      `backend/tests/contract/test_question_api.py`: submit a notated
      free-text response (e.g. containing "½") to
      `POST /api/questions/{id}/answer` and assert it is accepted and
      forwarded to grading as ordinary text -- no shape/validation
      change from a plain-text submission (`research.md` §2, §5)
- [ ] T010 [P] [US2] Add regression assertions to
      `frontend/tests/unit/free-text-rejection-states.test.tsx` and
      `frontend/tests/unit/multi-step-question.test.tsx`: a
      plain-ASCII-only submission (no toolbar use) reaches
      `answerQuestion` byte-for-byte unchanged from before this feature
- [ ] T011 [US2] Run quickstart.md Scenarios 3 and 5 (zero grading
      regression on plain-text answers; multi-step per-step notation
      graded like any other step)

**Checkpoint**: Both user stories work independently; notation adds
capability without changing grading behavior.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T012 Run the full backend (`pytest`) and frontend (`vitest`)
      regression suites and confirm zero failures (SC-002) -- this run
      also implicitly covers FR-008 (historical answers untouched, no
      migration exists to break them) and FR-009 (audit log/Langfuse
      trace coverage for `answer_submitted` is exercised unchanged by
      the existing suite); no dedicated task exists for either since
      neither requires new code
- [ ] T013 [P] Run `backend/scripts/check_no_subject_conditionals.py`
      to confirm no subject-ID-keyed gating was introduced
      (Constitution Principle III, FR-005)
- [ ] T014 Run all 5 `quickstart.md` scenarios end-to-end as a final
      confirmation before opening the PR
- [ ] T015 [P] Manually confirm FR-003 and SC-004: generate one question
      per content subject (algebra-1, biology) whose rubric criteria
      include notation characters, and confirm question-generation's
      existing validation step accepts it with no new failure mode --
      no code change expected, this is a smoke check that the existing
      pipeline's free-form text handling already accommodates notation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies -- start immediately.
  BLOCKS both user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2. No dependency on US2.
- **User Story 2 (Phase 4)**: Depends on Phase 2. Independent of US1's
  UI work (T009/T010 can be written as soon as Phase 2 lands), but
  T011's quickstart run is most meaningful once US1 exists to produce a
  notated answer to test against.
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Parallel Opportunities

- T001 and T003 can each run alongside other same-phase work once their
  own single dependency (T002 for T003) is met.
- T006 and T007 are independent test files -- run in parallel.
- T009 and T010 are independent (backend vs. frontend) -- run in
  parallel.
- T013 and T015 have no dependency on T012's outcome or each other --
  all three can run in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2 (Foundational): shared `NotationToolbar`.
2. Complete Phase 3 (US1): notation entry in both answer-input
   components.
3. **STOP and VALIDATE**: quickstart.md Scenarios 1/2/4.
4. This alone is demoable -- a learner can enter and submit notated
   answers.

### Incremental Delivery

1. Foundational → US1 (MVP: notation entry works) → US2 (proves zero
   grading regression) → Polish (full regression + Constitution III
   check + full quickstart run).

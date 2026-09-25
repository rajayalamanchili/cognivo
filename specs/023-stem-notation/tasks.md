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

- [X] T001 [P] Add the notation character-set constant (precomposed
      fractions, superscript/subscript digit ranges, fraction-slash
      composition helper -- `data-model.md`) in
      `frontend/src/lib/notation-options.ts`
- [X] T002 Implement the shared `NotationToolbar` component in
      `frontend/src/components/NotationToolbar.tsx` (depends on T001).
      **Implementation-time simplification**: every button (precomposed
      fractions, exponent/subscript digits) inserts one already-complete
      character; the only multi-character composition (an arbitrary
      fraction) happens in a small self-contained numerator/denominator
      composer whose own Insert button is disabled until both fields are
      digits. Nothing incomplete can ever reach the caller's `onInsert`,
      so FR-007 is satisfied by construction -- no `isIncomplete` flag or
      cursor-position tracking needed (simpler than research.md §4's
      illustrative mode-toggle design; same requirement, less code).
- [X] T003 [P] Unit tests for `NotationToolbar`'s insertion buttons and
      the custom-fraction composer's disabled-until-complete Insert
      button in `frontend/tests/unit/notation-toolbar.test.tsx`
      (depends on T002) -- 6/6 passing

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

- [X] T004 [US1] Integrate `NotationToolbar` into
      `frontend/src/components/FreeTextAnswerInput.tsx`: renders above
      the `<textarea>`, inserts at the tracked cursor position via a new
      `textareaRef`. No submit-disabled change needed (see T002's
      simplification note) -- `tsc --noEmit` clean, existing
      `free-text-rejection-states.test.tsx` suite (7/7) still passes
      unchanged.
- [X] T005 [US1] Integrate `NotationToolbar` into
      `frontend/src/components/MultiStepAnswerInput.tsx`: one toolbar
      instance per step `<input>`, same cursor-insertion behavior via a
      per-step ref array. Added `data-testid="multi-step-step-{index}"`
      on each step's wrapper so tests can scope `within()` queries
      across multiple same-page toolbar instances. `tsc --noEmit`
      clean, existing `multi-step-question.test.tsx` suite (6/6) still
      passes unchanged.
- [X] T006 [P] [US1] Extend
      `frontend/tests/unit/free-text-rejection-states.test.tsx`: 4 new
      tests (fraction/exponent insertion displays the real character,
      exact-composed-string submit, plain-ASCII submission unaffected)
      -- 11/11 passing. **Bug found while writing these tests, fixed
      before committing**: the initial insertion implementation
      refocused the field via `requestAnimationFrame` after insert,
      which raced with fast subsequent typing elsewhere and silently
      stole keystrokes back into the wrong field. Fixed by dropping the
      post-insert refocus entirely (see `FreeTextAnswerInput.tsx`'s
      `insertNotation` comment) -- insertion position is still read
      synchronously at click time, just never force-restored afterward.
- [X] T007 [P] [US1] Extend
      `frontend/tests/unit/multi-step-question.test.tsx`: 2 new tests
      (notation inserted into one step doesn't affect another, scoped
      via `within()`; exact composed strings submitted per step) --
      8/8 passing. Same refocus-race bug found and fixed here too
      (`MultiStepAnswerInput.tsx`'s `insertNotation`).
- [X] T008 [US1] **Not verified in a live browser** -- this sandbox has
      neither `chromium-cli` nor a local Postgres/backend available, and
      no project skill exists yet for launching this app (see `run`
      skill's report). Substituted with the closest available
      verification: T003/T006/T007's Vitest+jsdom tests render these
      exact components in a real DOM and assert actual `value`
      attributes and `disabled` states (this is what caught the
      refocus-race bug above), plus `tsc --noEmit`. Scenario 1's
      grading-correct claim is covered by T009's backend contract test
      instead of a live manual run. Recommend a manual
      `npm run dev` + backend click-through before merging if a live
      visual check is wanted.

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

- [X] T009 [P] [US2] Added
      `backend/tests/integration/test_free_text_notation_answer.py`
      (not `tests/contract/test_question_api.py` as originally
      planned -- `test_question_api.py`'s `mocked_generation` fixture
      only produces `multiple_choice` questions; the existing free-text
      test infrastructure lives in `tests/integration/` with
      `free_text_helpers.py`, and `test_free_text_paraphrase_
      equivalence.py` is the exact existing pattern for "two answers,
      same mocked grading result, assert identical outcome" -- reused
      that pattern with a notated vs. plain-text pair instead of two
      paraphrases). 1/1 passing against the real test Postgres DB.
- [X] T010 [P] [US2] Regression coverage already lands from T006/T007:
      `free-text-rejection-states.test.tsx`'s new "plain-ASCII-only
      submission is unaffected" test asserts the exact pre-existing
      `answerQuestion("q1", "an answer", undefined, undefined)` call
      shape; `multi-step-question.test.tsx`'s original (unmodified)
      "renders one input per step... submits them as an ordered array"
      test continues to pass unchanged, proving the toolbar's presence
      doesn't alter a plain-text multi-step submission either.
- [X] T011 [US2] Ran quickstart.md Scenario 5 (multi-step per-step
      notation graded like any other step) via T007's new test
      (submits `["½", "x = 4"]`, asserts identical
      `answerQuestion` call/grading path as an all-plain-text
      submission). Scenario 3 (zero grading regression) deferred to
      T012's full-suite run, same as SC-002's own definition.

**Checkpoint**: Both user stories work independently; notation adds
capability without changing grading behavior.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T012 Full backend suite: **701/701 passing**, zero failures
      (`uv run pytest -q`, ~19.5 min against the real test Postgres DB).
      Full frontend suite: **137/137 passing** (`npx vitest run`). SC-002
      confirmed. This run also implicitly covers FR-008 (historical
      answers untouched, no migration exists to break them) and FR-009
      (audit log/Langfuse trace coverage for `answer_submitted` is
      exercised unchanged by the existing suite).
- [X] T013 [P] Ran `backend/scripts/check_no_subject_conditionals.py` --
      "OK: no subject-id-keyed conditionals found in backend/src for
      ['algebra-1', 'biology']"
- [X] T014 Final confirmation across all 5 `quickstart.md` scenarios:
      Scenario 1 (fraction grades correctly) -- T009's backend test.
      Scenario 2 (exponent/subscript display while typing) -- T006's
      frontend tests. Scenario 3 (zero grading regression) -- T012's
      full suite. Scenario 4 (incomplete notation blocks submission) --
      T003's composer-disabled-until-complete tests (satisfied by
      construction, see T002). Scenario 5 (multi-step per-step
      notation) -- T007/T011. **Not independently re-verified in a live
      browser** -- see T008's note; all 5 are covered by real-DOM
      (jsdom) or real-Postgres automated tests, not a live click-through.
- [X] T015 [P] Confirmed FR-003/SC-004 by code inspection rather than a
      live (costly) LLM generation call: `_validate_draft`
      (`assessment_gen/agent.py`) only checks `rubric_criteria` count
      and weight-sum for `FREE_TEXT`, never criterion content, and
      `RubricCriterion.description` is an unconstrained `str` (just
      `min_length=1`) -- no charset restriction exists to trip on
      notation. Added a cheap permanent regression check,
      `backend/tests/unit/test_notation_rubric_validation.py`, calling
      `_validate_draft` directly with a notated vs. plain-text criterion
      -- 1/1 passing, no LLM call, no DB write.

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

# Implementation Plan: Math and Science Notation for Free-Text Answers

**Branch**: `033-stem-notation` | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-stem-notation/spec.md`

## Summary

Let a learner enter fractions, exponents, and chemical-formula
subscripts in a free-text or multi-step answer, using a small notation
toolbar that inserts real Unicode characters into the existing plain-
text input -- instead of typing an ASCII approximation ("1/2", "x^2",
"H2O"). Research (see `research.md`) found this requires zero backend
or grading changes: free-text/multi-step grading is already an LLM
judgment against natural-language rubric criteria (Milestone 6/16), not
exact-string matching, so it already tolerates "1/2" and "½" as the
same idea; and because the output is plain Unicode text (not markup),
every existing surface that already renders that text renders it
correctly with no new rendering step. The entire change is a frontend
addition to `FreeTextAnswerInput`/`MultiStepAnswerInput`.

## Technical Context

**Language/Version**: TypeScript (frontend only -- no backend/Python
changes)

**Primary Dependencies**: None new. Reuses the existing Next.js/React
stack (`tech-stack.md`'s Frontend row); no new npm package.

**Storage**: N/A -- no schema change (`data-model.md`, `research.md` §5).

**Testing**: Vitest + React Testing Library (`tech-stack.md`'s Testing
row) -- new unit tests on the notation-toolbar component; no new
backend tests needed since no backend behavior changes.

**Target Platform**: Same as the rest of the frontend -- Vercel-deployed
Next.js, any modern browser.

**Project Type**: Web application (existing `backend/` + `frontend/`
structure) -- this feature touches `frontend/` only.

**Performance Goals**: N/A -- a client-side text-insertion UI has no
meaningful performance budget beyond normal component render cost.

**Constraints**: Must not add a new dependency (research.md §1 rejected
LaTeX/KaTeX and WYSIWYG math-editor libraries as disproportionate to
this scope); must not change the request/response shape of
`POST /api/questions/{id}/answer` or its practice/quiz-session
equivalents (`contracts/api.md`).

**Scale/Scope**: Two existing content subjects (algebra-1, biology);
three notation categories (fractions, exponents, subscripts); two
existing input components (`FreeTextAnswerInput`, `MultiStepAnswerInput`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **I. Personalization Is a Model, Not a Guess** -- N/A, no mastery-model
  change.
- **II. Generated Content Is Graded Against a Rubric, Never Vibes** --
  PASS. Grading is explicitly unchanged (research.md §2); the existing
  rubric-criteria LLM evaluation is untouched by this feature.
- **III. One Engine, Many Subjects** -- PASS. The notation toolbar is a
  shared component used identically regardless of `subject_id`; no
  subject-conditional gating (FR-005). `check_no_subject_conditionals.py`
  stays clean since no engine code branches on subject.
- **IV. Multi-Agent Boundaries Reflect Real Responsibility Boundaries**
  -- PASS. No new agent; this is a frontend input-widget addition,
  matching the precedent CLAUDE.md already documents for Milestone 5's
  in-quiz difficulty logic (new capability layered on existing
  responsibility, not a new agent boundary).
- **V. Every Personalization and Grading Decision Is Logged and
  Explainable** -- PASS. The audit log and Langfuse trace already
  capture `response_text`/`response_steps` verbatim; notation is
  carried through unchanged (FR-009).
- **VI. Agent Boundaries Match Deployment Boundaries** -- N/A, no A2A
  change.
- **VII. Spec Before Code, Milestone-Gated** -- satisfied by this
  spec/plan sequence; `/speckit-tasks` and `/speckit-analyze` follow
  before `/speckit-implement`.
- **VIII. No Real Learner Data Until Privacy/Retention Are Specified**
  -- N/A, no data-handling change.
- **IX. Deployable and Demoable From the Start** -- PASS, trivially: no
  new dependency, no new server-side execution path, nothing that
  interacts with Vercel's serverless constraints beyond what already
  exists.
- **X. Staged Release Discipline** -- standard: PR into `staging`,
  automated review gate, promotion PR to `main` once verified.

No violations. Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/023-stem-notation/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── api.md           # "no contract changes" record
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
└── (no changes -- see contracts/api.md, research.md §5)

frontend/
├── src/
│   ├── components/
│   │   ├── FreeTextAnswerInput.tsx      # gains notation toolbar
│   │   ├── MultiStepAnswerInput.tsx     # gains notation toolbar (per step)
│   │   └── NotationToolbar.tsx          # new: shared insertion UI + state machine
│   └── lib/
│       └── notation-options.ts          # new: character-set constant (data-model.md)
└── tests/
    └── unit/
        ├── notation-toolbar.test.tsx        # new
        ├── free-text-rejection-states.test.tsx  # extended
        └── multi-step-question.test.tsx         # extended
```

**Structure Decision**: Existing web-application layout
(`backend/` + `frontend/`, locked project-wide). This feature adds one
new frontend component (`NotationToolbar.tsx`) and one new constants
file (`notation-options.ts`), and extends the two existing answer-input
components to use them. No new backend module, no new directory beyond
what already exists.

## Complexity Tracking

*No entries -- Constitution Check has no violations to justify.*

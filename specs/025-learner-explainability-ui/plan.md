# Implementation Plan: Learner-Facing Explainability UI

**Branch**: `025-learner-explainability-ui` | **Date**: 2026-09-27 | **Spec**: `specs/025-learner-explainability-ui/spec.md`

**Input**: Feature specification from `specs/025-learner-explainability-ui/spec.md`

## Summary

Surface six already-computed-but-never-shown explanations to the learner: why a question was selected (`is_fallback`/decay), a decay-aware dashboard mastery bar, a per-criterion grading view extended into the flows that lack it today (quiz, timed quiz, placement, instructor-assigned attempts), a one-shot "refreshed" acknowledgment on a mastery-threshold crossing, a mastery-over-time sparkline, and a learner-facing rendering of the existing weak-area report. Every value displayed is read from data a prior milestone already computes and persists (Milestone 1's BKT model, Milestone 22's decay module, Milestone 6/16's grading rubric, Milestone 2's Recommendation Agent) -- this feature adds response fields and frontend rendering, never a second computation of any of them.

## Technical Context

**Language/Version**: Python 3.12 (backend, FastAPI/ADK), TypeScript 5 (frontend, Next.js 16 / React 19) -- both already locked in `tech-stack.md`, no change.

**Primary Dependencies**: FastAPI, SQLAlchemy, Next.js/React -- all already installed. **Zero new dependencies** (ladder step 5: nothing here needs a library that isn't already in the project).

**Storage**: PostgreSQL via Neon, existing models only. **Zero new tables, zero new columns, zero migration.** Every value this feature surfaces is either already persisted (`MasteryState.p_mastery`/`updated_at`, `AssessmentEvent` payloads, `NEXT_TOPIC_SELECTED`/`MASTERY_UPDATED` audit events) or computed on the fly from already-persisted data by an already-existing pure function (`effective_mastery_for_review`, `mastery_band_for`).

**Testing**: `pytest` (backend contract/unit/integration), `Vitest` + React Testing Library (frontend) -- existing patterns, no new tooling.

**Target Platform**: Vercel serverless (existing) -- every change is a per-request computation over already-open DB connections, no new background process, no new persistent state (Constitution Principle IX).

**Project Type**: Web application (existing `backend/` + `frontend/` split).

**Performance Goals**: No new performance target -- every addition is either an additive response field on an existing query (no new round trip) or one new indexed-by-existing-PK query (mastery-history), well within the existing per-request latency norms this project already operates under.

**Constraints**: Must not alter grading or decay math (Principle I/II); must not add a subject-id conditional anywhere (Principle III, `check_no_subject_conditionals.py`); must not introduce a new age-adaptation mechanism (reuses Milestone 17's grade-band-keyed pattern); the "refreshed" acknowledgment must require no new persisted tracking state (Clarifications, spec.md).

**Scale/Scope**: Same learner/topic/answer volumes as every existing route this feature extends -- no new scale dimension.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization is a model, not a guess | Effective mastery, mastery bands, and the "refreshed" crossing all reuse the existing BKT/decay pure functions (`bkt.py`, `decay.py`) called from the response-building layer -- no second implementation of any threshold or decay math. | PASS |
| II. Rubric-graded, never vibes | Grading detail surfaced (User Story 3) is the already-recorded rubric result (`criteria_met`/`criteria_missed`/`step_results`); no re-grading, no new rubric logic. | PASS |
| III. One engine, many subjects | No new subject-id-keyed conditional anywhere; `check_no_subject_conditionals.py` re-run in Polish (FR-017). | PASS |
| IV. Agent boundaries reflect real responsibility | No new agent, no new A2A service -- this is a presentation layer over existing agents' outputs, correctly staying inside the boundary rather than inventing one. | PASS |
| V. Logged and explainable | This feature *is* Principle V's payoff for the Sequencing Agent's pick and the mastery model's decay -- both already logged (M22's audit-trail fix) but never surfaced until now. No new audit event types needed; this reads what's already logged. | PASS |
| VI. A2A boundary discipline | N/A -- no A2A service touched. | N/A |
| VII. Spec before code | This plan follows an approved, clarified `spec.md`. | PASS |
| VIII. No real data until privacy is specified | No new data collection; reads only. | PASS |
| IX. Deployable/stateless | Every read is per-request against already-open DB connections; no in-memory state; the "refreshed" acknowledgment is derived once per grading response, never cached across requests. | PASS |
| X. Staged release discipline | Standard feature-branch -> `staging` -> `main` PR flow, unchanged. | PASS |

No violations. **Complexity Tracking is not needed for this feature.**

**Post-Phase-1 re-check**: `data-model.md` and `contracts/api-changes.md` confirm every change is an additive field on an existing response model, one new read-only query/endpoint, or one new derived boolean computed from two already-existing enum values (`prior_band`/`posterior_band`) -- no new table, no new agent, no new A2A call, no new subject-conditional. Constitution Check still PASSES with no changes to the table above.

## Project Structure

### Documentation (this feature)

```text
specs/025-learner-explainability-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-changes.md
└── tasks.md             # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── agents/sequencing/
│   │   ├── agent.py                  # NextTopicSelection already carries is_fallback/p_mastery/
│   │   │                             #   effective_p_mastery (M22) -- read, not modified
│   │   └── mastery_tool.py           # MasteryUpdateResult gains `prior_band` (one new field,
│   │                                 #   derived from already-available prior_observation.band)
│   ├── services/mastery/
│   │   ├── decay.py                  # effective_mastery_for_review -- read, not modified
│   │   └── mastery_history.py        # NEW: one query helper, mirrors weak_area.py's
│   │                                 #   `_build_evidence` pattern exactly
│   └── api/routes/
│       ├── questions.py              # NextQuestionOut/AnswerOut gain fields; build_next_question_out
│       │                             #   (already the single shared builder for 3 call sites) is the
│       │                             #   one place is_fallback/p_mastery/effective_p_mastery get added
│       ├── quiz.py                   # QuizQuestionOut gains the same 3 fields
│       ├── quiz_assignments.py       # its QuizQuestionOut(...) construction gains the same 3 values
│       ├── placement.py              # PlacementSubmitResponse gains per_question_results (reuses
│       │                             #   AnswerOut-shaped fields, computed in the existing grading loop)
│       ├── mastery.py                # MasteryTopicOut gains effective_p_mastery
│       └── mastery_history.py        # NEW: GET /api/learners/{id}/topics/{topic_id}/mastery-history
│
frontend/
├── src/
│   ├── components/
│   │   ├── AnswerResultView.tsx      # existing, reused as-is in quiz/placement flows (no changes
│   │   │                             #   needed to the component itself -- it already handles both
│   │   │                             #   free-text and multi-step shapes)
│   │   ├── SelectionReasonChip.tsx   # NEW: renders "why this question" from is_fallback/p_mastery/
│   │   │                             #   effective_p_mastery
│   │   ├── MasteryView.tsx           # extended: effective vs. peak mastery, last-practiced indicator
│   │   ├── RefreshedBanner.tsx       # NEW: renders when AnswerOut.refreshed is true
│   │   ├── MasteryTrend.tsx          # NEW: sparkline from the new mastery-history endpoint
│   │   └── WeakAreaSummary.tsx       # NEW: learner-facing rendering of existing getRecommendations()
│   ├── lib/
│   │   └── explainabilityCopy.ts     # NEW: grade-band-keyed copy tiers, mirrors pacing.ts's
│   │                                 #   getPacingProfile(unlockedGrade) pattern (FR-016)
│   ├── app/quiz/quiz-flow.tsx        # wire AnswerResultView + RefreshedBanner into the render path
│   │                                 #   that currently discards the answer result entirely
│   ├── app/practice/practice-flow.tsx # unchanged rendering, gains SelectionReasonChip/RefreshedBanner
│   └── components/LearnerAssignments.tsx # the separate, guardian-mediated instructor-assigned-attempt
│                                         #   UI (confirmed distinct from quiz-flow.tsx, not a thin
│                                         #   wrapper around it) -- gains the same three components as
│                                         #   quiz-flow.tsx; it independently discards the answer result
│                                         #   today and needs its own wiring (tasks.md C1 remediation)
```

**Structure Decision**: Existing `backend/` (FastAPI) + `frontend/` (Next.js) split, unchanged. This feature adds one new backend module (`mastery_history.py`, a query + a route) and extends five existing response models with additive fields; on the frontend it adds five small presentational components and one copy-tier helper, wiring them into two existing flow components. No new top-level directory, no new service boundary.

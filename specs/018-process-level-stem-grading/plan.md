# Implementation Plan: Process-Level STEM Grading

**Branch**: `025-process-level-stem-grading` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/018-process-level-stem-grading/spec.md`

## Summary

Extend Milestone 6's existing Grading Agent to grade a multi-step
submission step by step, localizing the first step that diverges from
an expected solution instead of returning one undifferentiated
"incorrect." No new agent, no new tables, no change to the mastery
model itself: a new `multi_step` `QuestionType` reuses the free-text
grading path end to end (content-artifact opt-in flag, generation-time
rubric, the existing A2A call to `grading-agent/`, the existing
aggregate-score-into-mastery mechanism), with the rubric, the request
payload, and the grading call all carrying an ordered list of steps
instead of one flat criteria list. Everything not opted in -- every
existing question type, every topic that hasn't authored step rubrics
-- is untouched.

## Technical Context

**Language/Version**: Python 3.12 (`backend/`, `grading-agent/`), TypeScript (`frontend/`) -- unchanged, no new runtime

**Primary Dependencies**: FastAPI, Google ADK, LiteLLM, `a2a-sdk`, SQLAlchemy/Alembic (`backend/`); Google ADK, LiteLLM, `a2a-sdk` (`grading-agent/`); Next.js/React (`frontend/`) -- all already locked in `tech-stack.md`; this feature adds zero new dependencies

**Storage**: PostgreSQL via Neon (existing). One new column (`topics.step_grading_enabled`), zero new tables -- the step rubric, the stepwise submission, and the step-level grading result all reuse existing JSON columns (`GeneratedQuestion.answer_key`, `AssessmentEvent.payload`), the same "extend the existing shape" precedent Milestone 6 (rubric criteria) and Milestone 11 (misconception classification) both already established

**Testing**: `pytest` (`backend/`, `grading-agent/`), `Vitest` (`frontend/`) -- unchanged frameworks, new test cases only

**Target Platform**: Vercel serverless (existing `backend` and `grading-agent` Services deployments) -- no new deployable, no `vercel.json` change

**Project Type**: Web application (existing `backend` + `grading-agent` + `frontend`), per `tech-stack.md`'s locked Vercel Services structure

**Performance Goals**: SC-006's 15s end-to-end budget for grading one full multi-step submission, measured the same way (full request path, not an isolated call) as Milestone 6's own SC-006

**Constraints**: FR-003a's flat-LLM-cost requirement (one batched A2A call per submission, never one call per step); must stay within `grading-agent/`'s existing `maxDuration: 30` Vercel budget with the same retry margin Milestone 6 already established (research.md §1); bypasses Milestone 13's semantic grading cache for `multi_step` submissions in v1 -- calls the Grading Agent directly rather than through `get_or_grade_answer()` (research.md §6)

**Scale/Scope**: Opt-in per topic (FR-001); initial scope is authoring step-enabled topics in `algebra-1` only (research.md §5) -- `biology` and every other unopted-in topic is provably unaffected (spec.md US3, SC-003)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | Mastery update mechanism (BKT) is completely unchanged; a stepwise submission produces the same single `graduated_score`/`correct` signal any other question type already produces (FR-007) | PASS |
| II. Generated Content Is Graded Against a Rubric, Never Vibes | Step rubric is generated alongside the question by the existing Assessment-Generation Agent, before display (FR-002); each step's correctness is judged against that step's own authored criteria, never a freeform read of the whole submission (FR-005) | PASS |
| III. One Engine, Many Subjects | Opt-in is a per-topic content-artifact field (`process_level_grading`), loaded into a plain nullable-default-false column -- zero subject-id-keyed conditionals in engine code (FR-001, FR-011) | PASS |
| IV. Multi-Agent Boundaries Reflect Real Responsibility | No new agent. Extends the Grading Agent's existing free-text-grading responsibility with a richer input/output shape; still the same one call, same evaluation criteria (rubric-grounded correctness), same failure mode (`grading_unavailable`) (FR-009) | PASS |
| V. Every Decision Is Logged and Explainable | `ANSWER_SUBMITTED`'s existing payload gains `step_results`/`first_diverging_step_index`, same append-only audit-log pattern as every prior milestone's payload extension (FR-008); Langfuse traces the extended A2A call like any other (unchanged instrumentation) | PASS |
| VI. Agent Boundaries Match Deployment Boundaries | No new A2A service -- reuses `grading-agent/`'s existing shared-secret auth, Vercel Deployment Protection bypass, and leaked-secret compensating guardrails unchanged. The larger multi-step request body is covered by the existing length-cap compensating control (research.md §2 confirms the cap's headroom) | PASS |
| VII. Spec Before Code | This plan follows an approved, clarified `spec.md`; `tasks.md` follows this plan | PASS (in progress) |
| VIII. No Real Learner Data | Unaffected -- synthetic content artifacts and synthetic learner profiles only, same as every milestone before Milestone 7's real accounts | PASS |
| IX. Deployable and Demoable From the Start | No new Vercel service, no `maxDuration` change; research.md §1 shows the existing 30s ceiling still holds worst-case | PASS |
| X. Staged Release Discipline | PR into `staging` per usual workflow; no direct-to-`main` path introduced | PASS |

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/018-process-level-stem-grading/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── api.md           # Phase 1 output -- extends specs/007-grading-agent/contracts/api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── enums.py                    # + QuestionType.MULTI_STEP
│   │   └── topic.py                    # + step_grading_enabled: bool
│   ├── agents/assessment_gen/
│   │   └── agent.py                    # + StepDraft/step rubric generation + validation (FR-002/FR-010)
│   ├── services/
│   │   ├── content_artifact/
│   │   │   └── validator.py            # + parse/validate optional per-topic `process_level_grading`
│   │   ├── mastery/
│   │   │   └── grading.py              # + response-shape check for multi_step (list[str]), FR-012 step-count check
│   │   └── grading_client/
│   │       └── client.py               # + grade_stepwise_answer(), extended GradingResult
│   └── api/
│       └── questions.py                # + multi_step branch of POST /answer (FR-003/FR-004/FR-006/FR-008/FR-012)
└── alembic/versions/
    └── <new>_add_topics_step_grading_enabled.py

grading-agent/
└── src/
    └── agent.py                        # + multi-step grading instruction/prompt, per-step criteria_results output

frontend/
└── src/
    └── components/
        └── (stepwise answer input + per-step result display, only rendered for question_type === "multi_step")
```

**Structure Decision**: Extends the existing web-application structure
(`backend/` + `grading-agent/` + `frontend/`) already locked in
`tech-stack.md`. No new top-level directory, no new service.

## Complexity Tracking

*No entries -- Constitution Check has no violations to justify.*

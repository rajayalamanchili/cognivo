# Implementation Plan: Grade-Banded Curriculum Scoping

**Branch**: `024-grade-banded-curriculum` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-grade-banded-curriculum/spec.md`

## Summary

Placement now also assigns each learner an explicit starting grade
(1-12) per subject, using the same deterministic-model discipline
Milestone 1 already holds per-topic mastery to. Grade is a new content-
artifact entity (`GradeBand`) grouping a subject's existing topics
(FR-001); the Sequencing Agent gates next-question selection so a
learner never sees a grade above their currently-unlocked one until
every topic in their current grade reaches the existing "mastered" band
(FR-004/FR-005); and placement gains a skip action so a learner isn't
forced to guess at a question above their currently-assessed level
(FR-006). All of this lands as new logic inside the existing Diagnostic
Agent, Sequencing Agent, and mastery-update tool -- no new agent
boundary, no new A2A service, no new UI framework. A content artifact
that declares no `GradeBand` rows is completely unaffected (FR-009);
`biology` stays ungraded and is this feature's own SC-005 regression
fixture.

## Technical Context

**Language/Version**: Python 3.12 (`backend/`, unchanged); TypeScript/
Next.js (`frontend/`, unchanged). No new language or runtime.

**Primary Dependencies**: None new. SQLAlchemy 2.0 + Alembic (schema/
migrations), FastAPI (API), Google ADK (`Diagnostic`/`Sequencing` local
sub-agents, unchanged agent framework) -- all already locked in
`tech-stack.md`.

**Storage**: PostgreSQL (Neon), via two new tables (`grade_bands`,
`grade_progress`) and two modified tables (`topics` gains
`grade`; `generated_questions` gains `grade` and
`placement_session_id`), plus three new `AssessmentEventType` enum
values. See `data-model.md`.

**Testing**: `pytest` (backend: new pure-function tests for
`determine_starting_grade`, `grade_entry_topics`, and the grade-aware
`rank_eligible_topics` filter, plus integration tests for the new skip
endpoint and the unlock audit trail); `Vitest` (frontend: placement
flow's skip button and grade label). Same frameworks Milestone 1 already
locked -- no new testing dependency.

**Target Platform**: Vercel serverless functions (`backend`,
`frontend`), unchanged from Milestone 1. The new skip endpoint's
replacement-question generation is one more call to the existing
Assessment-Generation Agent -- the same per-question LLM call placement
already makes today, not a new latency-sensitive path.

**Project Type**: Web application (existing `backend/` + `frontend/`).
No new service.

**Performance Goals**: None new. No Success Criterion in spec.md is
latency-based; the skip endpoint's one additional generation call stays
within the existing per-question generation budget.

**Constraints**:
- Grade-banding is all-or-nothing per subject content artifact
  (`research.md` Decision 1) -- a subject either grades every topic or
  none of them; no per-topic-optional mixing.
- `GradeProgress.unlocked_grade` is a monotonic high-water mark,
  never recomputed-down from live mastery state (Edge Cases,
  `data-model.md`).
- No new agent boundary or A2A service (Constitution Principle IV/VI) --
  reuses the existing local Diagnostic/Sequencing ADK sub-agents and the
  existing `apply_mastery_update` write path (`research.md` Decisions 7-8).
- `submit_placement`'s request/response shape does not change
  (`research.md` Decision 6) -- skip is additive, not a redesign of the
  existing batch placement flow.

**Scale/Scope**: Touches `backend/` (2 new models, 2 modified models, 1
new route, small changes to the Diagnostic Agent's topic-selection
query, the Sequencing Agent's eligibility filter, and the mastery-update
tool, plus content-artifact validator/loader changes and 2 migrations)
and `frontend/` (placement flow gains a skip button and grade label
display). `content/algebra-1/subject.yaml` is retrofitted with
`grade_bands` + per-topic `grade` (a `tasks.md` item -- otherwise this
feature has no subject to demo against); `content/biology/subject.yaml`
is deliberately left ungraded as the SC-005 fixture. No change to
`grading-agent/`, `tutor-agent/`, or any other independently-deployed
service.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | Starting-grade determination (`determine_starting_grade`) and the grade-unlock check are both pure, deterministic functions of stored mastery/answer state -- never an LLM impression. Directly satisfies SC-001's ten-repeated-runs determinism requirement as a unit test. | PASS |
| II. Generated Content Graded Against a Rubric | Unaffected -- grade gates *which* topic a question is generated for, never how a question is graded. Every placement/skip-replacement question still carries its own `answer_key`, generated the same way as today. | PASS |
| III. One Engine, Many Subjects | Grade bands are authored per subject in its own YAML (`GradeBand` rows, per-topic `grade`); no subject-id conditional anywhere in `backend/src`. `check_no_subject_conditionals.py` (SC-004 extensibility check, Milestone 1) must stay clean. | PASS (verify at implement time) |
| IV. Agent Boundaries Reflect Real Responsibility | No new agent. Grade-entry topic selection is new logic in the existing Diagnostic Agent's placement-topic-selection path; grade eligibility is a new filter in the existing Sequencing Agent's `rank_eligible_topics`; the unlock check lives in the existing `apply_mastery_update`. None of these is an independently-evaluable or independently-versioned responsibility distinct from what already exists -- matches Milestone 5's precedent (quiz difficulty as new logic on an existing agent, not a sixth agent), which spec.md's own Assumptions cite directly. | PASS |
| V. Every Decision Logged and Explainable | FR-010: `GRADE_ASSIGNED` (once, at placement) and `GRADE_UNLOCKED` (each unlock) are new `AssessmentEventType` values with enough payload to reconstruct the decision (`data-model.md`). `PLACEMENT_QUESTION_SKIPPED` additionally covers Acceptance Scenario 4 of User Story 1 (which answers, including skips, drove the placement). | PASS |
| VI. Agent Boundaries Match Deployment Boundaries | No new A2A service -- everything stays local to `backend`. | PASS |
| VII. Spec Before Code | This plan follows an approved, clarified `spec.md`; `/speckit-tasks` and `/speckit-analyze` still required before `/speckit-implement`. | PASS |
| VIII. No Real Learner Data Until Privacy Specified | No new data category -- extends the existing synthetic demo-learner model (Milestone 1) with one more per-subject value (`unlocked_grade`), same trust tier as `MasteryState`. | PASS |
| IX. Deployable and Demoable | New skip endpoint is a normal awaited FastAPI route within the existing serverless function; no new persistent process, no in-memory session state (grade progress is a DB row, not agent session state). | PASS |
| X. Staged Release Discipline | Enforced at PR time (staging -> main), not a plan-time gate. | N/A here |

No violations. Complexity Tracking is not needed.

**Post-Phase-1 re-check**: `research.md` and `data-model.md` confirm the
design stayed inside this table's assumptions -- no new table beyond
the two minimal, justified additions (`GradeBand`, `GradeProgress`),
no new agent, no new A2A service, no subject-id branching, and
`submit_placement` needed zero code changes (Decision 6). The gate still
passes.

## Project Structure

### Documentation (this feature)

```text
specs/017-grade-banded-curriculum/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── api.md            # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── content/
│   └── algebra-1/
│       └── subject.yaml              # MODIFIED: + grade_bands, per-topic grade
├── src/
│   ├── models/
│   │   ├── grade_band.py             # NEW: GradeBand(subject_id, grade)
│   │   ├── grade_progress.py # NEW: GradeProgress(learner_id, subject_id, unlocked_grade)
│   │   ├── topic.py                  # MODIFIED: + grade (nullable, FK -> grade_bands)
│   │   ├── generated_question.py     # MODIFIED: + grade, + placement_session_id
│   │   └── enums.py                  # MODIFIED: + GRADE_ASSIGNED, GRADE_UNLOCKED,
│   │                                  #   PLACEMENT_QUESTION_SKIPPED
│   ├── agents/
│   │   ├── diagnostic/
│   │   │   └── agent.py              # MODIFIED: + grade_entry_topics() pure selection helper
│   │   └── sequencing/
│   │       ├── agent.py              # MODIFIED: rank_eligible_topics() + unlocked_grade filter
│   │       └── mastery_tool.py       # MODIFIED: apply_mastery_update() + unlock check,
│   │                                  #   MasteryUpdateResult.grade_unlocked
│   ├── services/
│   │   ├── content_artifact/
│   │   │   ├── validator.py          # MODIFIED: grade_bands + per-topic grade validation
│   │   │   │                          #   (Decision 1's all-or-nothing rule)
│   │   │   └── loader.py             # MODIFIED: persist GradeBand rows + Topic.grade
│   │   └── placement/
│   │       └── starting_grade.py     # NEW: determine_starting_grade() pure function
│   │                                  #   (research.md Decisions 3/4)
│   └── api/
│       └── routes/
│           └── placement.py          # MODIFIED: start_placement grade-entry selection +
│                                      #   grade field; submit_placement gains the one-time
│                                      #   GRADE_ASSIGNED write + GradeProgress creation;
│                                      #   NEW: skip_placement_question route
├── alembic/
│   └── versions/
│       ├── <new>_grade_banded_curriculum_schema.py   # NEW migration
│       └── <new>_grade_event_types.py                # NEW migration
└── tests/
    ├── unit/
    │   ├── test_starting_grade.py     # NEW: determine_starting_grade determinism (SC-001)
    │   └── test_sequencing.py         # MODIFIED: grade-gated rank_eligible_topics cases
    └── integration/
        ├── test_placement.py          # MODIFIED: grade-labeled questions, GRADE_ASSIGNED event,
        │                               #   biology (ungraded) regression case (SC-005)
        └── test_placement_skip.py     # NEW: skip endpoint (FR-006/FR-007/FR-008, SC-004)

frontend/
└── src/
    └── app/
        └── placement/
            └── placement-flow.tsx     # MODIFIED: grade label per question, skip button
                                        #   calling the new skip endpoint
```

**Structure Decision**: Existing web-application layout (`backend/` +
`frontend/`) is unchanged. This feature adds two new backend model files
and one new pure-function module, modifies existing files across
models/agents/services/routes/content, and adds one frontend
modification -- no new top-level directory, service, or project.

## Complexity Tracking

*No Constitution Check violations -- this section is intentionally empty.*

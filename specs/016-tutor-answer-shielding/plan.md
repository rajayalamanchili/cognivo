# Implementation Plan: Tutor Agent Answer-Shielding

**Branch**: `023-tutor-answer-shielding` | **Date**: 2026-09-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-tutor-answer-shielding/spec.md`

## Summary

When a learner asks the Tutor Agent something that would reveal the
final answer to a question they currently have open and unanswered
(practice, quiz -- learner-initiated or instructor-assigned -- or
placement), the system withholds the direct answer and responds with a
hint instead. The determination ("is this open, and does this tutor
question ask for its answer") is made in `backend` -- the sole data
owner (tech-stack.md) -- using a new, local, in-process cheap-model
classification step that mirrors `grading_cache/equivalence.py`'s
already-established pattern (Milestone 13), not a new agent or A2A
service. When shielding applies, `backend` withholds the open
question's `answer_key` from the request it sends to `tutor-agent/`
entirely, and `tutor-agent/`'s existing instruction gains a hint-only
mode -- so a false-positive shield still relies on the model simply not
having the answer to give away, not only on it following an
instruction not to.

## Technical Context

**Language/Version**: Python 3.12 (`backend/` and `tutor-agent/`, both
already on this version -- no change).

**Primary Dependencies**: `google-adk` (`LlmAgent`/`LiteLlm`/`Runner`,
already a dependency, used the same way `grading_cache/equivalence.py`
and `grading_client/moderation.py` already use it), `a2a-sdk` (existing
Tutor Agent client, `services/tutor_agent_client/client.py`),
SQLAlchemy + Alembic (existing `backend` ORM/migration stack). No new
dependency is introduced.

**Storage**: PostgreSQL (Neon), via the existing `tutor_exchanges`,
`generated_questions`, and `assessment_events` tables. One migration
adds two nullable columns to `tutor_exchanges` (`shielded`,
`shielded_question_id`) -- no new table.

**Testing**: `pytest` in both `backend/` and `tutor-agent/`, matching
each project's existing unit/integration split (see Project Structure).

**Target Platform**: Vercel serverless functions (`backend`,
`tutor-agent/`), per Constitution Principle IX -- unchanged from
Milestone 9; the new classification call is a normal awaited call
inside the existing `prepare_message` request lifecycle, not a new
long-running process.

**Project Type**: Web application (existing `backend/` +
`frontend/` + independently-deployed `tutor-agent/`/`grading-agent/`
services) -- no new service added by this feature.

**Performance Goals**: None (Clarifications, 2026-09-04). This feature
introduces no latency success criterion; Milestone 9's existing 3s p95
time-to-first-token target (SC-001, already unmet in production at
4.03s) is neither extended to cover the new classification step nor
used as a ceiling for it.

**Constraints**:
- The open question's `answer_key` MUST NOT be included in any payload
  sent to the externally-deployed `tutor-agent/` service when shielding
  applies (mirrors the semantic-caching precedent of never forwarding
  the sensitive raw value across a boundary that doesn't need it,
  spec 015 FR-009) -- this is a structural guarantee, not only an
  instruction to the model.
- The shielding determination MUST default to shielding (not to
  answering directly) whenever it cannot reach a confident result
  (FR-010) -- the classification call's own failure/timeout/malformed-
  response path must be treated as "shield," mirroring FR-016's
  existing "fail toward the safe interpretation" pattern for the
  citation step.
- No new agent boundary or A2A service (Constitution Principle IV/VI)
  -- the determination step is local and in-process, reusing the
  already-justified `grading_cache/equivalence.py` shape rather than
  inventing a second one.

**Scale/Scope**: Touches `backend/` (new classification module, one
migration, `tutor/session.py` and `tutor_agent_client/client.py`
changes) and `tutor-agent/` (instruction gains a hint-only mode,
`TUTOR_INSTRUCTION_VERSION` bump). No change to `frontend/`,
`grading-agent/`, or any other agent's scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | Shielding never touches mastery state, sequencing, or grading (FR-009) -- it only changes what the Tutor Agent is willing to say. | PASS |
| II. Generated Content Graded Against a Rubric | Unaffected -- no change to question generation or grading. | PASS |
| III. One Engine, Many Subjects | The shielding classifier operates generically on question text/stem; no subject-id branching. `check_no_subject_conditionals.py` must stay clean. | PASS (verify at implement time) |
| IV. Agent Boundaries Reflect Real Responsibility | No new agent. The classification step reuses the existing local, in-process cheap-model-classification shape (`grading_cache/equivalence.py`) rather than a new boundary -- there is no independent-versioning/evaluation need distinct from what a prompt-version bump already covers. | PASS |
| V. Every Decision Logged and Explainable | FR-007/SC-003: `tutor_exchanges.shielded`/`shielded_question_id` (mirrors the existing `grounded`/`retrieved_passage_ids` columns) plus the existing `TUTOR_EXCHANGE_COMPLETED` audit payload gain the same fields. The classification call gets its own explicit `traced_request(...)` wrapper at its call site in `prepare_message` (research.md's tracing note, `/speckit-analyze` finding I1) -- it is a real LLM call and must not be placed in the same unwrapped position the (non-LLM) delegation-context lookup already occupies. | PASS |
| VI. Agent Boundaries Match Deployment Boundaries | No new A2A service; the determination stays local to `backend`, avoiding an unjustified remote boundary. | PASS |
| VII. Spec Before Code | This plan follows an approved `spec.md`; `/speckit-tasks` and `/speckit-analyze` still required before `/speckit-implement`. | PASS |
| VIII. No Real Learner Data Until Privacy Specified | No new data category introduced; reuses existing guardian-mediated/demo-learner access model (Milestone 9). | PASS |
| IX. Deployable and Demoable | New classification call is a normal awaited call within existing serverless functions; no new persistent process or in-memory session state. | PASS |
| X. Staged Release Discipline | Enforced at PR time (staging -> main), not a plan-time gate. | N/A here |

No violations. Complexity Tracking is not needed.

**Post-Phase-1 re-check**: `research.md`, `data-model.md`, and
`contracts/api.md` confirm the design stayed inside this table's
assumptions -- no new table, no new agent, no new A2A service, no
subject-id branching, and the classifier call gets its own explicit
trace wrapper rather than reusing another call's. No new violations;
the gate still passes.

**Second re-check (post-`/speckit-analyze`)**: findings C1 (FR-006's
"session/attempt ended" branch), C2 (SC-001/002/004 need an actual
eval fixture, not just spot-check tests), and I1 (the tracing wrapper
above) were all remediated in `research.md`/`data-model.md`/`tasks.md`
directly -- none required a Constitution Check change; the gate still
passes.

## Project Structure

### Documentation (this feature)

```text
specs/016-tutor-answer-shielding/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # Phase 1 output (delta to spec 012's internal A2A contract)
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

The Polish-phase eval fixture (`/speckit-analyze` finding C2) lives at
`backend/evaluation/shielding_ground_truth.jsonl`, not under this
directory -- corrected during implementation to match this codebase's
actual convention for a script-driven eval (`misconception_ground_
truth.jsonl`/`grading_ground_truth.jsonl` sit there too), not Milestone
9's separate manual-checklist-markdown convention under `specs/.../eval/`.

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── tutor_exchange.py            # MODIFIED: + shielded, shielded_question_id columns
│   ├── services/
│   │   ├── tutor/
│   │   │   ├── session.py                # MODIFIED: call shielding check (own traced_request())
│   │   │   │                              #   in prepare_message, thread result into request
│   │   │   │                              #   payload + persistence
│   │   │   └── shielding.py              # NEW: open-question lookup (FR-001/FR-002/FR-006,
│   │   │                                  #   reads GeneratedQuestion + AssessmentEvent +
│   │   │                                  #   QuizAssignmentTarget/QuizAssignment.cancelled_at) +
│   │   │                                  #   direct-or-paraphrase classification (FR-004/FR-010)
│   │   └── tutor_agent_client/
│   │       └── client.py                 # MODIFIED: request_payload gains a "shielding" key;
│   │                                      #   answer_key is never included when shielding applies
│   └── alembic/
│       └── versions/
│           └── <new>_tutor_exchange_shielding_columns.py   # NEW migration
├── scripts/
│   └── check_shielding_eval.py           # NEW: SC-001/SC-002/SC-004 rate measurement
│                                          #   (Polish, /speckit-analyze finding C2)
└── tests/
    ├── unit/
    │   └── test_tutor_shielding.py       # NEW: shielding.py's lookup + classification logic,
    │                                      #   including the FR-010 fail-toward-shielding and
    │                                      #   FR-006 cancelled-assignment paths
    └── integration/
        ├── test_tutor_messages.py         # MODIFIED: shielded-exchange scenarios, including
        │                                   #   the assignment-cancellation lift case
        └── test_tutor_exchange_inspection.py  # MODIFIED: SC-003 (shielded exchange inspectable)

tutor-agent/
├── src/
│   └── agent.py                          # MODIFIED: instruction gains hint-only shielding mode;
│                                          #   TUTOR_INSTRUCTION_VERSION "v1" -> "v2"
└── tests/
    └── test_agent_instruction.py         # MODIFIED: hint-only-mode instruction coverage
```

**Structure Decision**: Existing web-application layout (`backend/` +
`frontend/` + independently-deployed `tutor-agent/`/`grading-agent/`)
is unchanged. This feature adds one new module
(`backend/src/services/tutor/shielding.py`) and modifies four existing
files across the two projects the feature actually touches; no new
top-level directory, service, or project.

## Complexity Tracking

*No Constitution Check violations -- this section is intentionally empty.*

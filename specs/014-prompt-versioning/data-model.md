# Phase 1 Data Model: Prompt Versioning and Regression Testing

**Feature**: `022-prompt-versioning` | **Date**: 2026-09-01

This feature's two conceptual entities (spec's Key Entities section) are
not new database tables -- per research.md §1, a Prompt Artifact is a
code-level construct (module-level constants), and a Regression Gate is
a CI-level binding (a workflow step). This document makes both concrete
against the actual codebase, plus the one real schema change (§3).

## 1. Prompt Artifact (code-level, not a table)

Concrete shape: a module-level string constant (or a template constant
+ builder function, for prompts that interpolate per-call parameters),
paired with a module-level string constant whose name contains
`VERSION`, both defined in the same file.

| Agent | Content location | Version constant (this milestone) |
|---|---|---|
| Assessment-Generation | `backend/src/agents/assessment_gen/agent.py` (`_INSTRUCTION_TEMPLATE` + `_build_instruction()`) | `GENERATION_PROMPT_VERSION = "v1"` |
| Grading Agent (scoring) | `grading-agent/src/prompt_defense.py` (`_GRADING_INSTRUCTION_TEMPLATE` + `build_instruction()`) | `GRADING_LOGIC_VERSION = "v2"` (already exists, in `grading-agent/src/agent.py`) |
| Tutor Agent (conversational) | `tutor-agent/src/agent.py` (`_INSTRUCTION`) | `TUTOR_INSTRUCTION_VERSION = "v1"` |
| Backend moderation guardrail (shared: grading pre-check + tutor session check) | `backend/src/services/grading_client/moderation.py` (`_INSTRUCTION`) | `MODERATION_INSTRUCTION_VERSION = "v1"` |
| Grading Agent in-agent moderation guardrail | `grading-agent/src/guardrails.py` (`_MODERATION_INSTRUCTION`) | `GRADING_GUARDRAIL_MODERATION_VERSION = "v1"` |
| Tutor Agent in-agent moderation guardrail | `tutor-agent/src/guardrails.py` (`_MODERATION_INSTRUCTION`) | `TUTOR_GUARDRAIL_MODERATION_VERSION = "v1"` |
| Misconception Classifier baseline-comparison prompt (eval-only) | `backend/src/services/misconception/baseline.py` (`_INSTRUCTION_TEMPLATE` + `_build_instruction()`) | `MISCONCEPTION_BASELINE_PROMPT_VERSION = "v1"` |

**Validation rule** (enforced by `check_prompt_versioning.py`, not by any
runtime code): every `LlmAgent(instruction=...)` call site's argument
must resolve to a module-level symbol, and that symbol's module must
define at least one `VERSION`-named module-level constant. No new
Python type/class is introduced -- existing plain-string constants
satisfy this shape already (research.md §1's rejected-abstraction note).

## 2. Regression Gate (CI-level, not a table)

| Agent | Existing quality-eval suite | CI workflow step (this milestone) |
|---|---|---|
| Assessment-Generation | `backend/scripts/batch_eval_questions.py` (internal-consistency re-validation, spec 001 SC-003) | `backend-tests.yml` gains a new blocking step: `batch_eval_questions.py --fresh` (research.md §5) |
| Grading Agent | `backend/scripts/check_grading_agent_eval.py` (ground-truth accuracy/consistency, spec 007 FR-008) | Already wired in `grading-agent-tests.yml`; no change needed (research.md §6) |
| Tutor Agent, all three moderation guardrails, Misconception baseline prompt | None exist | Versioned (via §1) but explicitly not regression-gated this milestone (spec Assumptions) |

## 3. `GeneratedQuestion` schema change

**Table**: `generated_questions` (`backend/src/models/generated_question.py`)

**New column**: `generation_prompt_version: str`, non-nullable, no
server-side default.

**Migration**: standard Alembic revision adding the column. No backfill
of existing rows (research.md §7 -- historical rows were never versioned
and SC-003 only requires versioning from this milestone forward, not
retroactive attribution).

**Call sites requiring an update** (both already construct a
`GeneratedQuestion`; both gain one new keyword argument sourced from
`GENERATION_PROMPT_VERSION`):
- `backend/src/api/routes/questions.py:100`
- `backend/src/api/routes/placement.py:79`

**Relationship to existing versioned fields**: same pattern as
`grading_logic_version` (an existing field on the grading response,
persisted in the `answer_submitted` audit-event payload) and
`classifier_version` (an existing field in `misconception_classified`
event metadata) -- this is the third and last prompt-driven decision
Constitution Principle V's explainability guarantee required covering
(spec's User Story 3), and the only one of the three that lives on the
entity's own row rather than a separate audit-event payload, since a
`GeneratedQuestion` row already *is* the durable record of its own
generation (research.md §7).

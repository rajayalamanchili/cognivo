# Implementation Plan: Free-Text Grading via a Real A2A Service

**Branch**: `007-grading-agent` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-grading-agent/spec.md`

## Summary

Adds a free-text (short-answer) question type, graded by a new Grading
Agent that -- unlike every prior agent in this project -- is a genuine
remote A2A service in its own Vercel deployment, not a local ADK
sub-agent. The main backend calls it as an A2A client, treats its
response as untrusted output to be validated against the question's own
rubric before acceptance (never as instructions to follow), and feeds
the resulting graduated score -- thresholded to a binary
correct/incorrect signal -- into the exact same, unmodified mastery-
update pipeline every other question type already uses. Four new,
mutually distinct pre-grading guardrails (moderation, prompt-injection
defense, a length cap, and a per-learner rate limit) sit in front of
the Grading Agent call, all enforced by the backend rather than
duplicated inside the agent. No new database tables: two existing
Postgres enums gain one value each, and the existing `answer_key` JSON
column and `AssessmentEvent` audit stream absorb everything else,
following this project's established minimal-schema-footprint pattern.

## Technical Context

**Language/Version**: Python 3.12 for both the existing backend
(unchanged) and the new Grading Agent (new deployment unit, same
language/version -- no cross-language justification exists for this
feature, per `tech-stack.md`'s "Explicitly not yet decided" note that
language is a plan-time decision). TypeScript/Next.js frontend,
unchanged runtime.

**Primary Dependencies**: Backend -- adds `a2a-sdk` as an A2A *client*
dependency (research.md §1); all other backend dependencies (FastAPI,
SQLAlchemy 2.0, Pydantic 2, Alembic, Google ADK, LiteLLM) already
locked, unchanged. New Grading Agent project -- Google ADK, LiteLLM
(Claude Sonnet default, matching the existing Assessment-Generation
Agent's provider choice), `a2a-sdk[http-server]` (the `http-server`
extra required for `sse_starlette`, discovered at implementation time --
research.md §1), and ADK's own `google.adk.a2a.utils.agent_to_a2a
.to_a2a()` utility to expose the agent as an A2A server. Frontend --
Next.js/React/Tailwind, unchanged; no new dependency (a free-text
answer is a plain `<textarea>`).

**Storage**: PostgreSQL via Neon, same database as every other
milestone -- no new tables (research.md §9). Two enum-value additions
(`question_type` gains `free_text`; `assessment_event_type` gains
`free_text_submission_rejected`), via the same `ALTER TYPE ... ADD
VALUE` Alembic technique spec 002 already established. The Grading
Agent itself has no database connection at all (research.md §3).

**Testing**: `pytest` (backend, `backend/tests/{unit,integration}/`)
for rubric-shape validation, the score-to-binary threshold, the
moderation/length/rate-limit guardrails, the retry/idempotency
behavior (mocking the A2A client boundary), and the ground-truth eval
gate itself (FR-008, `backend/evaluation/`, extending Milestone 3's
harness precedent). A separate, minimal `pytest` suite for the Grading
Agent project (its own `grading-agent/tests/`), since it is now an
independently deployable, independently testable unit -- this is the
concrete evidence Constitution Principle VI's justification requires,
not merely claimed. `Vitest` + React Testing Library for the new
free-text input component and its four new rejection states.
`Playwright` (E2E) extended to cover a full free-text question
answer-and-grade round trip against the live dev deployment, per
`tech-stack.md`.

**Target Platform**: The existing Vercel Services project
(`backend/`+`frontend/`) continues to serve everything except the
Grading Agent. The Grading Agent deploys as a **new, separate Vercel
project** (`grading-agent/`), independently, per research.md §2 --
this is the one genuinely new deployment unit this project has
introduced since Milestone 1.

**Project Type**: Web service monorepo, now with three deployable
units instead of two (`backend/`, `frontend/`, `grading-agent/`).

**Performance Goals**: SC-006 -- 95% of free-text submissions graded
within 5 seconds including retries. Bounded by: one moderation
classification call (Haiku, ~0.5-1s per research.md §5) + one grading
call (Sonnet, same cost profile as existing question-generation calls)
+ up to 2 retries on failure (research.md §7) -- comfortably within
budget for the non-retry path; the retry path is the one SC-006
explicitly measures against.

**Constraints**: Stateless per request (Constitution Principle IX) --
the Grading Agent holds no state at all (research.md §3); the rate
limit (FR-016) is enforced via a DB query, never in-memory (research.md
§6), for the same reason.

**Scale/Scope**: Single learner per submission, same solo-learner scope
as every prior milestone. Two seeded subjects (`algebra-1`, `biology`)
each get at least one topic opted into `free_text` via
`preferred_question_types` (research.md §10), proving Constitution
Principle III's subject-agnostic claim continues to hold.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1
design below.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | The mastery model (BKT) is untouched -- free-text grading's graduated score is thresholded to the same binary observation shape every other question type already produces (FR-005, research.md §7) before it ever reaches the Sequencing Agent's mastery tool. | PASS |
| II. Generated content graded against a rubric | The core purpose of this milestone: every free-text question carries a rubric generated alongside it (FR-002, reusing Milestone 1's `answer_key`-generation guarantee, research.md §9); grading evaluates against that rubric, never freeform judgment (FR-004) and never the answer's own embedded claims (FR-014). | PASS |
| III. One engine, many subjects | Free-text question-type selection is entirely content-artifact-owned via `preferred_question_types` (research.md §10) -- zero new subject-id-keyed conditionals in engine code, covered by the existing `check_no_subject_conditionals.py` scan. Both seeded subjects opt in. | PASS |
| IV. Agent boundaries reflect real responsibility | The Grading Agent's responsibility (rubric-based scoring) is genuinely distinct from Assessment-Generation's (question + rubric authoring) -- different failure modes (a bad grade vs. a bad question), different evaluation criteria (the ground-truth eval set, FR-008, vs. Milestone 1's draft-validation checks). Three of the four guardrails (moderation, length, rate limit) are platform-wide abuse-prevention concerns owned by the backend, not duplicated per-agent. The fourth, prompt-injection defense, is intrinsic to the Grading Agent's own scoring responsibility -- defending its own prompt from the untrusted input it evaluates is part of scoring correctly, not a duplicated cross-cutting concern -- so it correctly lives inside `grading-agent/` itself (`prompt_defense.py`), not the backend. | PASS |
| V. Logged and explainable | Every grading outcome (FR-007) and every guardrail rejection (FR-012/015/016) is a distinct, queryable `AssessmentEvent` (data-model.md) -- "why was this marked wrong" and "why was this rejected" both have real, traceable answers. Every Grading Agent call is wrapped in the existing `traced_request()` Langfuse instrumentation, same as every other agent call. | PASS |
| VI. A2A justified by concrete need | This is the concrete case Constitution Principle VI and `tech-stack.md` both name in advance: independent versioning/evaluation of grading logic (FR-008's merge gate) without redeploying the rest of the platform. SC-005 and this feature's own separate `grading-agent/tests/` suite exist specifically to prove the boundary earns its keep, not merely claim it does (research.md §2). | PASS |
| VII. Spec before code | This plan follows the approved, twice-clarified spec.md (Clarifications sessions 2026-08-19). | PASS |
| VIII. No real learner data | Reads/writes only `DemoLearnerProfile`-scoped rows, same as every prior milestone. The moderation/rate-limit guardrails exist regardless of real-vs-synthetic data, but no real learner data is introduced by this milestone. | PASS |
| IX. Deployable and demoable | The Grading Agent's statelessness (research.md §3) and the rate limiter's DB-backed design (research.md §6) are both direct, deliberate consequences of this principle, not afterthoughts. Three deployable units now exist; all three deploy to Vercel. | PASS |
| X. Staged release discipline | Feature branch `007-grading-agent` -> PR into `staging`, per existing workflow. The new `grading-agent/` Vercel project needs its own branch-deployment mapping (`staging`/`main`) set up alongside the existing two, per `tech-stack.md`'s Branching table -- a one-time infrastructure step, not a per-PR concern. | PASS (process, not a design gate) |

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/007-grading-agent/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── api.md            # Phase 1 output
└── tasks.md               # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── enums.py                  # + QuestionType.FREE_TEXT,
│   │                                    # AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED
│   ├── agents/
│   │   └── assessment_gen/
│   │       └── agent.py              # + free_text branch: rubric-shape draft field,
│   │                                    # draft_to_answer_key() free-text case (research.md §9)
│   ├── services/
│   │   └── grading_client/           # NEW -- A2A client-side orchestration (distinct
│   │       ├── __init__.py           # from services/mastery/grading.py, which stays
│   │       ├── moderation.py         # NEW: pre-grading moderation check (research.md §5)
│   │       ├── guardrails.py         # NEW: length cap (FR-015) + rate limit (FR-016,
│   │       │                          # research.md §6) -- pure precondition checks
│   │       ├── client.py             # NEW: A2A call + bounded retry (research.md §4/§7)
│   │       │                          # + response validation against rubric (FR-014)
│   │       └── moderation_review.py  # NEW: FR-013's per-learner flag-count query
│   └── api/routes/
│       └── questions.py              # answer_question() becomes async; free-text branch
│                                        # calls services/grading_client/, converges into
│                                        # the same downstream apply_mastery_update()/
│                                        # record_event() calls every other type uses
├── alembic/versions/
│   └── <new>_free_text_question_type.py  # NEW: two ALTER TYPE ADD VALUE statements
└── content/
    ├── algebra-1/subject.yaml        # + free_text in >=1 topic's preferred_question_types
    └── biology/subject.yaml          # + free_text in >=1 topic's preferred_question_types

grading-agent/                        # NEW -- separate Vercel project (research.md §2)
├── src/
│   ├── agent.py                      # NEW: the Grading Agent itself (ADK LlmAgent,
│   │                                    # LiteLlm/Claude Sonnet) + to_a2a() wrapping
│   │                                    # (research.md §1); GRADING_LOGIC_VERSION
│   │                                    # constant (research.md §8)
│   └── prompt_defense.py             # NEW: "treat answer as data, not instructions"
│                                        # prompt construction (FR-014)
├── tests/                            # NEW: this project's own independent test suite
│   └── test_agent.py                 # (Constitution Principle VI's evidence requirement)
├── pyproject.toml                    # NEW
└── vercel.json                       # NEW: this project's own deployment config

frontend/
├── src/
│   ├── components/
│   │   └── FreeTextAnswerInput.tsx   # NEW: textarea input, reused wherever
│   │                                    # QuestionCard already renders MC/numeric inputs
│   └── services/
│       └── api.ts                    # answerQuestion() extended to accept a string
│                                        # response; four new rejection-state shapes
└── tests/
    └── (unit/e2e test files added at /speckit-tasks time)
```

**Structure Decision**: Extends the existing `backend/` + `frontend/`
monorepo with a **third** top-level project, `grading-agent/` -- the
first new deployable unit since Milestone 1, deliberately separate
(research.md §2) rather than folded into `backend/`'s existing
Services setup. `backend/` follows its established
`services/<name>/` (orchestration) + `api/routes/<name>.py` (thin HTTP
layer) split, adding `services/grading_client/` alongside the existing
`services/mastery/`, `services/quiz/`, `services/recommendation/`
precedent. `grading-agent/` is deliberately minimal -- one agent module,
one prompt-defense module, its own tests -- since it has exactly one
responsibility (Constitution Principle IV).

## Post-Design Constitution Check

*Re-checked after Phase 1 (data-model.md, contracts/api.md,
quickstart.md).* Phase 1 confirmed two decisions beyond the Phase 0
table above: (1) "Grading Decision" and "Moderation Flag"
(spec.md Key Entities) map onto the existing `AssessmentEvent` stream
with richer payloads rather than new tables (research.md §9,
data-model.md) -- no new schema surface beyond two enum values; (2)
`answer_question()`'s free-text branch reuses the identical
`apply_mastery_update()` + `record_event()` calls the MC/numeric path
already uses (contracts/api.md), so FR-006's "not a second,
inconsistent source of truth" guarantee is structural, not just
tested-for. Neither revisits a `tech-stack.md`-locked choice; both are
applications of patterns Milestone 1/2/5 already established. All ten
principles re-checked above still PASS; no new gate failure.

## Complexity Tracking

*No Constitution Check violations -- table intentionally omitted.*

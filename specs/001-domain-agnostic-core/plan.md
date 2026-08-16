# Implementation Plan: Domain-Agnostic Core -- Content Schema, Structured Assessment, Single-Learner Mastery Model

**Branch**: `001-domain-agnostic-core` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-domain-agnostic-core/spec.md`

## Summary

Build the domain-agnostic engine that everything else in Cognivo depends
on: a subject content-artifact schema (topic graph, prerequisites, skill
definitions, three difficulty bands) validated at load time; a
Diagnostic Agent that places a new learner with one question per
entry-level topic; a Sequencing Agent whose Bayesian Knowledge Tracing
mastery model (research.md §1) deterministically scores each topic into
a three-band mastery state (struggling / developing / mastered) and
picks the next topic; an Assessment-Generation Agent that generates a
structured question plus its own validated answer key via an LLM called
through ADK's LiteLLM wrapper (Claude Sonnet default, research.md §2);
deterministic structured-answer grading; a pedagogical audit log plus
Langfuse tracing on every agent call; and two subjects (Algebra I,
Biology) proving zero engine-file changes are needed per subject. All
agents are local ADK sub-agents (no A2A boundary yet -- no concrete need
exists per Constitution Principle VI), state is Postgres-backed
throughout (Vercel-compatible), and the whole flow is live-deployed and
demoable via a seeded, explicitly-flagged demo learner profile.

## Technical Context

**Language/Version**: Python 3.11 (backend/agents), TypeScript (Next.js
frontend) -- per `tech-stack.md`.

**Primary Dependencies**: Google ADK (agent framework, `LiteLlm` model
wrapper per research.md §2), FastAPI (Vercel Python Function/ASGI),
`openinference.instrumentation.google_adk` + Langfuse (tracing), Next.js
(frontend). LLM calls default to Anthropic Claude Sonnet via LiteLLM,
provider swappable by config (research.md §2).

**Storage**: PostgreSQL (Neon, serverless-compatible) -- mastery state,
ADK session state, content-artifact metadata, `GeneratedQuestion`,
`AssessmentEvent` audit log. See `data-model.md`.

**Testing**: `pytest` (backend), `Vitest` + React Testing Library
(frontend components), `Playwright` (SC-007 deployment smoke test) --
research.md §4.

**Target Platform**: Vercel (stateless, ephemeral Python + Next.js
Functions/Services) -- per Constitution Principle IX / `tech-stack.md`.

**Project Type**: Web application (Next.js frontend + FastAPI backend,
deployed together as Vercel Services).

**Performance Goals**: Not independently specified by spec.md beyond
fitting within a single Vercel Function's execution window per request
(`tech-stack.md`'s deployment-target section); no additional
domain-specific throughput/latency target exists for this milestone.

**Constraints**: Stateless/ephemeral serverless execution (no in-memory
session state -- FR-013); every agent invocation must complete and flush
its Langfuse trace within one function's execution window (FR-014); all
mastery/grading decisions deterministic and explainable (Constitution
Principles I, V).

**Scale/Scope**: One synthetic demo learner profile, two subjects
(Algebra I, Biology), placement-through-first-follow-up-question flow.
No multi-tenancy, no real learner data (Constitution Principle VIII).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | Mastery state computed by BKT (research.md §1), called as an ADK tool by the Sequencing Agent -- never an LLM impression. Deterministic given identical inputs (SC-001). | PASS |
| II. Generated Content Graded Against a Rubric | Every `GeneratedQuestion` carries `answer_key` generated together with the question, validated before `shown_at` (FR-007, data-model.md). Free-text/rubric grading itself is out of scope this milestone (structured-only). | PASS |
| III. One Engine, Many Subjects | `Subject`/`Topic`/`PrerequisiteEdge` hold all subject-specific data; SC-004's automated conditional scan is a hard gate (roadmap.md M1 DoD). Two subjects (Algebra I, Biology) built now specifically to prove this. | PASS |
| IV. Agent Boundaries Reflect Real Responsibility | Diagnostic, Sequencing, Assessment-Generation are three separate ADK sub-agents, each with a distinct responsibility and failure mode (placement selection vs. mastery/sequencing vs. generation+validation) -- not a decorative split. | PASS |
| V. Every Decision Logged and Explainable | `AssessmentEvent` (data-model.md) answers "why" pedagogically; Langfuse trace (FR-014) answers "what happened in the model call" technically. Both required, both implemented. | PASS |
| VI. A2A Justified by Concrete Need | All three agents stay local ADK sub-agents this milestone -- no A2A boundary introduced. Matches spec.md's Assumptions; no concrete independent-versioning/evaluation need stated for any of the three yet. | PASS |
| VII. Spec Before Code, Milestone-Gated | This plan.md follows an approved, clarified spec.md; `/speckit-tasks` and `/speckit-analyze` still required before `/speckit-implement`. | PASS (workflow, not a design gate) |
| VIII. No Real Learner Data | Only `DemoLearnerProfile` rows exist, `is_demo` non-nullable and explicit at creation (data-model.md). No real-account path built. | PASS |
| IX. Deployable and Demoable | FastAPI + Next.js as Vercel Services; all state Postgres-backed, no in-memory session assumption; SC-007's Playwright-driven smoke test validates the live deployment itself, not just the API. | PASS |
| X. Staged Release Discipline | Feature branch `001-domain-agnostic-core` → PR into `staging` → separate promotion PR into `main`; `anthropics/claude-code-action@v1` gate already established (roadmap.md M1 DoD, repo's existing CI history). No design decision here conflicts with this. | PASS (repo-level, already in place) |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-domain-agnostic-core/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── api.md           # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── agents/
│   │   ├── diagnostic/          # Diagnostic Agent (ADK sub-agent)
│   │   ├── sequencing/          # Sequencing Agent (ADK sub-agent) + BKT tool
│   │   └── assessment_gen/      # Assessment-Generation Agent (ADK sub-agent)
│   ├── models/                  # Subject, Topic, PrerequisiteEdge, MasteryState,
│   │                             GeneratedQuestion, AssessmentEvent, DemoLearnerProfile
│   ├── services/
│   │   ├── mastery/             # BKT implementation (research.md §1) -- pure, tested in isolation
│   │   ├── content_artifact/    # Load-time schema + cycle/reachability validation (FR-002)
│   │   ├── dedup/                # Near-duplicate check (research.md §3)
│   │   └── audit_log/           # AssessmentEvent writer
│   ├── api/                     # FastAPI routes per contracts/api.md
│   └── observability/           # Langfuse/OpenInference instrumentation, span flush
├── content/
│   ├── algebra-1/                # Content artifact: topic graph, skills, difficulty bands
│   └── biology/                  # Content artifact: topic graph, skills, difficulty bands
├── scripts/
│   ├── seed_demo_learner.py
│   └── load_content_artifact.py
└── tests/
    ├── contract/                 # Validates api.md request/response shapes
    ├── integration/              # Full placement-through-first-question flow (quickstart.md)
    └── unit/                     # BKT determinism (SC-001), dedup, validation logic

frontend/
├── src/
│   ├── components/                # Question display, mastery view, demo badge
│   ├── pages/ (or app/)            # Placement flow, next-question flow
│   └── services/                   # API client per contracts/api.md
└── tests/
    ├── unit/                       # Vitest + RTL component tests
    └── e2e/                        # Playwright, incl. SC-007 deployment smoke test
```

**Structure Decision**: Web application (Option 2) -- FastAPI backend +
Next.js frontend, deployed together as Vercel Services per
`tech-stack.md`. Engine code (`backend/src/agents`, `models`, `services`,
`api`) contains no subject-specific logic; both subjects live entirely
under `backend/content/<subject>/`, matching Constitution Principle III
and FR-001/FR-012's requirement that engine source stay free of
subject-id-keyed conditionals (enforced by SC-004's automated scan).

## Complexity Tracking

No Constitution Check violations -- this section is intentionally empty.

## Post-Design Constitution Check

*Re-evaluated after Phase 1 (data-model.md, contracts/api.md, quickstart.md).*

No new violations introduced by the Phase 1 design. Specifically:
- `data-model.md`'s `MasteryState` and `AssessmentEvent` entities keep
  Principles I and V's determinism/explainability guarantees concrete
  (not just asserted) at the schema level.
- `contracts/api.md` never exposes an `answer_key` before grading and
  never accepts a grading decision from the client, keeping Principle II
  intact end to end.
- No endpoint or entity introduces subject-specific fields or logic
  outside `backend/content/<subject>/` (Principle III).
- No new agent or A2A boundary was introduced during design (Principle
  VI unchanged from the initial Constitution Check).

Gate: **PASS**.

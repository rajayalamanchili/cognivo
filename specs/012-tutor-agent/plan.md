# Implementation Plan: Tutor Agent -- Conversational Delegation, Vector-Grounded Retrieval, and Streaming Responses

**Branch**: `012-tutor-agent` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-tutor-agent/spec.md`

## Summary

A learner (guardian-mediated, or the seeded demo learner) asks the
Tutor Agent a plain-English question and gets a streamed,
`pgvector`-grounded answer; when the question depends on the learner's
own performance, the answer reflects their real mastery/weak-area
state rather than a guess. The `backend` orchestrates each turn
(retrieval, gathering Sequencing/Recommendation context in-process)
and calls a new standalone `tutor-agent/` A2A service -- built the same
way as `grading-agent/` -- with everything it needs bundled into one
request; `tutor-agent/` streams back a grounded answer and holds no
state or database credentials of its own. Every exchange is logged
(pedagogical audit event + Langfuse trace) so a specific answer's
grounding and delegation can be reconstructed after the fact. A
session is get-or-create per learner/subject, only one exchange may be
in flight per session at a time, and the conversational endpoint is
rate-limited per learner -- all three enforced at the data layer, not
just in application code (FR-013/FR-014/FR-015). Which passages an
answer actually grounded in is communicated via a dedicated terminal
tool call (`cite_passages`), structurally separate from the streamed
answer text -- not parsed back out of it (FR-016, research.md §9),
replacing the marker+JSON-in-text protocol PRs #42/#44 found unreliable
after shipping.

## Technical Context

**Language/Version**: Python 3.12 (`backend`, new `tutor-agent/`); TypeScript/Next.js (frontend chat UI), matching every existing project in this repo.

**Primary Dependencies**: `google-adk`, `litellm` (Anthropic + Voyage), `a2a-sdk`, `langfuse`, `openinference-instrumentation-google-adk` (all already used by `grading-agent/`, reused as-is for `tutor-agent/`); `pgvector` (new: PyPI package for the SQLAlchemy `Vector` column type, added to `backend`'s dependencies only -- `tutor-agent/` never touches Postgres, research.md §2).

**Storage**: PostgreSQL/Neon (existing), gaining the `pgvector` extension plus three new tables (`content_passage_embeddings`, `tutoring_sessions`, `tutor_exchanges`) -- see data-model.md. `tutor-agent/` itself is stateless (no storage).

**Testing**: `pytest` (`backend`, `tutor-agent/`, matching both existing projects' `pytest.ini_options`); Vitest (frontend unit) + Playwright (frontend E2E), matching `frontend/`'s existing setup.

**Target Platform**: Vercel serverless -- three deployable units: the existing `backend`+`frontend` Services project, and a new, separately-deployed `tutor-agent/` Vercel project (mirrors `grading-agent/` exactly, including its `to_a2a()` host/protocol/port derivation from `VERCEL_BRANCH_URL`/`VERCEL_URL`, research.md §7).

**Project Type**: Web application (existing `backend`/`frontend`) plus a new standalone agent service (`tutor-agent/`), matching the precedent `grading-agent/` already set for this repo's project layout.

**Performance Goals**: First streamed token within 3s p95 (SC-001, locked via `/speckit-clarify` 2026-08-23 -- still provisional in the sense that no real measurement exists yet, same caveat Grading Agent's SC-006 carried before `spec 007`'s live data; research.md §6).

**Constraints**: Vercel `maxDuration: 60` on both the backend's tutor endpoint and the `tutor-agent/` function (research.md §6); A2A inbound auth via a distinct shared secret (`TUTOR_AGENT_SHARED_SECRET`) per Constitution Principle VI; retrieval scope limited to this platform's own content-artifact material, never third-party sources (FR-012, already locked in `tech-stack.md`); at most one active Tutoring Session per learner per subject (FR-014) and at most one in-flight exchange per session (FR-015), both enforced at the data layer (research.md §8); Tutor Agent conversational endpoint rate-limited per learner, reusing the Grading Agent's existing DB-query-based window pattern (FR-013).

**Scale/Scope**: Demo/classroom scale (not high-concurrency) -- consistent with every prior milestone; no new scale requirement introduced.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Status | Notes |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | PASS | FR-006 requires the Tutor Agent's performance-dependent answers to come from the existing deterministic mastery model + Recommendation Agent output, never an LLM's own re-derivation from chat context. |
| II. Generated Content Graded Against a Rubric | PASS (N/A-adjacent) | This milestone introduces no new grading logic; where grading context is needed (research.md §3), the backend reuses the existing Grading Agent path unchanged. |
| III. One Engine, Many Subjects | PASS | Retrieval/embedding generation operates generically over the content-artifact schema (research.md §5) -- no subject-id-keyed conditional; verified by the existing `check_no_subject_conditionals.py` gate at implementation time. |
| IV. Multi-Agent Boundaries Reflect Real Responsibility | PASS | Tutor Agent owns a distinct responsibility (grounded conversational generation + streaming) with its own success criterion (SC-002's grounding rate) genuinely different from Sequencing/Recommendation/Grading's. Delegation is inspectable per User Story 3/FR-007, not a black box. |
| V. Every Decision Logged and Explainable | PASS | FR-007 (pedagogical audit event, reusing `assessment_events`) + FR-008 (Langfuse trace) satisfy both halves explicitly. FR-016 (research.md §9) makes the grounding signal itself more reliably explainable: a schema-validated tool call, not a heuristically-parsed text footer. |
| VI. Agent Boundaries Match Deployment Boundaries | PASS | `tutor-agent/` as a new A2A service is justified by a concrete need (independent evaluability of retrieval-grounding quality, SC-002; matches the Grading Agent precedent). Sequencing/Recommendation explicitly stay local (FR-009) since neither has a stated independent-versioning/evaluation need -- avoids the "A2A by default" anti-pattern. Inbound auth (shared secret) + compensating guardrails required for `tutor-agent/`, same as Grading Agent. |
| VII. Spec Before Code, Milestone-Gated | PASS | This plan follows an approved `spec.md`; Milestone 8's Success Criteria were met before this milestone began (`roadmap.md`). |
| VIII. No Real Learner Data Until Privacy/Retention Specified | PASS | Access model (FR-001) reuses Milestone 8's already-approved guardian-mediated pattern plus the demo learner -- no new real-data surface or account type introduced. `/speckit-analyze` (2026-08-23) verified this claim rather than leaving it asserted: `specs/009-privacy-retention/data-classification.md` has been extended to cover `tutoring_sessions`/`tutor_exchanges` (finding C1). That same check surfaced a **pre-existing, not-Milestone-9-introduced** gap -- FR-004/FR-005's actual deletion-execution pathway was never implemented in Milestone 7, only the `DeletionRequest` model -- now tracked in `roadmap.md`'s new "Known gap" section rather than silently inherited. |
| IX. Deployable and Demoable From the Start | PASS | `tutor-agent/` is stateless (research.md §2), session/exchange state is DB-backed (data-model.md), streaming uses Vercel/Next.js's native support -- no in-memory state assumed anywhere. |
| X. Staged Release Discipline | PASS (process) | Work happens on `012-tutor-agent`, branched from `origin/staging`; PR targets `staging`, subject to the automated review gate. |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/012-tutor-agent/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── api.md            # Phase 1 output (/speckit-plan command)
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── content_passage_embedding.py   # NEW
│   │   ├── tutoring_session.py            # NEW
│   │   └── tutor_exchange.py              # NEW
│   ├── services/
│   │   ├── content_artifact/
│   │   │   └── loader.py                  # EXTENDED: embed passages on load (research.md §5)
│   │   ├── retrieval/
│   │   │   └── passage_search.py          # NEW: pgvector similarity query
│   │   ├── tutor/
│   │   │   ├── session.py                 # NEW: orchestrates a turn (research.md §2), enforces FR-014/FR-015
│   │   │   └── rate_limit.py              # NEW: FR-013, mirrors grading_client/guardrails.py's check_rate_limit
│   │   └── tutor_agent_client/
│   │       └── client.py                  # NEW: A2A client, mirrors services/grading_client/client.py; reads TextPart deltas + the cite_passages DataPart directly (FR-016) -- no text-footer parsing
│   └── api/routes/
│       └── tutor.py                       # NEW: POST /api/tutor/sessions, .../messages, GET .../exchanges/{id}
├── alembic/versions/
│   └── <hash>_tutor_agent.py              # NEW: pgvector extension, 3 new tables (tutor_exchanges incl. failed_at), new AssessmentEventType value
└── tests/
    ├── unit/                              # passage_search, tutor/session orchestration
    └── integration/                       # tutor.py routes, content_artifact loader extension

tutor-agent/                                # NEW, mirrors grading-agent/ layout exactly
├── pyproject.toml
├── vercel.json
├── src/
│   ├── agent.py                            # ADK agent + to_a2a(), _to_a2a_kwargs (mirrors grading-agent); cite_passages FunctionTool, terminal via skip_summarization (FR-016, research.md §9)
│   ├── guardrails.py                       # length cap + moderation compensating control
│   └── tracing.py
└── tests/

frontend/
├── src/
│   ├── app/tutor/                          # NEW: tutoring chat page
│   ├── components/
│   │   └── TutorChat.tsx                   # NEW: streaming chat UI
│   └── services/api.ts                     # EXTENDED: streaming fetch helper for /api/tutor/...
└── tests/
    ├── unit/tutor-chat.test.tsx            # NEW
    └── e2e/tutor-round-trip.spec.ts         # NEW
```

**Structure Decision**: Extends the existing `backend`/`frontend` web-application structure with a third top-level project, `tutor-agent/`, matching the precedent `grading-agent/` already established for this repo (a standalone A2A service gets its own Vercel-deployable project, not a subdirectory of `backend`). No existing directory is restructured.

## Complexity Tracking

*No Constitution Check violations -- this section is not needed.*

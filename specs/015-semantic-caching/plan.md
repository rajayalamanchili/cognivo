# Implementation Plan: Semantic Caching

**Branch**: `023-semantic-caching` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-semantic-caching/spec.md`

## Summary

Two new Postgres (Neon) tables sit in front of the two highest-volume model calls: `question_generation_cache` (a rotating 5-variant, 24-hour-fresh pool per `(subject_id, topic_id, difficulty, content_version, generation_prompt_version)`) in front of `assessment_gen.agent.generate_question`, and `grading_response_cache` (`pgvector`-matched on a reused `voyage-3` answer embedding, scoped by a content-hash `question_signature` + `grading_logic_version`) in front of `grading_client.client.grade_free_text_answer`. Both cache-aware wrappers return the exact same value shape (`GeneratedQuestionDraft`, `GradingResult`) the existing functions already return, so every downstream line — `GeneratedQuestion` persistence, `record_event`, mastery updates — runs completely unchanged on a hit or a miss (this is what makes SC-003's hit/miss indistinguishability structural rather than a discipline to remember). The only new work at each call site is: (1) a `served_from_cache` / `cache_miss_reason` key added to the payload already passed to the existing `record_event` call (no new event type, no new table), and (2) an explicit Langfuse span/generation on a hit, since `GoogleADKInstrumentor` only auto-instruments real ADK `Runner` calls and a cache hit makes none. No new dependency, no new service, no new HTTP route — everything lands inside `backend/src`.

## Technical Context

**Language/Version**: Python 3.12 (existing `backend/` `uv`-managed environment; no new language)

**Primary Dependencies**: None new. Reuses `pgvector` (already installed, `backend/src/models/content_passage_embedding.py`), `litellm`'s `voyage/voyage-3` embedding call (already used by `services/misconception/embed.py`), and the existing `langfuse>=4.14.4` client (`observability/tracing.py`) via its manual span/generation API instead of only the auto-instrumented path.

**Storage**: PostgreSQL via Neon (existing, locked in `tech-stack.md`). Two new tables, added via a normal Alembic migration chained off `be66baa35493` (research.md §1 resolves `tech-stack.md`'s "Semantic-caching layer... Milestone 13 decision" in favor of in-database Postgres over Redis/Upstash).

**Testing**: `pytest` (existing). New unit tests for the cache-lookup/eviction/similarity logic under `backend/tests/unit/caching/`, plus integration tests exercising both cache-aware wrappers end to end against a real DB, mirroring the existing `tests/integration/evaluation/` and `tests/integration/test_generated_question_prompt_version.py` conventions. A new synthetic load-test script (`backend/scripts/cache_load_test.py`) is the actual verification mechanism for SC-001/SC-002 (a measured per-type hit rate and a measured model-call-volume reduction) -- neither is demonstrable by unit/integration tests alone, since both require replaying volume, not a single request pair.

**Target Platform**: Vercel serverless (existing `backend/src/api/main.py` Function) for the runtime cache read/write path -- no change to the deployed execution model. No new Vercel Cron route (research.md §5: pool-cap eviction is enforced at insert time, not via a scheduled sweep).

**Project Type**: Existing multi-service monorepo (`backend/` + `grading-agent/` + `tutor-agent/` + `frontend/`) -- this feature touches `backend/` only. Neither `grading-agent/` nor `tutor-agent/` needs any code change: caching decides whether backend calls out to Grading's A2A endpoint at all, not how Grading itself behaves once called.

**Performance Goals**: A cache lookup (one indexed row query for question-gen; one `pgvector` cosine-distance query scoped by an indexed `question_signature` + version for grading) must add negligible latency relative to the model call it may replace (typically 1-3s) -- no numeric SLA beyond "the lookup itself is not the bottleneck," matching the spec's cost-focused Success Criteria (SC-001/SC-002) over a latency-focused one.

**Constraints**: Fail-open on any cache-storage error (FR-008) -- wrapped in a single reusable try/except per cache type, never surfaced to the learner. Hit/miss output must be byte-identical (FR-007/SC-003) -- enforced structurally by both wrappers returning the same dataclass/BaseModel the un-cached functions already return, with all downstream persistence/event code left untouched. Grading-cache matching must never cross questions (FR-004) or leak another learner's raw answer text (FR-009). Every cache hit gets its own full audit-log entry and Langfuse trace (FR-013, Clarifications 2026-09-02) -- not a lighter-weight record.

**Scale/Scope**: Question-gen pool size is bounded by the content catalog (finite topics × difficulty bands × current content/prompt versions) × 5 -- not open-ended. Grading-cache row count has no cap in this milestone (spec's Assumptions accept this explicitly, since only a `grading_logic_version` bump invalidates it) -- deferred, not overlooked; noted as a follow-up in research.md §6.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | Sequencing's mastery model and topic/difficulty selection are untouched -- caching only changes where the *content* of an already-selected (topic, difficulty) request's question comes from | PASS |
| II. Generated content graded against a rubric | Cached questions were validated (FR-007, `_validate_draft`) before ever entering the pool; cached grades were computed against the question's real rubric before caching -- caching never bypasses either guarantee, it only replays a prior validated/graded result | PASS |
| III. One engine, many subjects | Cache keys (`subject_id`, `topic_id`, `difficulty`, versions) are read from the request/DB, never hardcoded; `check_no_subject_conditionals.py` (research.md §7) must pass unchanged against the new cache modules | PASS |
| IV. Agent boundaries reflect real responsibility | No agent added, removed, or merged. Caching sits in `backend/src` as a lookup layer in front of existing agent/A2A calls, not as a new agent | PASS |
| V. Every decision logged and explainable | Directly reinforced: FR-013 requires every cache hit to carry its own full audit-log entry and Langfuse trace, exactly as a fresh call would -- data-model.md §3 and research.md §4 spell out how | PASS (reinforces) |
| VI. Agent boundaries match deployment boundaries | No new A2A service. A cache hit means the *existing* Grading Agent A2A call is skipped for that request -- Grading's own inbound-auth requirement is unaffected since nothing new calls it | PASS |
| VII. Spec before code | `spec.md` approved via `/speckit-clarify` (2026-09-02, 2 questions resolved, zero markers remaining) before this `plan.md` | PASS |
| VIII. No real learner data until privacy specified | Grading-cache rows store a question signature, an answer *embedding* (not raw text), and a grade -- never the learner's raw answer text or identity (FR-009); question-gen cache rows store no learner data at all | PASS |
| IX. Deployable and demoable from the start | Both new tables are read/written per-request from the existing stateless Vercel Function, no in-memory cache/session state assumed; no new persistent process | PASS |
| X. Staged release discipline | Implemented via a normal feature-branch PR into `staging`, same CI gates apply | PASS |

No violations. Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/015-semantic-caching/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md  # Already produced by /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature introduces no new or changed HTTP API surface (research.md §8). Every cache lookup/write happens inside existing request paths (`POST /api/questions/next`-style generation, `POST /api/questions/{id}/answer`-style grading) whose contracts are already fully specified by specs 001/005/007. User Story 3's hit-rate visibility ships as a maintainer-run script (`backend/scripts/cache_hit_rate_report.py`), not a new endpoint -- consistent with this project's existing script-based observability precedent (`batch_eval_questions.py`, `check_*.py`), and avoiding a new API surface for a maintainer-only concern.

### Source Code (repository root)

Existing multi-service monorepo, unchanged in shape. This feature only adds/edits files inside `backend/`:

```text
backend/
├── src/
│   ├── models/
│   │   ├── question_generation_cache.py    # NEW: pool table (data-model.md §1)
│   │   └── grading_response_cache.py       # NEW: pgvector-matched table (data-model.md §2)
│   ├── services/
│   │   ├── question_cache/
│   │   │   └── cache.py                    # NEW: get_or_generate_question() (research.md §2)
│   │   ├── grading_cache/
│   │   │   └── cache.py                    # NEW: get_or_grade_answer() (research.md §3)
│   │   └── misconception/embed.py          # reused as-is for the grading-answer embedding
│   ├── agents/sequencing/agent.py          # generate_question(...) call replaced with get_or_generate_question(...)
│   ├── services/quiz/session.py            # same replacement in generate_quiz_question()
│   ├── api/routes/questions.py             # grade_free_text_answer(...) call replaced with get_or_grade_answer(...); answer_payload gains served_from_cache/cache_miss_reason
│   ├── observability/tracing.py            # + record_cache_hit_trace() (research.md §4)
│   └── db.py                               # no change; existing Session/engine reused
├── alembic/versions/                       # NEW: one migration, two tables, chained off be66baa35493
├── scripts/
│   ├── cache_hit_rate_report.py            # NEW: US3 hit-rate script, reads AssessmentEvent payloads
│   └── cache_load_test.py                  # NEW: synthetic load test, the actual SC-001/SC-002 verification mechanism
└── tests/
    ├── unit/caching/
    │   ├── test_question_cache.py          # pool selection, eviction, TTL-as-miss
    │   └── test_grading_cache.py           # signature scoping, similarity threshold, fail-open
    └── integration/
        └── test_semantic_caching.py        # end-to-end hit/miss parity (SC-003), version-invalidation (SC-004)
```

**Structure Decision**: No new project, service, or route. Every change lands inside the existing `backend/` tree's `models/`, `services/`, `agents/`, `api/routes/`, `observability/`, `scripts/`, `alembic/`, and `tests/` directories -- consistent with this being a lookup layer in front of two already-complete agents, not a new architectural component. `grading-agent/` and `tutor-agent/` are untouched.

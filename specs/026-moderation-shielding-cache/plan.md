# Implementation Plan: Moderation & Shielding Classification Caching

**Branch**: `036-moderation-shielding-cache` | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-moderation-shielding-cache/spec.md`

## Summary

Two new Postgres tables sit in front of the two remaining high-call-volume, non-cached guardrail checks: `moderation_cache` (exact-signature match on normalized submitted text + `MODERATION_INSTRUCTION_VERSION`) in front of `grading_client.moderation.check_moderation`, and `shielding_classification_cache` (exact-signature match on a normalized (open-question-stem, tutor-message) pair + `SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION`) in front of `tutor.shielding.classify_match`. Unlike spec 015's grading cache, both use plain hashed-text exact matching, not `pgvector`/embeddings -- these are safety- and answer-leakage-relevant booleans with no equivalence-check safety net to make approximate matching safe (spec.md FR-003). Both cache-aware wrappers are injected at the same seam the existing modules already expose for testability (`shielding.py`'s own `match_fn` parameter; a new equivalent binding for `check_moderation`) so neither guardrail module's internals change at all. `tutor_exchanges` gains two small integer columns (`shielding_checks_total`, `shielding_checks_from_cache`) since `determine_shielding` performs up to 10 independent checks per exchange -- too many for a single per-exchange boolean to represent, unlike moderation's naturally 1-to-1 shape which reuses spec 015's existing `AssessmentEvent`-payload-flag pattern directly. No new dependency, no new service, no new HTTP route -- everything lands inside `backend/src`.

## Technical Context

**Language/Version**: Python 3.12 (existing `backend/` `uv`-managed environment; no new language)

**Primary Dependencies**: None new. `hashlib` (stdlib, already used by `cache_common/signature.py`) is the only new usage; reuses the existing `langfuse>=4.14.4` client (`observability/tracing.py::record_cache_hit_trace`, already generic across `cache_type`) and SQLAlchemy/Alembic already in place.

**Storage**: PostgreSQL via Neon (existing, locked in `tech-stack.md`). Two new tables plus two new columns on `tutor_exchanges`, added via a normal Alembic migration chained off the current head `824e2c5a0678` (research.md §1/§6). No `pgvector` column needed (research.md §1) -- simpler than spec 015's grading cache.

**Testing**: `pytest` (existing). New unit tests under `backend/tests/unit/caching/` (`test_moderation_cache.py`, `test_shielding_cache.py`), alongside the existing `test_question_cache.py`/`test_grading_cache.py`. New integration test `backend/tests/integration/test_guardrail_caching.py` (hit/miss parity, version-invalidation). A new script, `backend/scripts/guardrail_cache_load_test.py`, is the actual verification mechanism for SC-001/SC-002, mirroring spec 015's `cache_load_test.py` shape but without its embedding-specific fakes (research.md §7).

**Target Platform**: Vercel serverless (existing `backend/src/api/main.py` Function) -- no change to the deployed execution model, no new Cron route.

**Project Type**: Existing multi-service monorepo (`backend/` + `grading-agent/` + `tutor-agent/` + `frontend/`) -- this feature touches `backend/` only. Neither `grading-agent/` nor `tutor-agent/` needs any code change: both guardrails being cached already run entirely inside `backend/`.

**Performance Goals**: A cache lookup (one indexed exact-match row query per cache type) must add negligible latency relative to the model call it may replace -- no numeric SLA beyond "the lookup itself is not the bottleneck," matching the spec's cost-focused Success Criteria (SC-001/SC-002) over a latency-focused one. Exact-match lookups are cheaper than spec 015's `pgvector` cosine-distance queries.

**Constraints**: Fail-open on any cache-storage error (FR-006), preserving each guardrail's own existing fail-safe (moderation's fail-closed-on-no-response; shielding's default-to-shielded, spec 016 FR-010) if the *underlying* model call itself then fails -- caching only ever removes a redundant call, never changes what happens when a real call is actually needed and fails. Hit/miss output must be identical (FR-007) -- enforced structurally by both wrappers returning the exact same `bool` the un-cached functions already return. Neither cache stores raw submitted/tutor-message text (FR-008) -- only a non-reversible signature. Shielding-cache matching must never cross open questions (FR-004).

**Scale/Scope**: Both cache tables have no row-count cap or TTL in this milestone (spec.md Assumptions, mirroring spec 015's identical deferral for its grading cache) -- only an instruction-version bump invalidates entries. Growth is bounded in practice by the (small) space of common short/blank answer texts and common tutoring-chat phrasings, not by every unique learner interaction.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | Not touched -- this feature caches two guardrail checks, not the mastery model or sequencing logic | PASS |
| II. Generated content graded against a rubric | Not touched -- grading itself (and its own spec 015 cache) is unchanged; moderation/shielding are pre-grading and answer-leakage guardrails, not grading | PASS |
| III. One engine, many subjects | Both cache lookups key on normalized text/instruction-version only, never a subject-id-keyed branch; `check_no_subject_conditionals.py` must pass unchanged against the two new cache modules | PASS |
| IV. Agent boundaries reflect real responsibility | No agent added, removed, or merged. Caching sits as a lookup layer in front of two existing in-process guardrail checks, not as a new agent | PASS |
| V. Every decision logged and explainable | Directly reinforced: FR-009 requires a cache hit to produce the same observability a fresh call would -- moderation reuses existing `AssessmentEvent` payload keys (two new flags), shielding gets two new `tutor_exchanges` columns since one exchange can span several independent checks (data-model.md §3); both get a `record_cache_hit_trace` Langfuse span, same as spec 015's two cache types | PASS (reinforces) |
| VI. Agent boundaries match deployment boundaries | No new A2A service. Both guardrails already run in-process in `backend/`; caching doesn't change where either call happens, only whether it happens | PASS |
| VII. Spec before code | `spec.md` written via `/speckit-specify` (2026-09-30), quality checklist passed with zero `[NEEDS CLARIFICATION]` markers before this `plan.md` | PASS |
| VIII. No real learner data until privacy specified | Neither new cache table stores raw submitted answer text or raw tutor-message text, or any `learner_id`/FK to a real-identity table (FR-008, data-model.md §1/§2) -- `check_deletion_cascade_coverage.py` requires no new entry since no such FK is introduced | PASS |
| IX. Deployable and demoable from the start | Both new tables are read/written per-request from the existing stateless Vercel Function; no in-memory cache/session state assumed; no new persistent process | PASS |
| X. Staged release discipline | Implemented via a normal feature-branch PR into `staging`, same CI gates apply | PASS |

No violations. Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/026-moderation-shielding-cache/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md  # Already produced by /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature introduces no new or changed HTTP API surface (mirrors spec 015's identical decision). Both cache checks happen entirely inside the existing `POST /api/questions/{id}/answer` (moderation) and `POST /api/tutor/sessions/{id}/messages` (shielding) request paths, whose contracts are already fully specified by specs 007/018 and 016. User Story 3's hit-rate visibility extends the existing maintainer-run `scripts/cache_hit_rate_report.py`, not a new endpoint.

### Source Code (repository root)

Existing multi-service monorepo, unchanged in shape. This feature only adds/edits files inside `backend/`:

```text
backend/
├── src/
│   ├── models/
│   │   ├── moderation_cache.py                  # NEW: data-model.md §1
│   │   └── shielding_classification_cache.py    # NEW: data-model.md §2
│   ├── models/tutor_exchange.py                 # + shielding_checks_total / shielding_checks_from_cache columns (data-model.md §3)
│   ├── services/
│   │   ├── cache_common/signature.py            # + compute_text_signature() / compute_paired_signature() (research.md §2)
│   │   ├── moderation_cache/
│   │   │   └── cache.py                         # NEW: get_or_check_moderation() (research.md §3)
│   │   └── shielding_cache/
│   │       └── cache.py                         # NEW: get_or_classify_match() (research.md §3)
│   ├── api/routes/questions.py                  # check_moderation(...) call sites (both free-text and multi-step) wrapped via get_or_check_moderation(...); answer_payload / rejection payload gain moderation_served_from_cache/moderation_cache_miss_reason
│   ├── services/tutor/session.py                # match_fn binding passed to determine_shielding switched to get_or_classify_match(...); increments shielding_checks_total/shielding_checks_from_cache on the TutorExchange row
│   └── observability/tracing.py                 # no change -- record_cache_hit_trace already takes cache_type
├── alembic/versions/                            # NEW: one migration off 824e2c5a0678 -- two tables + two tutor_exchanges columns
├── scripts/
│   ├── cache_hit_rate_report.py                 # + moderation/shielding rates (research.md §8)
│   └── guardrail_cache_load_test.py             # NEW: SC-001/SC-002 verification (research.md §7)
└── tests/
    ├── unit/caching/
    │   ├── test_moderation_cache.py             # signature scoping, version-bump-as-miss, fail-open
    │   └── test_shielding_cache.py              # per-question scoping, version-bump-as-miss, fail-open
    └── integration/
        └── test_guardrail_caching.py            # end-to-end hit/miss parity, version-invalidation
```

**Structure Decision**: No new project, service, or route. Every change lands inside the existing `backend/` tree's `models/`, `services/`, `api/routes/`, `scripts/`, `alembic/`, and `tests/` directories -- consistent with this being a lookup layer in front of two already-complete guardrails, not a new architectural component. `grading-agent/`, `tutor-agent/`, and `frontend/` are all untouched.

## Complexity Tracking

*No violations -- table not needed.*

# Implementation Plan: Spaced Repetition / Mastery Decay for Foundational Topics

**Branch**: `035-spaced-repetition-mastery-decay` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/024-mastery-decay/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Make the Sequencing Agent's existing mastered-topic review fallback
(`rank_eligible_topics`'s `mastered` branch, `backend/src/agents/
sequencing/agent.py`) rank that one pool by a read-time-only, decayed
"effective mastery" instead of the raw, never-decaying `p_mastery` it
uses today -- so a topic mastered long ago and never revisited surfaces
for review ahead of one mastered more recently, without inventing a new
scheduler. Per research.md §1, decay is a pure function of
(`p_mastery`, `updated_at`, `now`) living in a new `backend/src/
services/mastery/decay.py`, mirroring the existing BKT module's
fixed-global-constant style. It is never persisted, never fed back into
`apply_bkt_update`, and never changes a topic's mastery band -- so every
other consumer (dashboard, Recommendation Agent, prerequisite gating,
the eligible-pool ranking itself) is unaffected by construction, not by
a special-cased branch. Zero schema change, zero new API/contract
surface, zero frontend change.

## Technical Context

**Language/Version**: Python 3.12 (`backend/pyproject.toml`'s
`requires-python = ">=3.12"`) -- unchanged, no new language surface.

**Primary Dependencies**: None new. Reuses SQLAlchemy 2.0 (already
installed) for the one existing `MasteryState` query
`_load_topic_ranking_context` already runs, and the stdlib `datetime`
module for the decay computation itself -- no date/time library is
added.

**Storage**: PostgreSQL (Neon) -- no schema change. `MasteryState.
updated_at` (already a column, already maintained via `onupdate=func.
now()`) is the only input this feature reads that it doesn't already
read today.

**Testing**: pytest. Pure-function unit tests for the new decay module
(mirrors `tests/unit/test_mastery_bkt.py`) and for `rank_eligible_
topics`'s decayed sort (mirrors `tests/unit/test_sequencing.py`'s
grade-gate convention), plus one DB-backed integration test proving
`select_next_topic`'s real fallback path picks the more-decayed row
(mirrors `tests/integration/test_next_topic_fallback.py`).

**Target Platform**: Vercel (existing backend Function) -- no change to
deployment shape; decay is computed inline during an already-happening
request, never a background job (Constitution Principle IX).

**Project Type**: Web application (existing `backend/` + `frontend/`
split) -- this feature only touches `backend/`. No frontend change:
`preview_topic_priority`'s response shape (`TopicPreviewEntryOut`) and
`select_next_topic`'s response shape are both unchanged; only the
*order* returned by the mastered-fallback branch changes.

**Performance Goals**: No added query. `updated_at` is already selected
by the same `MasteryState` query `_load_topic_ranking_context` runs
today; the decay computation itself is a handful of arithmetic
operations per topic in the (already small, already in-memory)
mastered-fallback pool.

**Constraints**: Must not add a background/cron process (Constitution
Principle IX -- no persistent process on Vercel); must not change
`MasteryState.p_mastery`, `update_count`, or `consecutive_mastered_
observations` (FR-002); must not change any consumer's output other
than the mastered-fallback pool's internal ordering (FR-004/FR-005).

**Scale/Scope**: One new pure-function module (~30 lines, mirroring
`bkt.py`'s size), two new optional keyword arguments on one existing
function (`rank_eligible_topics`), and two call sites (`select_next_
topic`, `preview_topic_priority`) each gaining one captured timestamp
and one dict lookup already available from data they already query.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applicability | Result |
|---|---|---|
| I (Personalization is a model, not a guess) | Directly applicable -- decay is a second explicit, deterministic function alongside BKT, not an LLM impression | Pass -- `effective_mastery_for_review(p_mastery, updated_at, now)` is pure; FR-010 requires identical inputs to always produce an identical output, and one `now` is captured per ranking call |
| II (Rubric grading) | N/A -- no grading surface touched | Pass (not engaged) |
| III (One Engine, Many Subjects) | Directly applicable -- decay parameters are fixed globals, not per-subject/per-topic | Pass -- no subject-conditional code added; `check_no_subject_conditionals.py` stays clean by construction (nothing subject-specific is added) |
| IV, VI (agent boundaries, A2A) | N/A -- no new agent, no A2A service; this stays inside the existing local Sequencing Agent | Pass (not engaged) |
| V (logged/explainable decisions, tracing) | Applicable in spirit, resolved narrower than a full audit-log change: spec.md deliberately does not add a new audit-log field for decay (Assumptions) -- the fallback path's existing `is_fallback` flag already answers "why was I shown this" at the granularity this feature changes (a fallback review pick), and no new agent invocation exists to trace | Pass -- no new decision surface requiring a new log field; existing fallback logging is untouched and still accurate |
| VII (spec before code) | Directly applicable | Pass -- this plan follows the approved spec.md; tasks.md follows this plan |
| VIII (no real learner data) | Directly applicable -- decay parameters are new fixed constants chosen absent real learner data | Pass -- FR-009 requires fixed global constants only, explicitly not per-learner-fitted, matching the BKT model's own existing precedent for the same reason |
| IX (deployable/demoable on Vercel) | Directly applicable -- decay must not require a background process | Pass -- computed lazily per request (research.md §1), same pattern as Milestone 20's timed-session expiry check |
| X (staged release discipline) | Directly applicable | Pass -- lands via a feature branch PR into `staging`, no direct push |

No violations. Complexity Tracking table below is empty/omitted.

## Project Structure

### Documentation (this feature)

```text
specs/024-mastery-decay/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature adds no new API endpoint and
changes no existing endpoint's request/response shape (research.md
§4) -- it changes only the internal ordering of an existing ranking
function's fallback branch. Same reasoning Milestone 19 (schema-drift
CI check) used for omitting `contracts/`.

### Source Code (repository root)

Existing web-application structure (`backend/` + `frontend/`) is
unchanged; this feature only adds/modifies files within `backend/`,
touching neither `frontend/` nor any other milestone's existing code:

```text
backend/
├── src/
│   ├── services/
│   │   └── mastery/
│   │       ├── bkt.py                      # unchanged -- decay never feeds into or reads from this
│   │       └── decay.py                    # NEW -- pure effective-mastery-for-review function (research.md §1)
│   └── agents/
│       └── sequencing/
│           └── agent.py                    # MODIFIED -- rank_eligible_topics gains two optional kwargs;
│                                            #   _load_topic_ranking_context, select_next_topic, and
│                                            #   preview_topic_priority each pass updated_at/now through
└── tests/
    ├── unit/
    │   ├── test_mastery_decay.py           # NEW -- pure decay-function coverage (mirrors test_mastery_bkt.py)
    │   └── test_topic_priority_decay.py    # NEW -- rank_eligible_topics decayed-sort coverage (mirrors
    │                                       #   test_sequencing.py's grade-gate convention)
    └── integration/
        └── test_next_topic_decay_fallback.py  # NEW -- real-DB proof select_next_topic's fallback picks
                                                #   the more-decayed row (mirrors test_next_topic_fallback.py)
```

**Structure Decision**: Web-application structure (Option 2), already
locked by every prior milestone. No new top-level directory, no new
package -- additive within `backend/src/services/mastery/`'s existing
convention (one module per model/algorithm, alongside `bkt.py`) plus
optional-kwarg additions to one existing function, matching how spec
017's `grade_by_topic`/`unlocked_grade` gate was added to the same
function without disturbing any existing caller.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations -- table intentionally omitted.

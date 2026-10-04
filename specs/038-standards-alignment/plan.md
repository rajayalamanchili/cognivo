# Implementation Plan: Standards Alignment

**Branch**: `038-standards-alignment` | **Date**: 2026-10-04 | **Spec**: `specs/038-standards-alignment/spec.md`

**Input**: Feature specification from `specs/038-standards-alignment/spec.md`

## Summary

Tag graded topics with real Common Core Math / NGSS standards codes (a new `StandardsTag` table, content-artifact-authored), and surface per-standard coverage (met / in-progress / not-yet-reached, derived only from existing `MasteryState` bands -- no new mastery computation) on the instructor's per-learner and roster-aggregate dashboard views, and on a new guardian-facing view of their own enrolled learner. Pure read/presentation layer plus one new content-authored entity -- no sequencing, grading, or mastery-model change (FR-008). The whole feature is gated by a developer-controlled, frontend-only render toggle (FR-013) -- backend computation and content-artifact validation are unaffected by its state.

## Technical Context

**Language/Version**: Python 3.12 (backend, FastAPI), TypeScript 5 (frontend, Next.js/React) -- both already locked in `tech-stack.md`, no change.

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, Next.js/React -- all already installed. **Zero new dependencies** (ladder step 5): per Clarifications, standards codes are sourced by manual/LLM research directly into content-artifact YAML, not a live external standards API. The developer toggle (FR-013) is a plain `process.env.NEXT_PUBLIC_STANDARDS_ALIGNMENT_ENABLED` read, the same mechanism `NEXT_PUBLIC_EXPLAIN_EVERY_PICK` already uses -- no feature-flag library.

**Storage**: PostgreSQL via Neon. **One new table** (`standards_tags`), following the existing `GradeBand`/`PrerequisiteEdge` pattern exactly -- no new columns on any existing table, no change to `MasteryState`/`Topic` schema beyond a new FK target.

**Testing**: `pytest` (backend contract/unit/integration), `Vitest` + React Testing Library (frontend) -- existing patterns, no new tooling.

**Target Platform**: Vercel serverless (existing) -- every new read is a per-request query over already-open DB connections; content-artifact tagging is a build-time/load-time authoring change, not a runtime process (Constitution Principle IX).

**Project Type**: Web application (existing `backend/` + `frontend/` split).

**Performance Goals**: No new performance target. Standards coverage for one learner is computed from the same `Topic`+`MasteryState` rows the existing `mastery-state` endpoint already loads for that learner -- one additional small query (`StandardsTag` by `subject_id`) per request, not a new N+1 pattern. The roster-aggregate view (US2) repeats this per enrolled learner, matching `build_roster_dashboard`'s existing per-learner fan-out shape (a plain loop, no new async/batch mechanism).

**Constraints**: Must not add a subject-id- or framework-keyed conditional anywhere (Principle III) -- `framework`/`code` are opaque authored strings, read and compared generically, the same way `topic_id` already is. Must not widen `require_learner_ownership_if_real()`'s guardian-only contract (`services/auth/dependencies.py`) to also accept instructor callers -- the instructor path reuses the already-roster-authorized `build_roster_dashboard` aggregation instead (research.md Decision 3). Must pair every status with a visible text label, never color alone (Clarifications, FR-011).

**Scale/Scope**: Two existing content artifacts, 16 topics total. Only `algebra-1` is currently graded (`grade_bands: [6, 7, 8]`); `biology` is deliberately ungraded (kept as Milestone 15's SC-005 ungraded-subject regression fixture, per `backend/content/biology/subject.yaml`'s own comment) -- so FR-010's real-code population applies to `algebra-1`'s 8 topics only. Zero NGSS tags will exist in this project's actual data until a graded science subject exists; this is FR-009's zero-tags case, not a gap (research.md Decision 1).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization is a model, not a guess | Standards coverage reads `MasteryState.band` directly (FR-004); no new threshold, no re-scoring. | PASS |
| II. Rubric-graded, never vibes | Not applicable -- no grading or question generation touched. | N/A |
| III. One engine, many subjects | `framework`/`code` are opaque content-artifact strings, validated and stored generically (same pattern as `topic_id`); no engine code branches on a specific framework or code value anywhere. | PASS |
| IV. Agent boundaries reflect real responsibility | No new agent, no new A2A service -- pure data/presentation addition over existing routes. | PASS |
| V. Logged and explainable | FR-007: every coverage figure traces to the specific `(topic_id, framework, code)` rows and `MasteryState` bands that produced it -- no rolled-up-only numbers, no new audit event needed (this is a read of already-logged mastery state, not a new decision). | PASS |
| VI. A2A boundary discipline | N/A -- no A2A service touched. | N/A |
| VII. Spec before code | This plan follows an approved, clarified `spec.md` (two clarification sessions, zero outstanding markers). | PASS |
| VIII. No real data until privacy is specified | No new data collection; `StandardsTag` carries no learner-identifying column, so it needs no deletion-cascade coverage (`check_deletion_cascade_coverage.py` unaffected, matching `GradeBand`/`PrerequisiteEdge`'s existing exemption). | PASS |
| IX. Deployable/stateless | Every read is per-request against already-open DB connections; content-artifact tagging is authored data loaded the same way `grade`/`skill_definition` already are -- no new background process. | PASS |
| X. Staged release discipline | Standard feature-branch -> `staging` -> `main` PR flow, unchanged. | PASS |

No violations. **Complexity Tracking is not needed for this feature.**

**Post-Phase-1 re-check**: `data-model.md` and `contracts/api-changes.md` confirm the only schema change is one new table with no FK from any learner-identifying row, and every API change is an additive field on an existing response model plus one new frontend-only route (no new backend endpoint beyond what FR-009's guardian page needs, which reuses the existing `mastery-state` endpoint). Constitution Check still PASSES with no changes to the table above.

## Project Structure

### Documentation (this feature)

```text
specs/038-standards-alignment/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   └── api-changes.md
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── content/
│   └── algebra-1/subject.yaml        # EXTENDED: each of the 8 topics gains a `standards:` list
│                                      #   (real Common Core Math codes, FR-010). biology/subject.yaml
│                                      #   is NOT touched -- it has no grade_bands, so FR-003 forbids
│                                      #   tagging it at all (Technical Context Scale/Scope).
├── src/
│   ├── models/
│   │   └── standards_tag.py          # NEW: StandardsTag, mirrors grade_band.py's minimal-table shape
│   ├── services/
│   │   ├── content_artifact/
│   │   │   ├── validator.py          # EXTENDED: `_validate_standards(...)`, same shape as
│   │   │   │                         #   `_validate_misconceptions`/`_validate_topic_grade` --
│   │   │   │                         #   rejects a tag on an ungraded topic (FR-003), rejects a
│   │   │   │                         #   missing framework/code (US3 Acceptance Scenario 3), and
│   │   │   │                         #   rejects two topics sharing a (framework, code) with
│   │   │   │                         #   mismatched titles (FR-012)
│   │   │   └── loader.py             # EXTENDED: persist_content_artifact upserts StandardsTag rows
│   │   │                             #   the same delete-and-recreate way as PrerequisiteEdge
│   │   │                             #   (nothing else references a tag row)
│   │   └── standards/
│   │       └── coverage.py           # NEW: compute_standards_coverage(db, learner_id, subject_id) --
│   │                                 #   the one shared function both mastery.py (guardian/demo path)
│   │                                 #   and dashboard/aggregation.py (instructor path) call; groups
│   │                                 #   StandardsTag rows by (framework, code), applies the
│   │                                 #   all-tagged-topics-mastered rule (Clarifications)
│   ├── api/routes/
│   │   ├── mastery.py                # EXTENDED: MasteryStateResponse gains `standards` field,
│   │   │                             #   computed via coverage.py -- backs the guardian-facing view
│   │   │                             #   (FR-004) through the existing ownership-gated endpoint,
│   │   │                             #   no change to require_learner_ownership_if_real()
│   │   └── instructor_dashboard.py   # EXTENDED: DashboardLearnerOut gains `standards`; DashboardOut
│   │                                 #   gains `standards_summary` (US2's roster-wide aggregate,
│   │                                 #   computed by combining each learner's coverage.py result --
│   │                                 #   no new query, no new permission check beyond the existing
│   │                                 #   roster.instructor_id ownership check)
│   └── services/dashboard/
│       └── aggregation.py            # EXTENDED: LearnerDashboardEntry gains `standards`, computed
│                                     #   via the same coverage.py call as mastery.py above
│
frontend/
├── src/
│   ├── components/
│   │   └── StandardsCoverage.tsx     # NEW: renders met/in-progress/not-yet-reached per standard,
│   │                                 #   text label always paired with color (FR-011); shared by
│   │                                 #   both the instructor per-learner view and the new guardian
│   │                                 #   page below -- same response shape, same component. Takes
│   │                                 #   an `enabled?: boolean` prop defaulting to
│   │                                 #   `NEXT_PUBLIC_STANDARDS_ALIGNMENT_ENABLED` (FR-013,
│   │                                 #   research.md Decision 5), mirroring
│   │                                 #   `SelectionReasonChip.tsx`'s `explainEveryPick` prop
│   │                                 #   exactly; renders `null` when disabled, self-gated --
│   │                                 #   neither call site below needs its own check
│   ├── app/instructor/dashboard/
│   │   └── instructor-dashboard-flow.tsx  # EXTENDED: renders StandardsCoverage per learner row plus
│   │                                       #   the roster-wide standards_summary (US2)
│   └── app/(auth)/guardian/learners/
│       └── page.tsx                  # EXTENDED: renders a NEW per-learner progress section (calls
│                                      #   the existing mastery-state endpoint, now carrying
│                                      #   `standards`) alongside the existing LearnerAssignments --
│                                      #   no guardian-facing progress view exists today (confirmed by
│                                      #   reading the current page: only JoinRosterForm +
│                                      #   LearnerAssignments render there), so this is net-new UI,
│                                      #   not an extension of an existing one (research.md Decision 4)
```

**Structure Decision**: Existing `backend/` (FastAPI) + `frontend/` (Next.js) split, unchanged. One new backend model/table (`StandardsTag`) and one new pure service function (`coverage.py`) shared by two existing routes; the content-artifact validator/loader gain one new field each, mirroring the `grade`/`misconceptions` pattern exactly. On the frontend, one new shared presentational component (self-gated by the FR-013 developer toggle) and one genuinely new surface (the guardian's per-learner progress section, which did not exist before this feature). No new top-level directory, no new service boundary, no new A2A call, no new feature-flag mechanism.

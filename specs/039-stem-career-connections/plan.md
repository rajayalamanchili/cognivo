# Implementation Plan: STEM-Career Connections

**Branch**: `039-stem-career-connections` | **Date**: 2026-10-04 | **Spec**: `specs/039-stem-career-connections/spec.md`

**Input**: Feature specification from `specs/039-stem-career-connections/spec.md`

## Summary

Author a real-world STEM career/application connection on every graded and
ungraded topic in both existing content artifacts (a new `career_connection`
JSON column on `Topic`, mirroring `image_asset`'s existing shape), and let it
be turned on or off per learner (a new `career_connections_enabled` boolean
on `LearnerProfile`, default on). Because this project has no real-learner
login -- the dashboard/practice/mastery/tutor flow is hardcoded to the single
shared, unauthenticated demo learner, and a real (guardian-managed) learner
never signs in -- the toggle has two actors: the demo learner controls its
own via a new settings page off its existing avatar menu; a real learner's
guardian controls theirs from the existing "My Learners" page. Both reuse the
existing `require_learner_ownership_if_real()` authorization rule for one new
endpoint pair. Content surfaces through the existing `mastery-state`
response (the same one both surfaces already fetch), gated server-side so an
off preference is enforced regardless of frontend code. Pure read/write
addition over two existing tables -- no sequencing, grading, or mastery-model
change (FR-009).

## Technical Context

**Language/Version**: Python 3.12 (backend, FastAPI), TypeScript 5 (frontend, Next.js/React) -- already locked in `tech-stack.md`, no change.

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, Next.js/React -- all already installed. **Zero new dependencies** (ladder step 5): content is authored directly into existing YAML content artifacts (Clarifications/Assumptions), no external careers API or dataset.

**Storage**: PostgreSQL via Neon. **Two new columns, no new tables**: `topics.career_connection` (JSON, nullable) and `learner_profiles.career_connections_enabled` (boolean, `server_default=sa.true()`), both additive to existing tables -- no change to any other table's schema.

**Testing**: `pytest` (backend contract/unit/integration), `Vitest` + React Testing Library (frontend) -- existing patterns, no new tooling.

**Target Platform**: Vercel serverless (existing) -- every new read/write is a per-request query over already-open DB connections; content-artifact authoring is a load-time change, not a runtime process (Constitution Principle IX).

**Project Type**: Web application (existing `backend/` + `frontend/` split).

**Performance Goals**: No new performance target. `career_connections` is computed inline in the already-existing `mastery-state` handler from the same `Topic` rows it already loads for that subject, plus one already-fetched `LearnerProfile.career_connections_enabled` read -- no new query pattern, no N+1 (same reasoning as spec 038's `standards` field addition to this identical response).

**Constraints**: Must not add a subject-id-keyed conditional anywhere (Principle III) -- `career`/`description` are opaque authored strings, read and rendered generically, same as `topic_id`/`image_asset` already are. Must not widen `require_learner_ownership_if_real()`'s guardian-only-or-demo-no-op contract to a third actor -- both the new endpoint and the extended `mastery-state` field reuse it exactly as every other learner-scoped route already does. Preference enforcement (FR-006) must happen server-side, not only in frontend rendering.

**Scale/Scope**: Both existing content artifacts, 16 topics total (`algebra-1`: 8, `biology`: 8) -- unlike Standards Alignment, both get real authored connections (FR-010), since this feature has no grade dependency gating authorship (research.md Decision 2). One new column on `LearnerProfile`, applying identically to the one seeded demo learner and every real learner a guardian has created.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization is a model, not a guess | No mastery/sequencing computation touched; `career_connections_enabled` and `career_connection` are both inert with respect to the mastery model (FR-009). | PASS |
| II. Rubric-graded, never vibes | Not applicable -- no grading or question generation touched. | N/A |
| III. One engine, many subjects | `career`/`description` are opaque content-artifact strings, validated and rendered generically (same pattern as `image_asset`/`topic_id`); no engine code branches on a specific career or subject value. | PASS |
| IV. Agent boundaries reflect real responsibility | No new agent, no new A2A service -- pure data/presentation addition over existing routes. | PASS |
| V. Logged and explainable | Not a personalization or grading decision (FR-009) -- a presentation preference, not a sequencing/grading outcome Principle V's audit-log requirement covers. No new audit event needed, same reasoning spec 038 applied to its own read-only `standards` field. | N/A |
| VI. A2A boundary discipline | N/A -- no A2A service touched. | N/A |
| VII. Spec before code | This plan follows an approved, clarified `spec.md` (one clarification session, three questions, zero outstanding markers). | PASS |
| VIII. No real data until privacy is specified | No new learner-identifying data collected -- `career_connections_enabled` is a presentation preference on an already-existing learner row, carrying no new PII; `career_connection` carries no learner-identifying column at all. Matches `GradeBand`/`PrerequisiteEdge`/`StandardsTag`'s existing deletion-cascade exemption. | PASS |
| IX. Deployable/stateless | Every read/write is per-request against already-open DB connections; content-artifact authoring is loaded the same way `image_asset`/`standards` already are -- no new background process. | PASS |
| X. Staged release discipline | Standard feature-branch -> `staging` -> `main` PR flow, unchanged. | PASS |

No violations. **Complexity Tracking is not needed for this feature.**

**Post-Phase-1 re-check**: `data-model.md` and `contracts/api-changes.md` confirm the only schema change is two additive columns on tables that already exist, with no new foreign key and no learner-identifying new column beyond a boolean already covered by the existing `LearnerProfile` row's own deletion handling. Every API change is either an additive field on an existing response or a new endpoint pair reusing an existing authorization function verbatim. Constitution Check still PASSES with no changes to the table above.

## Project Structure

### Documentation (this feature)

```text
specs/039-stem-career-connections/
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
│   ├── algebra-1/subject.yaml        # EXTENDED: each of the 8 topics gains a `career_connection:`
│   │                                  #   mapping (real career, FR-010)
│   └── biology/subject.yaml          # EXTENDED: each of the 8 topics gains a `career_connection:`
│                                      #   mapping too -- unlike spec 038, not excluded (research.md
│                                      #   Decision 2: no grade dependency)
├── src/
│   ├── models/
│   │   ├── topic.py                  # EXTENDED: `career_connection: Mapped[dict | None]` column,
│   │   │                             #   same JSON-column shape as the existing `image_asset`
│   │   └── learner_profile.py        # EXTENDED: `career_connections_enabled: Mapped[bool]` column,
│   │                                 #   `server_default=sa.true()`
│   ├── services/content_artifact/
│   │   ├── validator.py              # EXTENDED: `_validate_career_connection(...)`, same shape as
│   │   │                             #   `_validate_image_asset` -- requires `career`+`description`
│   │   │                             #   when present, no grade-gate (unlike `_validate_standards`)
│   │   └── loader.py                 # EXTENDED: `persist_content_artifact` sets
│   │                                 #   `Topic.career_connection` the same upsert-in-place way it
│   │                                 #   already sets `image_asset`
│   └── api/routes/
│       ├── mastery.py                # EXTENDED: `MasteryStateResponse` gains `career_connections`
│       │                             #   (new `CareerConnectionOut` list), computed inline from the
│       │                             #   already-loaded `Topic` rows + the learner's
│       │                             #   `career_connections_enabled` flag; NEW
│       │                             #   `GET`/`PATCH /api/learners/{learner_id}/
│       │                             #   career-connections-preference`, reusing
│       │                             #   `require_learner_ownership_if_real()` verbatim
│       └── demo_learner.py           # UNCHANGED -- `/settings` resolves the demo learner's id via
│                                     #   the existing `GET /api/demo-learner` call, same as
│                                     #   `/dashboard` already does
│
frontend/
├── src/
│   ├── components/
│   │   ├── CareerConnectionsList.tsx       # NEW: presentational, renders matched
│   │   │                                   #   `career_connections` entries against a topic list;
│   │   │                                   #   reused unmodified by both surfaces below
│   │   ├── CareerConnectionsToggle.tsx     # NEW: fetches/patches the new preference endpoint for a
│   │   │                                   #   given `learnerId`; reused unmodified by the demo
│   │   │                                   #   settings page and the guardian's "My Learners" page
│   │   ├── DashboardSubjectSection.tsx     # EXTENDED: renders `CareerConnectionsList` from the
│   │   │                                   #   `career_connections` field off its already-fetched
│   │   │                                   #   `getMasteryState` call -- no new fetch
│   │   ├── GuardianLearnerCareerConnections.tsx  # NEW: sibling to `GuardianLearnerStandards.tsx`,
│   │   │                                         #   same `listLearnerEnrollments` +
│   │   │                                         #   `getMasteryState`-per-subject fetch shape,
│   │   │                                         #   extracting `.career_connections` instead of
│   │   │                                         #   `.standards`
│   │   └── Nav.tsx                         # EXTENDED: demo-learner avatar-menu dropdown gains a
│   │                                       #   "Settings" link to the new `/settings` page,
│   │                                       #   alongside the existing "Exit Demo"/"Sign In" items
│   ├── app/
│   │   ├── settings/
│   │   │   └── page.tsx              # NEW: demo-learner-only settings page (no explicit route
│   │   │                             #   gate, same precedent as `/dashboard`/`/mastery`), resolves
│   │   │                             #   the demo learner's id via `getDemoLearner()`, renders
│   │   │                             #   `CareerConnectionsToggle`
│   │   └── (auth)/guardian/learners/
│   │       └── page.tsx              # EXTENDED: renders `CareerConnectionsToggle` inside the
│   │                                  #   existing per-added-learner `<li>` block, alongside
│   │                                  #   `JoinRosterForm`/`GuardianLearnerStandards`/
│   │                                  #   `LearnerAssignments` -- same per-session-added-learner
│   │                                  #   scope those three already have
```

**Structure Decision**: Existing `backend/` (FastAPI) + `frontend/` (Next.js) split, unchanged. Two new columns on two already-existing tables (no new table, unlike Standards Alignment's `StandardsTag`) and one new route pair reusing an existing authorization dependency verbatim. On the frontend, two new small presentational/data components reused across the demo-learner and guardian surfaces, plus one genuinely new page (`/settings`, for the demo learner only -- the guardian's equivalent control slots into its already-existing "My Learners" page). No new top-level directory, no new service boundary, no new A2A call, no new auth concept.

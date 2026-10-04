# Phase 0 Research: Standards Alignment

All decisions below were resolved by reading the actual code and content artifacts this feature extends, not by assumption -- each cites the exact existing model/function/file it mirrors or reuses, per Constitution Principle I's "no second implementation" bar.

## 1. Which content artifact actually gets real standards codes (FR-010, Scale/Scope)

**Decision**: Only `backend/content/algebra-1/subject.yaml`'s 8 topics get real Common Core Math codes. `backend/content/biology/subject.yaml` gets none.

**Rationale**: `biology/subject.yaml`'s own header comment states it is deliberately left without `grade_bands` as "the SC-005 ungraded-subject regression fixture" for Milestone 15. FR-003 (standards tags only declarable on a graded topic) therefore forbids tagging any biology topic at all -- not an oversight, a direct consequence of a prior milestone's own deliberate test fixture. FR-010's "every graded topic in this project's existing content artifacts" is vacuously satisfied for biology (zero graded topics, so zero required tags), landing on FR-009's existing zero-tags case rather than a contradiction. Net effect: this milestone's real data will contain Common Core Math codes only; zero NGSS codes will exist anywhere in the running system until a graded science subject is added later (the full-K-12-catalog backlog item roadmap.md already tracks separately).

**Alternatives considered**: Making `biology` graded as part of this feature so NGSS codes have somewhere to go -- rejected; that would silently repurpose Milestone 15's own regression fixture for a different feature's convenience, a change with a blast radius well outside this feature's stated scope (FR-008's presentation-only boundary), and not something FR-010 actually requires.

## 2. Data model for a standards tag (FR-001, FR-003)

**Decision**: A new minimal table, `StandardsTag` (`backend/src/models/standards_tag.py`), mirroring `GradeBand`'s shape exactly -- no metadata beyond the fields FR-001 names. Composite primary key `(subject_id, topic_id, framework, code)` (FK to `Topic`'s composite key), plus a non-key `title` column. One row per (topic, standard) pairing; a topic with two tags is two rows. Persisted the same delete-and-recreate way as `PrerequisiteEdge` (`loader.py`'s own docstring: "cheap to delete and recreate since nothing references them") rather than upserted in place like `Topic`/`GradeBand` -- nothing holds a foreign key into a specific tag row, so there is no stale-reference hazard to avoid.

**Rationale**: The composite PK makes an exact-duplicate tag on one topic a schema-level impossibility rather than an edge case to validate separately. A dedicated table (not JSON embedded in `Topic.skill_definition`, the way `misconceptions` is) is required because FR-005's roster aggregate needs to group tags by `(framework, code)` *across* topics -- a cross-row grouping query that a per-topic JSON blob can't express without loading and parsing every topic's JSON in application code for every dashboard request.

**Alternatives considered**: Embedding `standards` as a JSON list inside `Topic.skill_definition`, matching `misconceptions`' existing pattern -- rejected per the grouping-query argument above; `misconceptions` never needs a cross-topic join (M11's classifier loads all of one subject's topics once per training run, not per dashboard request).

## 3. Guardian access without widening the ownership gate (Clarifications, FR-004)

**Decision**: Two independent call paths, not one widened permission check:
- **Guardian path**: `GET /api/learners/{learner_id}/mastery-state` (`mastery.py`) already calls `require_learner_ownership_if_real()` and already loads every `Topic`+`MasteryState` row for that learner/subject. Add a `standards` field to `MasteryStateResponse`, computed by a new shared function (`services/standards/coverage.py`) called with the same `topics`/`states` data already in scope. No change to `require_learner_ownership_if_real()` itself.
- **Instructor path**: `require_learner_ownership_if_real()` explicitly rejects any `claims.account_type != "guardian"` (`services/auth/dependencies.py`) -- it was deliberately hardened in PR #93 to close a real enumeration gap, and loosening it to also accept an instructor would reopen exactly the kind of ambient-authority question that fix closed. Instead, `build_roster_dashboard` (`services/dashboard/aggregation.py`) -- already instructor-roster-ownership-checked at the route level (`instructor_dashboard.py`'s `roster.instructor_id != instructor.instructor_id`) -- gains a second per-learner call to the same `coverage.py` function, independently of the guardian path.

**Rationale**: One shared pure function (`coverage.py`) guarantees both surfaces compute standards status identically (FR-004's "both views" requirement) without either widening an existing, deliberately-narrow security boundary or duplicating the coverage logic itself.

**Alternatives considered**: Adding `instructor` as a second accepted `account_type` inside `require_learner_ownership_if_real()`, gated on roster co-membership -- rejected; that function's one job today is "is this guardian's own learner," and teaching it a second, differently-shaped authorization rule (instructor + shared roster, not ownership) makes a security-critical function harder to reason about for a feature that doesn't need it, when the existing roster-level check already does the job.

## 4. Guardian-facing progress view does not exist yet (Clarifications, FR-004)

**Decision**: `frontend/src/app/(auth)/guardian/learners/page.tsx` is the only guardian-facing page that already knows a real `learner_id` (added via `createLearner`). Read in full: it renders `JoinRosterForm` and `LearnerAssignments` only -- no mastery/progress view of any kind. This feature adds a new `StandardsCoverage` render to that same page, calling the existing (now-extended) `mastery-state` endpoint for that `learner_id`.

**Rationale**: `MasteryView.tsx`/`mastery-flow.tsx` (the demo-learner dashboard's existing per-topic mastery UI) are hardwired to `getDemoLearner()`, not parameterized by an arbitrary `learner_id` -- confirmed by reading `mastery-flow.tsx` directly rather than assuming it was reusable as-is. Building a new, smaller `StandardsCoverage` component (standards-only, not full per-topic mastery) sidesteps re-plumbing that page for a real learner, and is a smaller, more honest diff than retrofitting a demo-only flow.

**Alternatives considered**: Generalizing `mastery-flow.tsx` to accept a `learner_id` prop so the guardian page could reuse the whole page -- rejected as materially larger than this feature's scope (that page's full per-topic mastery view, "refreshed" banner, and sparkline are not part of this feature's ask); `StandardsCoverage.tsx` only needs the new `standards` field, not the rest of `MasteryStateResponse`.

## 5. Accessibility encoding (Clarifications, FR-011)

**Decision**: `StandardsCoverage.tsx` renders status as `{color-coded icon/background} + {visible text label}` always -- "Met" / "In progress" / "Not yet reached" -- never a color-only chip or hover-only tooltip.

**Rationale**: Matches the pattern this project has required twice before for the identical reason (colorblind accessibility, touch-device invisibility of hover-only cues): Milestone 10's image-stimuli accessibility requirement, and Milestone 23's `/speckit-clarify` session on the "last practiced" decay indicator, plus the mid-PR fix (PR #90) that converted `MasteryView`'s recovery framing from a hover-only `title` tooltip to visible text for the same reason.

**Alternatives considered**: None seriously -- this project has already tried and rejected color-only/hover-only status encoding twice.

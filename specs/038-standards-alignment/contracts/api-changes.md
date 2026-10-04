# API Contract Changes: Standards Alignment

All changes are additive (new fields on existing responses). No existing field changes type or meaning; no existing endpoint's request shape, auth requirement, or URL changes. Backward compatible by construction -- an old frontend build talking to a new backend ignores the new fields; the new guardian-page UI requires the new backend field.

## New shared shape: `StandardCoverageOut`

Used by both modified endpoints below, so an instructor's and a guardian's view of the same learner's coverage are byte-for-byte identical in shape and derivation (FR-004).

```
framework: str
code: str
title: str
topic_ids: list[str]
status: "met" | "in_progress" | "not_yet_reached"
```

## Modified: `GET /api/learners/{learner_id}/mastery-state`

Auth unchanged -- still gated by `require_learner_ownership_if_real()` (guardian-owns-this-real-learner, or demo/nonexistent no-op). Not widened to accept instructor callers (research.md Decision 3).

**`MasteryStateResponse`** gains:
```
standards: list[StandardCoverageOut]
```
Empty list for a subject with zero `StandardsTag` rows (FR-006/FR-009) -- not an error, not an omitted field.

## Modified: `GET /api/rosters/{roster_id}/dashboard`

Auth unchanged -- still gated by the existing `roster.instructor_id != instructor.instructor_id` check in `instructor_dashboard.py`.

**`DashboardLearnerOut`** gains:
```
standards: list[StandardCoverageOut]
```
(Same shape and derivation as the guardian path above, computed by the same `services/standards/coverage.py` function -- FR-004.)

**`DashboardOut`** gains:
```
standards_summary: list[RosterStandardSummaryOut]
```
where `RosterStandardSummaryOut` is:
```
framework: str
code: str
title: str
met_count: int
total_count: int   # total enrolled learners in the roster, not total tagged topics
```
One entry per distinct `(framework, code)` present in the roster's subject (US2, FR-005). Absent entirely (empty list) for a subject with zero `StandardsTag` rows -- the frontend renders no standards-summary section in that case (US2 Acceptance Scenario 2), not an empty table.

## Unmodified: everything else

No change to `POST /api/learners/{learner_id}/...` write routes, `questions.py`, `placement.py`, `quiz.py`, sequencing, or grading endpoints -- this feature is read-only over existing `MasteryState` data (FR-008).

**The FR-013 developer toggle changes nothing in this document.** It is a frontend-only render switch (`NEXT_PUBLIC_STANDARDS_ALIGNMENT_ENABLED`) -- both endpoints above always return `standards`/`standards_summary` regardless of the toggle's state; only `StandardsCoverage.tsx`'s rendering is gated (research.md Decision 5).

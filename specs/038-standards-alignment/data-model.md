# Data Model: Standards Alignment

**Feature**: `038-standards-alignment` | **Date**: 2026-10-04

One new table. No modified tables, no new columns on any existing table, no new `AssessmentEventType` values (this feature reads existing `MasteryState` rows; it never writes a new kind of event).

## New: `StandardsTag` (`backend/src/models/standards_tag.py`)

The standards-code tag FR-001 resolved to: a grouping layer above `Topic`, authored per topic, never an engine-side conditional on a specific framework or code (Constitution Principle III).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `subject_id` | `str` (FK, part of composite -> `topics.subject_id`) | No | Composite PK (part 1). |
| `topic_id` | `str` (FK, part of composite -> `topics.topic_id`) | No | Composite PK (part 2). `ForeignKeyConstraint(["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"])`. |
| `framework` | `str` | No | Composite PK (part 3). Opaque authored string, e.g. `"Common Core Math"`, `"NGSS"` -- never read conditionally by engine code (FR-002). |
| `code` | `str` | No | Composite PK (part 4). Opaque authored string, e.g. `"CCSS.MATH.CONTENT.6.NS.C.5"`. |
| `title` | `str` | No | Short human-readable title (e.g. "Understand integers as representing quantities"), shown alongside the code on every coverage view (FR-004, US1 Acceptance Scenario 1). Not part of the key -- a content-artifact edit that only corrects a title's wording doesn't orphan any reference to the `(framework, code)` pair. |

The 4-column composite PK makes an exact-duplicate tag on one topic (same framework, same code) a schema-level impossibility rather than a separate validation rule. A `(framework, code)` pair MAY repeat across more than one topic in the same subject (research.md Decision 2) -- that is the normal, expected shape for a standard spanning several topics, not an anomaly.

**Validation rules** (enforced in `services/content_artifact/validator.py`, not a DB constraint -- the same place `grade`/`misconceptions` schema rules already live):
- A `StandardsTag` MUST only be declared on a topic whose `grade` is non-null (FR-003). A content artifact declaring a `standards` entry on an ungraded topic fails validation at load time, the same way a malformed `misconceptions` entry already does.
- When the same `(framework, code)` pair is declared on more than one topic within a subject, every occurrence MUST carry the identical `title` string. This closes an otherwise-real ambiguity: without it, `coverage.py`'s `StandardCoverageEntry.title` would have no defined answer for which topic's title to surface when they disagree. Enforced the same way `misconceptions`' subject-wide `misconception_id` uniqueness is -- a `seen_titles_by_code` dict built across the per-topic validation loop, raising on the first mismatch found.

**Persistence**: delete-and-recreate on every content-artifact reload, matching `PrerequisiteEdge` (`loader.py`) rather than `Topic`/`GradeBand`'s upsert-in-place -- no other row holds a foreign key into a specific `StandardsTag` row, so there is no stale-reference hazard from dropping and reinserting the whole set for a subject on every load.

## Derived (not stored): per-standard coverage status

Computed on read by `services/standards/coverage.py`, never persisted -- the same "derive, don't duplicate" discipline `effective_mastery_for_review` (Milestone 22) already established for decay.

```python
@dataclass(frozen=True)
class StandardCoverageEntry:
    framework: str
    code: str
    title: str
    topic_ids: tuple[str, ...]   # every topic tagged with this (framework, code)
    status: Literal["met", "in_progress", "not_yet_reached"]
```

**Status rule** (Clarifications, FR-004): `met` iff every topic in `topic_ids` has a `MasteryState` row at `band == mastered` for the learner in question; `not_yet_reached` iff none of them has any `MasteryState` row at all (i.e. `status == "unknown"` for every tagged topic, matching `mastery.py`'s existing per-topic `status` field); otherwise `in_progress`. This reuses `MasteryState.band` exactly as already computed by Milestone 1's BKT model -- no new threshold, no new computation of mastery itself.

## Modified response shapes (additive only; full shapes in `contracts/api-changes.md`)

- `MasteryStateResponse` (`mastery.py`): `+ standards: list[StandardCoverageOut]`
- `LearnerDashboardEntry` (`services/dashboard/aggregation.py`, internal dataclass): `+ standards: tuple[StandardCoverageEntry, ...]`
- `DashboardLearnerOut` (`instructor_dashboard.py`): `+ standards: list[StandardCoverageOut]`
- `DashboardOut` (`instructor_dashboard.py`): `+ standards_summary: list[RosterStandardSummaryOut]` -- one entry per distinct `(framework, code)` across the roster's subject, each carrying `met_count` / `total_count` (US2, FR-005).

No existing field on any of the above is renamed, retyped, or removed.

## Developer toggle (FR-013): no data-model impact

`NEXT_PUBLIC_STANDARDS_ALIGNMENT_ENABLED` is a frontend-only render switch (research.md Decision 5) -- it introduces no column, no table, and no change to any response shape above. Both `StandardCoverageOut` and `RosterStandardSummaryOut` are always populated identically regardless of the toggle's state.

# Data Model: STEM-Career Connections

**Feature**: `039-stem-career-connections` | **Date**: 2026-10-04

Two new columns on two existing tables. No new tables, no new
`AssessmentEventType` values (this feature is presentation-only, FR-009 --
it writes no new kind of pedagogical event).

## Modified: `Topic` (`backend/src/models/topic.py`)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `career_connection` | `dict` (JSON) | Yes | New. `{career: str, description: str}` when present. `None` for a topic with no authored connection yet (FR-007) -- zero or one per topic, mirroring `image_asset`'s existing shape exactly rather than `standards`'s many-per-topic list. |

**Validation rules** (`services/content_artifact/validator.py`, same place
`image_asset`/`standards` schema rules already live):
- `career_connection`, if present, MUST be a mapping with non-empty string
  `career` and `description` keys (FR-002) -- same shape of check as
  `_validate_image_asset`'s `filename`/`alt_text` pair.
- No grade dependency (research.md Decision 2) -- unlike `standards`, a
  `career_connection` may be declared on a topic regardless of `grade`
  (including every `biology` topic, which has no `grade` at all).

**Persistence**: upsert-in-place at content-artifact load time, same as
every other scalar `Topic` column (`display_name`, `image_asset`, ...) --
not a delete-and-recreate table like `StandardsTag`/`PrerequisiteEdge`,
since this is a column on `Topic` itself, not a separate row.

## Modified: `LearnerProfile` (`backend/src/models/learner_profile.py`)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `career_connections_enabled` | `bool` | No (`server_default=sa.true()`) | New. One flag per learner row -- demo or real. Written by the demo learner itself (self-service, unauthenticated) or by a real learner's owning guardian (Clarifications) via the new endpoint below; never by an instructor. |

**Default**: `true` at the database level (spec Assumptions: visible
unless explicitly turned off). No backfill logic needed -- every existing
row (the one seeded demo learner, every already-created real learner)
picks up the column default identically; none has an existing explicit
choice to preserve.

## Derived (not stored): per-topic career connections on a mastery-state read

Computed inline in `mastery.py`'s existing handler, never persisted as its
own row -- same "derive, don't duplicate" discipline `coverage.py`
(spec 038) and `effective_mastery_for_review` (Milestone 22) already
established.

```python
class CareerConnectionOut(BaseModel):
    topic_id: str
    career: str
    description: str
```

`MasteryStateResponse.career_connections: list[CareerConnectionOut] = []`
-- one entry per topic in the requested subject that both (a) has an
authored `career_connection` and (b) belongs to a learner whose
`career_connections_enabled` is `true`. Empty list in every other case
(FR-006/FR-007) -- never an error, never a partial/placeholder entry.

## New endpoint pair (not a new table): the preference itself

`GET`/`PATCH /api/learners/{learner_id}/career-connections-preference`
read/write `LearnerProfile.career_connections_enabled` directly -- see
`contracts/api-changes.md`. No separate "preference" table; the column
above is the entire state.

## Entity relationship

```
Topic (1) ---- (0..1) career_connection [JSON column, not a row]
LearnerProfile (1) ---- (1) career_connections_enabled [bool column]
```

No foreign key, no join table -- both are columns on rows that already
exist for every other reason (content-artifact authoring, learner
creation), matching `image_asset`'s and `has_been_mastered`'s own shape
rather than `StandardsTag`'s separate-table shape.

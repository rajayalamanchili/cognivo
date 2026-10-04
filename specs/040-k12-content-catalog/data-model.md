# Data Model: Full K-12 Content Catalog

No schema change. Every entity below already exists (Milestones 1, 15,
038, 039) — this feature adds new *rows*, never a new table or column.
Documented here for traceability between `spec.md`'s Key Entities and the
actual rows this feature's content artifacts will produce at load time.

## Subject (existing — `src/models/subject.py`)

Two new rows:

| `subject_id` | `display_name` | `content_version` |
|---|---|---|
| `algebra-2` | Algebra II | `1.0.0` |
| `physics` | Physics | `1.0.0` |

## GradeBand (existing — `src/models/grade_band.py`)

New rows, one per `(subject_id, grade)` pair declared in each subject's
`grade_bands` list (research.md Decision 1):

- `algebra-2`: grades `9`, `10` (2 rows)
- `physics`: grades `9`, `10`, `11` (3 rows)

## Topic (existing — `src/models/topic.py`)

16 new rows total (8 per subject, research.md Decision 1), each carrying
every field the model already defines — no field is left at a reduced
bar relative to Algebra I/Biology:

- `subject_id`, `topic_id` (composite PK)
- `display_name`
- `grade` (9, 10, or 11 — FK to the subject's own `GradeBand` rows above)
- `prerequisites` (validated against this subject's own topic set only —
  research.md Decision 2)
- `skill_definition` (JSON: `summary`, `preferred_question_types`)
- `difficulty_calibration` (implicit via `easy`/`medium`/`hard` prose,
  validated by `_validate_difficulty_calibration`)
- `standards` (one or more real Common Core Math HS-strand or NGSS
  HS-Physical-Science codes — research.md Decision 3)
- `career_connection` (JSON: `career`, `description` — Milestone 039's
  existing shape)
- `order_index` (assigned at load time from authored order, same as every
  existing subject)
- `is_entry_level` (derived: `True` iff `prerequisites` is empty)
- `image_asset` (nullable — not required by any FR; left `NULL` unless a
  specific topic's authoring pass determines an image genuinely helps,
  matching Algebra I/Biology's own selective use of `image_asset`)
- `step_grading_enabled` (per-topic, set by the authoring pass per
  Milestone 16's existing criteria — a multi-step topic like
  `momentum-and-collisions` is a plausible candidate; not mandated by any
  FR here)

## Relationships

Identical to every existing subject: `Subject 1--* Topic`, `Subject 1--*
GradeBand`, `Topic.grade --FK--> GradeBand(subject_id, grade)`,
`Topic.prerequisites` is a same-subject topic-graph edge list validated
for acyclicity exactly as Algebra I/Biology's already are. No new
relationship shape is introduced.

## Validation rules

All pre-existing, reused unchanged (`src/services/content_artifact/
validator.py`): required-field completeness per topic (FR-002/FR-003),
prerequisite-graph acyclicity and same-subject-only resolution (FR-003,
research.md Decision 2), grade-vs-`grade_bands` all-or-nothing membership
(FR-009), standards-tag shape and graded-topic requirement (research.md
Decision 3), career-connection shape. No new validation rule is added by
this feature.

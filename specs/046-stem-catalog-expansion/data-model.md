# Data Model: STEM Catalog Expansion (Remaining Six Subjects)

Zero schema change -- every entity below already exists (Milestones 1,
15, 038, 039, 040), and this feature only adds new *rows*. Unlike
Milestone 040 (which added `ClassroomRoster.grade`), this feature finds
no engine gap requiring a new column.

## Subject (existing -- `src/models/subject.py`)

Six new rows:

| `subject_id` | `display_name` | `content_version` |
|---|---|---|
| `pre-algebra` | Pre-Algebra | `1.0.0` |
| `geometry` | Geometry | `1.0.0` |
| `chemistry` | Chemistry | `1.0.0` |
| `earth-science` | Earth Science | `1.0.0` |
| `elementary-math` | Elementary Math | `1.0.0` |
| `elementary-science` | Elementary Science | `1.0.0` |

## GradeBand (existing -- `src/models/grade_band.py`)

New rows, one per `(subject_id, grade)` pair declared in each subject's
`grade_bands` list (research.md Decision 1):

- `pre-algebra`: grades `6`, `7` (2 rows)
- `geometry`: grades `9`, `10` (2 rows)
- `chemistry`: grades `9`, `10` (2 rows)
- `earth-science`: grade `6` (1 row)
- `elementary-math`: grades `1`, `2`, `3`, `4`, `5` (5 rows -- the first
  rows below grade 6 in this catalog's history)
- `elementary-science`: grades `1`, `2`, `3`, `4`, `5` (5 rows)

All satisfy the existing `ck_grade_bands_grade_range` constraint
(`grade BETWEEN 1 AND 12`) with no change to that constraint.

## Topic (existing -- `src/models/topic.py`)

48 new rows total (8 per subject x 6 subjects, research.md Decision 1),
each carrying every field the model already defines -- no field left at
a reduced bar relative to the four existing subjects:

- `subject_id`, `topic_id` (composite PK)
- `display_name`
- `grade` (FK to the subject's own `GradeBand` rows above -- for
  Elementary Math/Science, the first `Topic.grade` values of 1-5 in
  this catalog)
- `prerequisites` (validated against this subject's own topic set only
  -- research.md Decision 2)
- `skill_definition` (JSON: `summary`, `preferred_question_types`)
- `difficulty_calibration` (`easy`/`medium`/`hard` prose, validated by
  `_validate_difficulty_calibration`)
- `standards` (one or more real Common Core Math or NGSS codes, in the
  per-grade or per-strand format appropriate to that subject's grade
  band -- research.md Decision 3)
- `career_connection` (JSON: `career`, `description` -- Milestone 039's
  existing shape)
- `order_index` (assigned at load time from authored order)
- `is_entry_level` (derived: `True` iff `prerequisites` is empty)
- `image_asset` (nullable -- left `NULL` unless a specific topic's
  authoring pass determines an image genuinely helps)
- `step_grading_enabled` (per-topic, set by the authoring pass per
  Milestone 16's existing criteria where a multi-step topic like
  `stoichiometry` is a plausible candidate; not mandated by any FR here)

## ClassroomRoster (existing -- `src/models/classroom_roster.py`)

No change. Its `grade` column (added by Milestone 040's FR-009) and
`services/roster/enrollment.py`'s `_check_grade_matches_subject` are
reused unchanged against each new subject's own `GradeBand` rows above
(FR-009, this spec).

## Relationships

Identical to every existing subject: `Subject 1--* Topic`, `Subject
1--* GradeBand`, `Topic.grade --FK--> GradeBand(subject_id, grade)`,
`Topic.prerequisites` is a same-subject topic-graph edge list validated
for acyclicity exactly as every prior subject's already is. No new
relationship shape is introduced.

## Validation rules

All pre-existing, reused unchanged (`src/services/content_artifact/
validator.py`): required-field completeness per topic (FR-002/FR-003),
prerequisite-graph acyclicity and same-subject-only resolution (FR-003,
research.md Decision 2), grade-vs-`grade_bands` all-or-nothing
membership, standards-tag shape and graded-topic requirement
(research.md Decision 3), career-connection shape. No new validation
rule is added by this feature -- including for the elementary subjects'
grades 1-5, which satisfy every existing check with no widening
(research.md Decision 6).

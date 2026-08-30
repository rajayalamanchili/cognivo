# Data Model: Multimodal Question Stimuli

## Content artifact schema addition (YAML, per-topic, optional)

```yaml
topics:
  - topic_id: graphing-linear-equations
    display_name: Graphing Linear Equations
    ...
    image_asset:
      filename: slope-intercept-diagram.png
      alt_text: >-
        A coordinate plane showing the line y = 2x + 1, with its
        y-intercept at (0, 1) and slope marked as a rise of 2 over a
        run of 1.
```

Physical file location: `backend/content/<subject_id>/images/<filename>`
(research.md §1). `image_asset` is optional per topic (FR-001) --
absent means the topic's questions are text-only, exactly as before
this milestone.

### `ValidatedTopic` (extends `services/content_artifact/validator.py`)

| Field | Type | Notes |
|---|---|---|
| `image_asset` | `dict \| None` | `{"filename": str, "alt_text": str}` if present. Schema-validated only (non-empty `filename`/`alt_text` strings) -- no filesystem access here (research.md §2). |

Validation rules (`validate_content_artifact`, schema-only):
- If `image_asset` is present, it MUST be a mapping.
- `filename` MUST be a non-empty string.
- `alt_text` MUST be a non-empty string (FR-003) -- missing or empty
  fails validation at load time, same error class
  (`ContentArtifactValidationError`) as every other schema violation.

Validation rules (`services/content_artifact/loader.py::load_content_artifact_file`,
filesystem-touching, run immediately after schema validation succeeds):
- The file `<artifact_dir>/images/<filename>` MUST exist.
- Its size MUST be <= 1,048,576 bytes (1 MB, FR-002).
- Its extension (case-insensitive) MUST be one of `.png`, `.jpg`,
  `.jpeg`, `.svg` (FR-002).
- Any failure raises `ContentArtifactValidationError` and MUST NOT set
  `Subject.validated_at` (same all-or-nothing contract every other
  load-time check already has).

## `Topic` (extends `models/topic.py`)

| Column | Type | Notes |
|---|---|---|
| `image_asset` | `JSON`, nullable | `{"filename": str, "alt_text": str}`, persisted verbatim from `ValidatedTopic.image_asset`. `NULL` for a topic with no image. |

New Alembic migration adds this single nullable column -- no backfill
needed, existing rows default to `NULL` (text-only, unchanged
behavior).

## `GeneratedQuestion` (extends `models/generated_question.py`)

| Column | Type | Notes |
|---|---|---|
| `image_url` | `Text`, nullable | e.g. `/content-images/algebra-1/slope-intercept-diagram.png`. Snapshotted from `Topic.image_asset` at generation time (research.md §5) -- stable even if the content artifact is later reloaded. `NULL` for a text-only question. |
| `image_alt_text` | `Text`, nullable | Snapshotted alongside `image_url`. Always non-`NULL` when `image_url` is non-`NULL`, and vice versa -- the two are set/unset together, never independently. |

Same migration as `Topic.image_asset` above adds both columns.

**Grading**: `answer_key`, `validation_status`, and every column
`services/mastery/grading.py::grade_answer` reads are completely
unaffected -- `image_url`/`image_alt_text` are display-only fields,
never read by any grading path (FR-004, SC-001).

## New shared helper: `services/content_artifact/image_asset.py`

```python
def content_image_url(subject_id: str, filename: str) -> str:
    return f"/content-images/{subject_id}/{filename}"
```

One function, no class -- used by both `agents/sequencing/agent.py`
(`NextQuestionResult`) and `services/quiz/session.py`
(`QuizQuestionResult`) so the URL convention is defined exactly once
(research.md §5).

## Result-carrier dataclasses (extended, not replaced)

- `agents/sequencing/agent.py::NextQuestionResult` gains `image_url: str | None`, `image_alt_text: str | None`.
- `services/quiz/session.py::QuizQuestionResult` gains the same two fields.

Both are populated from the already-fetched `topic.image_asset` at the
same point each dataclass is currently constructed -- no new database
query.

## API response shapes (extended)

- `routes/questions.py::NextQuestionOut`
- `routes/quiz.py::QuizQuestionOut` (shared by `QuizStartOut.question` and `QuizNextQuestionOut.question`)

Each gains:

| Field | Type | Notes |
|---|---|---|
| `image_url` | `str \| None` | Absent/`null` for a text-only question. |
| `image_alt_text` | `str \| None` | Required whenever `image_url` is set. |

No other response shape changes -- placement (`routes/placement.py`,
the Diagnostic Agent) is out of this milestone's scope (spec.md
Assumptions: this milestone depends only on the Assessment-Generation
Agent), so placement questions stay exactly as they are.

## Frontend types (extended)

- `frontend/src/services/api.ts`'s `NextQuestion` interface gains
  `image_url: string | null` and `image_alt_text: string | null`,
  mirroring the backend response shape 1:1 (no transformation layer).
- `frontend/src/components/QuestionCard.tsx` renders
  `<img src={question.image_url} alt={question.image_alt_text} />`
  immediately above the stem when `image_url` is set; renders nothing
  extra when it's `null` (User Story 1 Acceptance Scenario 3).

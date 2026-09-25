# Data Model: Math and Science Notation for Free-Text Answers

## No new entities, no schema change

Per `research.md` §1/§5, notation is plain Unicode text carried inside
fields that already exist and already accept arbitrary text:

| Existing shape | Where | Change |
|---|---|---|
| `GeneratedQuestion.answer_key` (JSON column) | `backend/src/models/generated_question.py` | None -- `rubric_criteria` descriptions are already free-form text and may already contain any Unicode character an author or the generation LLM produces. |
| `response` / `response_text` (`str`) | `POST /api/questions/{id}/answer`, validated by `validate_response_shape` (`grading.py`) | None -- `FREE_TEXT` already requires `str`. |
| `response_steps` (`list[str]`) | Same endpoint, `MULTI_STEP` | None -- already requires `list[str]`. |
| Pedagogical audit log (`AssessmentEvent`, `answer_submitted`) | `backend/src/models/assessment_event.py` | None -- stores the submitted text verbatim already. |

No migration, no new table, no new column.

## New frontend-only constant: notation character set

A small, static list of supported notation insertions (the toolbar's
button set), following the same pattern as `time-limit-options.ts`
(spec 022) -- a frontend constants file, not a backend entity or
database table, since the set is fixed and small:

- Precomposed fraction glyphs: ¼ ½ ¾ ⅓ ⅔ ⅕ ⅖ ⅗ ⅘ ⅙ ⅚ ⅐ ⅛ ⅜ ⅝ ⅞ ⅑ ⅒
- Superscript digits (exponents): ⁰ ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁻
- Subscript digits (chemical formulas): ₀ ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉
- The fraction-slash composition rule for any other numerator/
  denominator pair (superscript digits + U+2044 + subscript digits)

This constant has no relationship to any other entity -- it's a lookup
table for the toolbar UI only, not referenced by `answer_key`,
`response`, or any stored row.

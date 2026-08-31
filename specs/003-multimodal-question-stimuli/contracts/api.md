# API Contract: Multimodal Question Stimuli

**Feature**: `003-multimodal-question-stimuli` | **Date**: 2026-08-30

Extends `specs/001-domain-agnostic-core/contracts/api.md` and
`specs/005-adaptive-quiz/contracts/api.md` -- no new endpoints, no
changed request bodies. Every existing question-bearing response gains
two optional fields.

## `GET /api/learners/{learner_id}/next-question` (EXTENDED)

**Response** `200` -- unchanged shape, two new optional fields:
```json
{
  "question_id": "uuid",
  "topic_id": "graphing-linear-equations",
  "difficulty": "medium",
  "question_type": "multiple_choice",
  "stem": "Which point lies on the line shown in the diagram?",
  "options": ["(0, 1)", "(1, 3)", "(-1, -1)", "(2, 4)"],
  "image_url": "/content-images/algebra-1/slope-intercept-diagram.png",
  "image_alt_text": "A coordinate plane showing the line y = 2x + 1, with its y-intercept at (0, 1) and slope marked as a rise of 2 over a run of 1."
}
```

`image_url`/`image_alt_text` are both `null` when the selected topic
has no `image_asset` (the pre-existing, unchanged shape for every topic
that predates this milestone). They are never independently `null` --
either both present or both `null`.

## `POST /api/quizzes` and `GET /api/quizzes/{quiz_session_id}/next-question` (EXTENDED)

Same two-field addition, in the nested `question` object, for both
endpoints (they share the `QuizQuestionOut` response model).

## `POST /api/questions/{question_id}/answer` (UNCHANGED)

No request or response change. Grading, mastery update, and every
guardrail run exactly as documented in
`specs/001-domain-agnostic-core/contracts/api.md` and
`specs/007-grading-agent/contracts/api.md` -- FR-004 requires this
stay a no-op change, verified by SC-001.

## Static asset serving (NEW, not a backend endpoint)

`GET /content-images/{subject_id}/{filename}` is served by the
**frontend** Next.js Service's built-in static-file handling from its
own `public/` directory (`vercel.json`'s `services.frontend`) -- not a
FastAPI route, and not proxied through `/api/*` (research.md §1). A
request for an image that was never synced (e.g. a stale/removed
content artifact) returns Next.js's normal static-file `404`, the same
as any other missing file under `public/`.

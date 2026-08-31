# API Contract: Fine-Tuned Misconception Classifier

**Feature**: `020-misconception-classifier` (spec directory
`013-misconception-classifier`) | **Date**: 2026-08-31

Extends `specs/002-recommendation-agent/contracts/api.md`. No route is
removed or renamed; one existing response gains an optional field, and
one new internal cron route is added.

## `GET /api/learners/{learner_id}/recommendations` (existing, extended)

Same route, same request shape as spec 002. Each `weak_areas[]` entry
gains one new, optional field. Every other field is byte-for-byte
unchanged from spec 002's contract.

**Response** `200` (diff only -- see spec 002's contract for the full
shape):
```json
{
  "weak_areas": [
    {
      "topic_id": "linear-equations",
      "...": "...(unchanged spec-002 fields)",
      "misconception": {
        "misconception_id": "confuses-independent-dependent-variable",
        "description": "Consistently swaps which variable is manipulated vs. observed.",
        "confidence": 0.82,
        "evidence": [
          {
            "event_id": "uuid",
            "question_id": "uuid",
            "question_stem": "Which variable did you change in this experiment?",
            "answer_correct": false,
            "created_at": "2026-08-30T09:00:00Z"
          }
        ]
      }
    }
  ]
}
```

`misconception` is `null` when no classification exists for this
learner/topic yet, evidence is below the minimum threshold, or the
subject defines no taxonomy at all (FR-006, data-model.md) -- a client
already handling spec 002's response shape needs no change to keep
working; the field is purely additive.

## `GET /api/cron/classify-misconceptions` (new, internal)

Vercel Cron-triggered, mirroring the existing
`GET /api/cron/reset-demo-data` route exactly (`backend/src/api/routes/cron.py`):
`Authorization: Bearer $CRON_SECRET`, verified via `hmac.compare_digest`,
fails closed (`503`) if `CRON_SECRET` is unconfigured, `401` on
mismatch. Never a publicly documented or frontend-called route -- not
part of this project's learner/instructor-facing API surface.

**Response** `200`:
```json
{ "status": "ok", "classified_count": 14 }
```

Scans learner/topic pairs with newly-qualifying free-text evidence
since the last run (research.md §3), classifies each via the trained
per-subject classifier (research.md §1), and writes one
`misconception_classified` `AssessmentEvent` per pair that clears the
evidence (research.md §5) and confidence thresholds. Never raises on an
individual learner/topic failure -- a single bad classification is
logged and skipped, not allowed to fail the whole scheduled run (same
"don't let one bad row break a batch job" shape `reset_demo_data()`
and `batch_eval_questions.py` already follow).

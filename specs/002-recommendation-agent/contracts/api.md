# API Contract: Recommendation Agent

**Feature**: `002-recommendation-agent` | **Date**: 2026-08-16

Extends `specs/001-domain-agnostic-core/contracts/api.md`'s FastAPI
backend -- same Vercel Python Function, same stateless-per-request
model. All request/response bodies are JSON.

## `GET /api/learners/{learner_id}/recommendations`

Requests a weak-area report for a learner on one subject. Always
returns `200` -- "not enough data" and "broad review needed" are
reported *in* the response body (FR-004, FR-005), never as an error
status, matching this feature's Edge Cases ("must not overreact,"
"must not crash").

**Path params**: `learner_id` (UUID)

**Query params**: `subject_id` (`algebra-1` | `biology`)

**Response** `200`:
```json
{
  "subject_id": "algebra-1",
  "data_sufficiency": "confident",
  "broad_review_needed": false,
  "weak_areas": [
    {
      "topic_id": "linear-equations",
      "display_name": "Linear Equations",
      "p_mastery": 0.23,
      "evidence": [
        {
          "event_id": "uuid",
          "question_id": "uuid",
          "question_stem": "Solve for x: 2x + 3 = 11",
          "answer_correct": false,
          "prior_p_mastery": 0.3,
          "posterior_p_mastery": 0.23,
          "created_at": "2026-08-16T12:00:00Z"
        }
      ],
      "next_step": {
        "recommended_topic_id": "order-of-operations",
        "recommended_display_name": "Order of Operations",
        "reason": "prerequisite_gap",
        "prerequisite_chain": ["linear-equations", "order-of-operations"]
      }
    }
  ],
  "in_progress_topic_ids": ["fractions"],
  "not_yet_assessed_topic_ids": ["quadratic-equations"],
  "insufficient_data_topic_ids": ["exponents"]
}
```

**Field notes**:
- `data_sufficiency`: `"confident"` | `"insufficient_data"` (FR-004).
- `broad_review_needed`: `true` when >= 60% of confidently-assessed
  topics are struggling (FR-005) -- `weak_areas` is still populated in
  full even when this is `true` (the client decides how to render "top
  N" vs. "broad review" framing from this flag plus the full list;
  the API never truncates).
- `weak_areas`: may be an empty list. An empty list with
  `data_sufficiency = "confident"` means genuinely no struggling
  topics -- distinct from `data_sufficiency = "insufficient_data"`,
  which means the report couldn't reach a confident verdict at all.
- `in_progress_topic_ids`: topics in the "developing" band (mastery
  0.4-0.7, `update_count >= 3`) -- explicitly listed rather than
  omitted (FR-003a), distinct from both `weak_areas` and
  `not_yet_assessed_topic_ids`.
- `next_step.reason = "prerequisite_not_yet_assessed"` (not shown
  above): the prerequisite chain stopped at a topic with no
  `MasteryState` row at all (Edge Cases).

**Errors**: `404` if `subject_id` unknown or not `validated_at`
(matching `mastery.py`'s existing check). No error for a learner with
zero `MasteryState` rows at all -- that's `data_sufficiency =
"insufficient_data"` with every topic in `not_yet_assessed_topic_ids`
or `insufficient_data_topic_ids`, per FR-003/FR-004 (a request must
never fail just because a learner is new).

**Side effects**: Writes one `recommendation_report_generated` event,
one `weak_area_flagged` event per entry in `weak_areas`, and one
`next_step_suggested` event per entry's `next_step` (FR-008). Wrapped in
`traced_request()` for the Langfuse span (FR-008's tracing
requirement), matching every other agent-invoking route.

---

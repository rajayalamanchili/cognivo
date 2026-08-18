# API Contract: Learner Dashboard

**Feature**: `004-learner-dashboard` | **Date**: 2026-08-17

Extends `specs/001-domain-agnostic-core/contracts/api.md` and
`specs/002-recommendation-agent/contracts/api.md`'s FastAPI backend --
same Vercel Python Function, same stateless-per-request model. All
request/response bodies are JSON.

## `GET /api/subjects` (NEW)

Lists every subject with a validated content artifact in the platform,
so the frontend never hardcodes subject ids (research.md §4).

**Query params**: none

**Response** `200`:
```json
{
  "subjects": [
    { "subject_id": "algebra-1", "display_name": "Algebra I" },
    { "subject_id": "biology", "display_name": "Biology" }
  ]
}
```

**Field notes**: Ordered by `subject_id`. Only includes subjects with
`validated_at IS NOT NULL` (same gate as every other subject-scoped
endpoint) -- a subject whose content artifact failed load-time
validation never appears here.

**Errors**: None -- an empty `subjects` list is a valid (if degenerate)
response, not an error.

**Side effects**: None. Not wrapped in `traced_request()` -- no
LLM/ADK invocation.

---

## `GET /api/learners/{learner_id}/topic-priority-preview` (NEW)

Returns the Sequencing Agent's current top-priority next topic for one
subject, plus up to 3 likely-upcoming topics from the same ranking --
without generating an actual question (unlike
`GET /api/learners/{learner_id}/next-question`, which also calls the
Assessment-Generation Agent). Powers FR-003/FR-004's path visualization.

**Path params**: `learner_id` (UUID)

**Query params**: `subject_id` (`algebra-1` | `biology`)

**Response** `200`:
```json
{
  "subject_id": "algebra-1",
  "next_topic": {
    "topic_id": "linear-equations",
    "display_name": "Linear Equations",
    "band": "struggling",
    "p_mastery": 0.23
  },
  "upcoming_topics": [
    {
      "topic_id": "fractions",
      "display_name": "Fractions",
      "band": "unknown",
      "p_mastery": null
    },
    {
      "topic_id": "order-of-operations",
      "display_name": "Order of Operations",
      "band": "developing",
      "p_mastery": 0.55
    }
  ],
  "is_fallback": false
}
```

**Field notes**:
- `next_topic`: always present (research.md §1 -- reuses
  `select_next_topic`'s existing fallback guarantee).
- `upcoming_topics`: 0-3 entries. Fewer than 3 only when the ranked pool
  `next_topic` came from has fewer than 4 topics total (SC-006).
- `is_fallback`: `true` when no topic was strictly eligible (every
  topic mastered, or none has its prerequisites satisfied) and both
  `next_topic` and `upcoming_topics` are drawn from the fallback pool
  instead (mirrors `select_next_topic`'s existing `is_fallback` field).

**Errors**: `404` if `subject_id` unknown or not `validated_at`
(matching `mastery.py`/`recommendation.py`'s existing check). No error
for a learner with zero `MasteryState` rows -- `next_topic` resolves to
an entry-level topic exactly as `select_next_topic` already does for a
brand-new learner (FR-005).

**Side effects**: None -- no `AssessmentEvent` row written, no
Langfuse trace (research.md §3: this is an illustrative preview, not a
committed sequencing decision).

---

## Reused, unchanged endpoints

Called once per subject by the dashboard, with no contract change:

| Endpoint | Contract | Powers |
|---|---|---|
| `GET /api/learners/{learner_id}/mastery-state?subject_id=X` | `specs/001-domain-agnostic-core/contracts/api.md` | FR-001, and the "topics already assessed" half of FR-003 |
| `GET /api/learners/{learner_id}/recommendations?subject_id=X` | `specs/002-recommendation-agent/contracts/api.md` | FR-002 (verbatim display, including `data_sufficiency`/`broad_review_needed` framing) |

Both retain their existing side effects (the `/recommendations` call's
`AssessmentEvent` writes are unchanged and unconditional, per that
feature's own FR-008) and their existing failure behavior -- a
`/recommendations` call that raises is caught by the frontend per-
section fetch (research.md §5) and rendered as FR-007's "couldn't load"
state, without any change to the endpoint itself.

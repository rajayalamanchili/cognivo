# API Contract: Tutor Agent Answer-Shielding

**Feature**: `016-tutor-answer-shielding` | **Date**: 2026-09-04

This feature adds no new public endpoint. It changes the internal A2A
request `backend` sends to `tutor-agent/` (spec 012's contract,
`specs/012-tutor-agent/contracts/api.md`) and the fields returned by
the existing exchange-inspection endpoint. `POST /api/tutor/sessions`
and `POST /api/tutor/sessions/{session_id}/messages`'s request shapes,
status codes, and streaming behavior are all unchanged.

## Internal A2A request: `backend` -> `tutor-agent/` (MODIFIED)

`tutor_agent_client/client.py`'s `request_payload` gains one new,
optional key:

```json
{
  "question": "...",
  "subject_id": "biology",
  "retrieved_passages": [ /* unchanged */ ],
  "delegation_context": [ /* unchanged */ ],
  "shielding": {
    "open_question_stem": "...",
    "open_question_topic_id": "photosynthesis"
  }
}
```

- `shielding` is present only when `backend`'s shielding determination
  (`research.md` decision 2) found a match, or could not reach a
  confident determination (FR-010) -- its absence means "answer
  normally" (FR-005), same as today.
- `shielding.open_question_stem`/`open_question_topic_id` are the
  **only** information about the open question included -- its
  `answer_key` is never present anywhere in this payload
  (`research.md` decision 3, a hard constraint, not an
  instruction-only guarantee).
- When `shielding` is present, `tutor-agent/`'s response MUST be a
  hint that does not state a final answer value for the open question
  -- enforced by `agent.py`'s instruction (`TUTOR_INSTRUCTION_VERSION`
  `"v2"`), verified by `tutor-agent/tests/test_agent_instruction.py`.

## `GET /api/tutor/exchanges/{id}` (EXISTING, response fields ADDED)

No change to the endpoint's auth, path, or existing `ExchangeOut`
fields (`backend/src/api/routes/tutor.py`). Response gains:

```json
{
  "exchange_id": "...",
  "status": "completed",
  "question_text": "...",
  "answer_text": "...",
  "grounded": true,
  "retrieved_passages": [ /* unchanged */ ],
  "delegation_context": [],
  "shielded": true,
  "shielded_question_id": "..."
}
```

- `shielded` (`boolean`, always present, default `false` for
  pre-feature rows).
- `shielded_question_id` (`string | null`) -- present and non-null only
  when `shielded` is `true` and a specific open question was
  confidently identified as the trigger (`data-model.md`'s invariant).

This is SC-003's concrete verification surface: an inspector can call
this endpoint for a sampled exchange and determine, without asking the
Tutor Agent to explain itself, whether and why it was shielded.

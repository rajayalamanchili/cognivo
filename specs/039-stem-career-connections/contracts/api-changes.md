# API Contract Changes: STEM-Career Connections

One modified endpoint (additive field only) and one new endpoint pair.
No existing field changes type or meaning; no existing endpoint's auth
requirement or URL changes. Backward compatible -- an old frontend build
ignores the new `career_connections` field; the new settings/toggle UI
requires the new endpoint pair.

## New shared shape: `CareerConnectionOut`

```
topic_id: str
career: str
description: str
```

## Modified: `GET /api/learners/{learner_id}/mastery-state`

Auth unchanged -- still gated by `require_learner_ownership_if_real()`
(guardian-owns-this-real-learner, or demo/nonexistent no-op).

**`MasteryStateResponse`** gains:
```
career_connections: list[CareerConnectionOut]
```
Empty list when the learner's `career_connections_enabled` is `false`,
or when the requested subject has zero topics with an authored
`career_connection` (FR-006/FR-007) -- not an error, not an omitted
field. Server-computed, not a frontend-only filter: an old or a
tampered frontend still cannot cause this list to render content a
learner's preference says should be hidden.

## New: `GET /api/learners/{learner_id}/career-connections-preference`

Auth: `require_learner_ownership_if_real()` -- identical rule to the
endpoint above. Returns the demo learner's single shared preference with
no session required; returns a real learner's preference only to that
learner's owning guardian (`ForbiddenError` otherwise, matching every
other learner-scoped read).

```
enabled: bool
```

## New: `PATCH /api/learners/{learner_id}/career-connections-preference`

Same auth as the `GET` above -- this is the one write path Clarifications
settled on (demo learner self-service; real learner, guardian-only).

Request body:
```
enabled: bool
```

Response: same `{enabled: bool}` shape as the `GET` above, reflecting the
value just written.

## Unmodified: everything else

No change to `POST /api/learners` (learner creation), `placement.py`,
`quiz.py`, sequencing, or grading endpoints -- this feature adds one
read-mostly preference and one additive response field, nothing else.

# Phase 1 Data Model: Tutor Agent

All new tables live in the main `backend` database (Postgres/Neon) --
`tutor-agent/` owns no persistence of its own (research.md §2). New
Alembic migration(s) follow the existing naming convention
(`backend/alembic/versions/<hash>_<slug>.py`).

## `content_passage_embeddings`

One row per content-artifact field embedded for retrieval
(research.md §5). Regenerated on content-artifact reload, keyed so a
stale-version row is never served.

| Column | Type | Notes |
|---|---|---|
| `passage_id` | UUID, PK | |
| `subject_id` | text, FK -> `topics.subject_id` (composite w/ `topic_id`) | |
| `topic_id` | text, FK -> `topics.topic_id` (composite) | |
| `field` | enum: `skill_summary`, `difficulty_easy`, `difficulty_medium`, `difficulty_hard` | Which content-artifact field this passage came from (research.md §5) |
| `text` | text, not null | The raw passage text that was embedded, shown verbatim under US3's inspection |
| `embedding` | `vector(1024)` (`pgvector`, `voyage-3`'s output dimension) | Indexed with an HNSW or IVFFlat index (`pgvector` extension) for cosine similarity search |
| `content_version` | text, not null | Copied from `Subject.content_version` at embedding time -- a reload that bumps the version regenerates all of that subject's passages; stale-version rows are deleted, not left to accumulate |
| `created_at` | timestamptz, server default `now()` | |

**Uniqueness**: `(subject_id, topic_id, field, content_version)` --
regenerating the same version is idempotent (upsert), matching
`persist_content_artifact`'s existing idempotency guarantee.

**Populated by**: extending `services/content_artifact/loader.py`'s
existing load pipeline (or a sibling function called right after
`persist_content_artifact`) with an embedding-generation step sourced
from the same already-validated `ValidatedContentArtifact` object --
not re-derived from partially-persisted `Topic.skill_definition` JSON,
since `difficulty_calibration` isn't a persisted `Topic` column today.

## `tutoring_sessions`

A bounded conversation (spec.md's "Tutoring Session" entity).

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID, PK | |
| `learner_id` | UUID, FK -> `learner_profiles.learner_id`, not null | The learner the session is about -- real (guardian-mediated) or the seeded demo learner, per FR-001 |
| `guardian_id` | UUID, FK -> `real_guardian_accounts.guardian_id`, nullable | Set when a real guardian's session opened this Tutoring Session on the learner's behalf; null for the demo learner path |
| `subject_id` | text, FK -> `subjects.subject_id`, not null | A session is scoped to one subject, matching every other per-subject session concept in this codebase (`quiz_sessions`, mastery state) |
| `started_at` | timestamptz, server default `now()` | |
| `status` | enum: `active`, `ended` | No hard expiry logic required by this spec; `ended` is a simple learner/guardian-initiated close |

**Uniqueness**: A partial unique index on `(learner_id, subject_id)
WHERE status = 'active'` enforces FR-014's "at most one active session
per learner per subject" at the database level, not just in
application code (research.md §8). `POST /api/tutor/sessions` is
get-or-create against this constraint.

## `tutor_exchanges`

One question-answer turn (spec.md's "Tutor Exchange" entity) --
append-only within a session.

| Column | Type | Notes |
|---|---|---|
| `exchange_id` | UUID, PK | |
| `session_id` | UUID, FK -> `tutoring_sessions.session_id`, not null | |
| `question_text` | text, not null | The learner's raw question |
| `answer_text` | text, nullable until streaming completes | Final assembled answer; written once streaming finishes (FR-005/FR-007 need the complete text logged, not just what the learner saw live) |
| `grounded` | boolean, not null | Whether FR-002/FR-004's retrieval step found and used at least one sufficiently relevant passage -- directly what SC-002 measures across a test set |
| `retrieved_passage_ids` | `UUID[]` (Postgres array) | FKs into `content_passage_embeddings.passage_id`, in the order presented to the Tutor Agent -- the raw material for FR-003/US3 |
| `delegation_context` | JSON, nullable | The mastery/weak-area (and, where applicable, grading) context the backend bundled into the Tutor Agent's request per research.md §2/§3 -- what FR-006 required and what US3 inspects to answer "why was I told this" |
| `created_at` | timestamptz, server default `now()` | |

**In-flight concurrency (FR-015)**: `answer_text IS NULL` on a
session's most recent `TutorExchange` row means that exchange is still
streaming. `POST /api/tutor/sessions/{id}/messages` checks for such a
row before creating a new one and rejects (`409`) rather than creating
a second in-flight row for the same session (research.md §8) -- no new
column needed; `answer_text`'s existing nullability is the single
source of truth for "is this exchange done."

## Rate limiting (FR-013)

No new table -- `check_tutor_rate_limit` (mirrors
`services/grading_client/guardrails.py`'s `check_rate_limit`) counts a
learner's `tutor_exchanges` rows with `created_at` in the trailing
10-minute window (queried directly off `tutor_exchanges` joined
through `tutoring_sessions.learner_id`, not through
`assessment_events`, since no `GeneratedQuestion`-shaped join target
applies here). Same `RATE_LIMIT_MAX_SUBMISSIONS = 20` /
`RATE_LIMIT_WINDOW_MINUTES = 10` constants as the existing
implementation (research.md §8).

## Audit log integration

No new audit-log table -- reuses the existing `assessment_events`
append-only mechanism (Constitution Principle V), adding one new
`AssessmentEventType` value:

- `TUTOR_EXCHANGE_COMPLETED = "tutor_exchange_completed"` -- written
  once a `TutorExchange` completes, `topic_id` left null (this event
  spans a conversational turn, not necessarily one topic, matching the
  existing precedent `recommendation_report_generated` already set for
  report-shaped events), `payload` holding `exchange_id`,
  `retrieved_passage_ids`, `grounded`, and a summary of
  `delegation_context` -- reconstructible detail for FR-007 without a
  second, parallel audit mechanism.

## Relationships

```text
Subject 1--* Topic 1--* ContentPassageEmbedding
LearnerProfile 1--* TutoringSession 1--* TutorExchange
RealGuardianAccount 0..1--* TutoringSession
TutorExchange *--* ContentPassageEmbedding   (via retrieved_passage_ids)
TutorExchange 1--1 AssessmentEvent           (tutor_exchange_completed)
```

## Validation rules (from Functional Requirements)

- A `TutorExchange` with `grounded = false` MUST still have
  `retrieved_passage_ids = []` (not a partial/low-confidence match
  silently treated as grounded) -- enforces FR-004's honesty
  requirement at the data level, not just in prompt wording.
- `content_passage_embeddings` rows for a superseded `content_version`
  MUST be deleted, not merely ignored by retrieval queries -- keeps
  retrieval from ever surfacing stale passage text after a content
  reload (mirrors `persist_content_artifact`'s existing
  upsert-not-accumulate discipline).
- A `tutoring_sessions` row MUST satisfy the `(learner_id, subject_id)
  WHERE status = 'active'` uniqueness constraint at all times -- a
  concurrent double-open request must fail one write and let the other
  win, never leave two active rows for the same pair (FR-014).
- `POST /api/tutor/sessions/{id}/messages` MUST NOT create a second
  `TutorExchange` row with `answer_text IS NULL` while one already
  exists for that session (FR-015) -- checked immediately before
  insert, in the same transaction, to close the race between the check
  and the write.

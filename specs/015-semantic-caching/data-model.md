# Phase 1 Data Model: Semantic Caching

Two new tables. No changes to any existing table's schema (`GeneratedQuestion`, `AssessmentEvent`, `Subject` are all read-only inputs to this feature -- see research.md §2-§4 for why no column needed to be added to any of them).

## §1. `question_generation_cache`

The rotating pool backing User Story 1 (FR-001, FR-005, FR-006, FR-012).

| Column | Type | Notes |
|---|---|---|
| `cache_entry_id` | UUID, PK | `default=uuid.uuid4`, same convention as `GeneratedQuestion.question_id` |
| `subject_id` | str, NOT NULL | Part of the lookup key |
| `topic_id` | str, NOT NULL | Part of the lookup key. `ForeignKeyConstraint(["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"])`, same composite-FK pattern as `GeneratedQuestion`/`AssessmentEvent` |
| `difficulty` | `DifficultyBand` enum, NOT NULL | Part of the lookup key |
| `content_version` | str, NOT NULL | `Subject.content_version` at creation time (FR-005). Part of the lookup key |
| `generation_prompt_version` | str, NOT NULL | `assessment_gen.agent.GENERATION_PROMPT_VERSION` at creation time (FR-005). Part of the lookup key |
| `question_type` | `QuestionType` enum, NOT NULL | Mirrors `GeneratedQuestion.question_type` |
| `stem` | Text, NOT NULL | Mirrors `GeneratedQuestion.stem` |
| `options` | JSON, nullable | Mirrors `GeneratedQuestion.options` |
| `answer_key` | JSON, NOT NULL | Mirrors `GeneratedQuestion.answer_key` (rubric for free-text, correct option/value for structured) |
| `image_url` / `image_alt_text` | Text, nullable | Mirrors `GeneratedQuestion`'s image fields (Milestone 10) |
| `question_signature` | Text, NOT NULL, indexed | `sha256(stem + canonical_json(answer_key rubric or options))` -- research.md §3's cross-learner grading-cache key. Computed once at insert |
| `created_at` | timestamptz, NOT NULL, `server_default=func.now()` | Freshness-window anchor (FR-012's 24h TTL is `created_at > now() - interval '24 hours'` at read time, never a stored expiry column) |
| `last_served_at` | timestamptz, nullable | Set on every hit; informational only (not part of eviction logic, which is purely oldest-`created_at`-first per FR-012) |
| `hit_count` | int, NOT NULL, `default=0` | Incremented on every hit; feeds the US3 hit-rate script alongside `AssessmentEvent` payloads |

**Indexes**: composite index on `(subject_id, topic_id, difficulty, content_version, generation_prompt_version, created_at)` -- the exact lookup + freshness-filter shape §2 of research.md queries on every request.

**Validation rules**: A row is only ever inserted after `assessment_gen.agent._validate_draft` has already passed (research.md §2) -- this table never stores an unvalidated draft. At most 5 rows may exist for a given `(subject_id, topic_id, difficulty, content_version, generation_prompt_version)` tuple at any time; the write path enforces this by deleting the oldest row(s) beyond 5 immediately after an insert, in the same transaction.

**Lifecycle**: insert (miss) → served 0+ times (hit, `hit_count`/`last_served_at` updated) → becomes stale after 24h (still present, just no longer matched by the read-time filter) → eventually superseded permanently once its `content_version`/`generation_prompt_version` no longer matches the live version (inert, no cleanup job in this milestone -- research.md §5).

## §2. `grading_response_cache`

Backing User Story 2 (FR-002, FR-003, FR-004, FR-005, FR-006, FR-009).

| Column | Type | Notes |
|---|---|---|
| `cache_entry_id` | UUID, PK | Same convention as above |
| `question_signature` | Text, NOT NULL, indexed | Same hash as §1 -- the "same question" key across different learners' distinct `GeneratedQuestion` rows (research.md §3) |
| `answer_embedding` | `Vector(1024)`, NOT NULL | `pgvector`, same dimension/model as `ContentPassageEmbedding.embedding` (`content_passage_embedding.py:16`) -- produced by `misconception/embed.py::embed_answer(question_stem, answer_text)`, reused unchanged |
| `grading_logic_version` | str, NOT NULL | `grading_agent.agent.GRADING_LOGIC_VERSION` at creation time. Part of the match filter (FR-006) |
| `correct` | bool, NOT NULL | Mirrors `GradingResult.correct` |
| `graduated_score` | float, NOT NULL | Mirrors `GradingResult.graduated_score` |
| `criteria_met` | JSON, NOT NULL | Mirrors `GradingResult.criteria_met` (list[str]) |
| `criteria_missed` | JSON, NOT NULL | Mirrors `GradingResult.criteria_missed` (list[str]) |
| `created_at` | timestamptz, NOT NULL, `server_default=func.now()` | No TTL semantics for this table (research.md §6) -- informational only |
| `last_served_at` | timestamptz, nullable | Set on every hit |
| `hit_count` | int, NOT NULL, `default=0` | Same purpose as §1 |

**What is deliberately NOT stored**: the learner's raw answer text, or any `learner_id`/answer-submission identifier from the request that created the entry (FR-009) -- only its embedding, which is not reversible to the original text, and the computed grade. A grading-cache hit response is built purely from this row's `correct`/`graduated_score`/`criteria_met`/`criteria_missed` columns; nothing from the original submitter's request ever reaches the new learner.

**Indexes**: composite index on `(question_signature, grading_logic_version)` for the hard filter; an IVFFlat or HNSW `pgvector` index on `answer_embedding` for the cosine-distance ranking, scoped by the same composite filter (matches `content_passage_embedding.py`'s existing indexing approach for its own `pgvector` column).

**Validation rules**: A row is only ever inserted after a real `grade_free_text_answer(...)` A2A call has returned and been validated (`grading_client/client.py`'s existing `_validate_and_parse`, FR-002) -- never a cache-hit result re-inserted as if it were a new grading. Matching requires `question_signature` AND `grading_logic_version` to match exactly (FR-004, FR-006); cosine distance to the closest matching row must be `<= 0.15` (research.md §3's initial threshold, pending eval validation) for a hit.

**Lifecycle**: insert (miss) → served 0+ times (hit) → becomes permanently unreachable once `grading_logic_version` bumps (FR-006) -- no expiry, no eviction, accepted long-term growth (research.md §6).

## §3. Reused entities (no schema change)

- **`AssessmentEvent`** (`assessment_event.py`): existing `payload` JSON column gains two new keys, `served_from_cache: bool` and `cache_miss_reason: str | None`, on the *existing* event writes that already fire on every question-generation and grading request that has one (`NEXT_TOPIC_SELECTED`, `ANSWER_SUBMITTED`) -- no new `AssessmentEventType` member, no new table (research.md §4). This is how FR-013's "own full pedagogical audit-log entry" requirement is met: the entry was always going to exist; caching only adds two keys to its payload. The spec's "Cache Hit/Miss Outcome" is these two keys, read back in aggregate for User Story 3 -- it is not a second, independently-stored record.
- **`GeneratedQuestion`**: unchanged. Every request still produces its own per-learner row, populated from either a cache-hit draft or a freshly generated one -- caching is invisible at this table's level, which is exactly what SC-003 requires. For the in-quiz question-generation path specifically, which records no dedicated `AssessmentEvent` even for a fresh call (spec.md's Edge Cases), this row -- unchanged by caching -- plus its own Langfuse trace on a hit *is* FR-013's audit-log requirement for that path (spec.md's FR-013 clarification).
- **Langfuse traces**: not a database entity, but worth noting here -- a cache hit produces a new Langfuse generation-shaped span (`observability/tracing.py::record_cache_hit_trace`, research.md §4) tagged with zero token usage, findable in Langfuse by the same `learner_id`/`session_id` metadata every other trace in this project already carries.

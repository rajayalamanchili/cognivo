# Phase 1 Data Model: Moderation & Shielding Classification Caching

Two new tables, plus two new columns on the existing `tutor_exchanges` table. No changes to any other existing table.

## §1. `moderation_cache`

Backing User Story 1 (FR-001, FR-003, FR-005, FR-006, FR-008).

| Column | Type | Notes |
|---|---|---|
| `cache_entry_id` | UUID, PK | `default=uuid.uuid4`, same convention as the existing cache tables |
| `text_signature` | Text, NOT NULL, indexed | `compute_text_signature(normalized submitted text)` (research.md §2) -- the exact-match lookup key. Part of the lookup key |
| `moderation_instruction_version` | str, NOT NULL | `moderation.MODERATION_INSTRUCTION_VERSION` at creation time (FR-005). Part of the lookup key |
| `allowed` | bool, NOT NULL | The cached verdict -- mirrors `check_moderation`'s own return value exactly |
| `created_at` | timestamptz, NOT NULL, `server_default=func.now()` | No TTL semantics (spec.md Assumptions: no eviction in this milestone) -- informational only |
| `last_served_at` | timestamptz, nullable | Set on every hit |
| `hit_count` | int, NOT NULL, `default=0` | Incremented on every hit; feeds `cache_hit_rate_report.py`'s moderation rate alongside the `AssessmentEvent` payload flags (§3) |

**What is deliberately NOT stored**: the raw submitted answer text (FR-008) -- only its signature, which is not reversible to the original text. A hit is served purely from `allowed`; nothing about the original submitter's request ever reaches a different learner's response.

**Indexes**: composite index on `(text_signature, moderation_instruction_version)` -- the exact lookup shape `moderation_cache/cache.py` queries on every submission.

**Validation rules**: A row is only ever inserted after a real `check_moderation(...)` call has returned (never a cache-hit result re-inserted as if it were fresh). Matching requires `text_signature` AND `moderation_instruction_version` to match exactly (FR-003, FR-005, FR-006) -- no partial or fuzzy match.

**Lifecycle**: insert (miss) → served 0+ times (hit, `hit_count`/`last_served_at` updated) → becomes permanently unreachable once `moderation_instruction_version` bumps (FR-005) -- no expiry, no eviction, accepted long-term growth (mirrors spec 015's identical acceptance for its grading cache, research.md §6).

## §2. `shielding_classification_cache`

Backing User Story 2 (FR-002, FR-003, FR-004, FR-005, FR-006, FR-008).

| Column | Type | Notes |
|---|---|---|
| `cache_entry_id` | UUID, PK | Same convention as above |
| `pair_signature` | Text, NOT NULL, indexed | `compute_paired_signature(normalized open_question_stem, normalized tutor_question)` (research.md §2), order-sensitive. Part of the lookup key -- this is what makes matching per-question (FR-004): two different open-question stems paired with the same tutor message produce two different signatures |
| `shielding_classification_instruction_version` | str, NOT NULL | `shielding.SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION` at creation time (FR-005). Part of the lookup key |
| `matches` | bool, NOT NULL | The cached verdict -- mirrors `classify_match`'s own return value exactly |
| `created_at` | timestamptz, NOT NULL, `server_default=func.now()` | No TTL semantics -- informational only |
| `last_served_at` | timestamptz, nullable | Set on every hit |
| `hit_count` | int, NOT NULL, `default=0` | Incremented on every hit; feeds `cache_hit_rate_report.py`'s shielding rate alongside `tutor_exchanges`' new columns (§3) |

**What is deliberately NOT stored**: the raw open-question stem text or raw tutor-message text (FR-008) -- only their combined signature. A hit is served purely from `matches`.

**Indexes**: composite index on `(pair_signature, shielding_classification_instruction_version)`.

**Validation rules**: A row is only ever inserted after a real `classify_match(...)` call has returned successfully (a `ClassificationFailedError` is never cached -- `determine_shielding`'s existing FR-010 fail-safe path is unaffected by this cache either way). Matching requires `pair_signature` AND `shielding_classification_instruction_version` to match exactly (FR-003, FR-004, FR-005, FR-006).

**Lifecycle**: insert (miss) → served 0+ times (hit) → becomes permanently unreachable once `shielding_classification_instruction_version` bumps (FR-005) -- no expiry, no eviction.

## §3. Extended entity: `tutor_exchanges` gains two columns

| Column | Type | Notes |
|---|---|---|
| `shielding_checks_total` | int, NOT NULL, `default=0` | How many `classify_match`-shaped checks `determine_shielding` performed for this exchange (one per open question at the time, up to `MAX_OPEN_QUESTIONS`) |
| `shielding_checks_from_cache` | int, NOT NULL, `default=0` | How many of those checks were served from `shielding_classification_cache` instead of a fresh model call |

**Rationale**: `determine_shielding` calls its match classifier once per open question, so a single per-exchange hit/miss boolean (the shape `AssessmentEvent`'s `served_from_cache` key uses for a 1-to-1 request) can't represent a request that made several independent cache checks with potentially mixed outcomes. A count pair is the smallest addition that still lets `cache_hit_rate_report.py` compute an accurate per-check (not per-exchange) hit rate for User Story 3, without introducing a new per-check audit-log row FR-010 explicitly avoids.

**Both default to 0** so every pre-existing `tutor_exchanges` row (before this migration) reads as "zero checks performed" rather than NULL -- correct, since no exchange before this feature ever performed a cached check.

## §4. Reused entities (no schema change beyond §3)

- **`AssessmentEvent`** (`assessment_event.py`): existing `payload` JSON column gains two new keys, `moderation_served_from_cache: bool` and `moderation_cache_miss_reason: str | None`, on the existing `FREE_TEXT_SUBMISSION_REJECTED` (moderation-block path) and `ANSWER_SUBMITTED` (moderation-allow path, both free-text and multi-step submissions) event writes -- no new `AssessmentEventType` member, no new table. Named with a `moderation_` prefix specifically so they don't collide with spec 015's existing `served_from_cache`/`cache_miss_reason` keys already present on the same `ANSWER_SUBMITTED` payload for the (separate) grading cache.
- **Langfuse traces**: a cache hit on either new cache type produces a `record_cache_hit_trace(..., cache_type="moderation" | "shielding", ...)` call, identical in shape to spec 015's existing usage for `cache_type="question_generation" | "grading"` -- no change to that function.

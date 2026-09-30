# Phase 0 Research: Moderation & Shielding Classification Caching

## §1. Storage mechanism: in-database Postgres, no `pgvector`

**Decision**: Two new plain Postgres tables (`moderation_cache`, `shielding_classification_cache`), no vector column, no `pgvector` index.

**Rationale**: Spec 026 FR-003 already settled on exact-signature (hashed, normalized-text) matching rather than semantic/embedding similarity -- unlike spec 015's grading cache, there's no equivalence-check safety net to make an approximate match safe for these two booleans. An exact match needs only a hashed text column with a plain b-tree index, which is materially simpler than spec 015's `pgvector`/HNSW setup. This is a direct consequence of the spec decision, not a new one made here.

**Alternatives considered**: Redis/Upstash (rejected for the same reason `tech-stack.md`/spec 015 research.md §1 already rejected it for the other two caches -- no new infra dependency for a Vercel-serverless deployment when Postgres already does the job). An in-memory process-local cache (rejected outright -- Constitution Principle IX: no in-memory state assumed across a stateless serverless function's invocations).

## §2. Signature computation: extend `cache_common/signature.py`

**Decision**: Add two pure functions alongside the existing `compute_question_signature`:

```python
def compute_text_signature(text: str) -> str:
    """sha256 of a normalized (trimmed, casefolded) text -- the
    moderation-cache lookup key."""

def compute_paired_signature(first: str, second: str) -> str:
    """sha256 of two normalized texts, order-sensitive -- the
    shielding-cache lookup key (open_question_stem, tutor_question)."""
```

**Rationale**: Same module, same hashing approach (`hashlib.sha256` over a canonical string) `compute_question_signature` already establishes -- no new dependency, no new pattern to learn. Normalization (trim + casefold) is deliberately minimal: FR-003 requires exact-signature matching, not fuzzy matching, so normalization only absorbs incidental whitespace/case differences a learner's client might introduce (e.g. trailing newline from a textarea), never wording differences.

**Alternatives considered**: A single generic `compute_signature(*parts: str) -> str`. Rejected as a premature abstraction for two call shapes -- `compute_text_signature` (moderation) takes one string, `compute_paired_signature` (shielding) takes two order-sensitive strings tied to FR-004's per-question scoping; collapsing them into one variadic function would just move the "how many parts, in what order" question into every call site instead of the function signature.

## §3. Cache-aware wrapper shape: mirrors `grading_cache/cache.py`'s injection pattern exactly

**Decision**:

```python
# src/services/moderation_cache/cache.py
async def get_or_check_moderation(
    db: Session, *, text: str, instruction_version: str,
    check_fn: Callable[[], Awaitable[bool]],
) -> tuple[bool, CacheOutcome]: ...

# src/services/shielding_cache/cache.py
async def get_or_classify_match(
    db: Session, *, open_question_stem: str, tutor_question: str,
    instruction_version: str, classify_fn: Callable[[], Awaitable[bool]],
) -> tuple[bool, CacheOutcome]: ...
```

Both reuse `cache_common/outcome.py`'s existing `CacheOutcome` dataclass unchanged, and both fail open on any lookup/write exception exactly as `question_cache/cache.py`/`grading_cache/cache.py` already do (FR-006) -- `check_fn`/`classify_fn` still runs on any storage failure, never raised to the caller.

**Call-site wiring requires no change to `moderation.py` or `shielding.py` themselves**:
- `questions.py`'s two `check_moderation(...)` call sites become `get_or_check_moderation(db, text=..., instruction_version=MODERATION_INSTRUCTION_VERSION, check_fn=functools.partial(check_moderation, text, session_service=...))`.
- `shielding.py`'s `determine_shielding` already takes an injected `match_fn` parameter (its own existing design, built for exactly this kind of wrapping -- see its docstring). `tutor/session.py`'s real call site changes its `functools.partial(classify_match, session_service=...)` binding to instead bind `functools.partial(get_or_classify_match, db=db, instruction_version=SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION, classify_fn=functools.partial(classify_match, session_service=...))`. `determine_shielding`'s own lookup/tie-break/fail-safe logic (FR-010) is completely unaware caching exists underneath it.

**Rationale**: Both existing caches, and `shielding.py`'s own match_fn injection, already establish "wrap the function, don't modify it" as this codebase's caching pattern (spec 015 research.md §2/§3; `shielding.py`'s own docstring explicitly calls out this shape as reusable). Following it here means zero changes to two guardrail modules a security-relevant control lives in -- lower review risk than touching their internals.

**Alternatives considered**: Decorating `check_moderation`/`classify_match` directly with a caching decorator. Rejected: `classify_match` is called up to 10 times per `determine_shielding` invocation with different arguments each time (one per open question) -- a decorator on the function itself would need the exact same keyword-based signature awareness a wrapper function already has, with no simplification benefit, and would touch a file whose docstring already documents the injection seam as the intended extension point.

## §4. Observability: reuse `record_cache_hit_trace` unchanged; extend `TutorExchange` and existing payloads instead of inventing new audit events

**Decision**: `observability/tracing.py::record_cache_hit_trace` already takes a `cache_type` string parameter -- call it with `cache_type="moderation"` / `cache_type="shielding"` on each hit, no code change needed to that function.

For the pedagogical audit trail (FR-009/FR-010, Constitution Principle V), reuse whatever record already exists on each code path rather than inventing a new one:
- **Moderation**: `questions.py`'s existing `FREE_TEXT_SUBMISSION_REJECTED` event (block path) and `ANSWER_SUBMITTED` event (allow path, both free-text and multi-step) each gain two new payload keys, `moderation_served_from_cache: bool` and `moderation_cache_miss_reason: str | None` -- same shape as spec 015's `served_from_cache`/`cache_miss_reason` grading keys already on `ANSWER_SUBMITTED`, just prefixed `moderation_` to avoid colliding with them on the same payload.
- **Shielding**: no per-check event exists today or is being added (spec.md's FR-010 explicitly disclaims inventing one) -- `determine_shielding` calls its match classifier once per open question (up to 10, `MAX_OPEN_QUESTIONS`), so a single boolean on the one `TutorExchange` row per tutor message can't represent potentially-mixed hit/miss outcomes across those calls. `TutorExchange` instead gains two small integer columns, `shielding_checks_total` and `shielding_checks_from_cache` (both `NOT NULL DEFAULT 0`), incremented by `determine_shielding`'s caller as each `match_fn` call resolves. This is the shielding equivalent of "two new keys on an existing record" -- no new table, no new per-check row.

**Rationale**: Directly extends spec 015's own precedent (data-model.md §3: "two new payload keys... not a second, independently-stored record") to a case (shielding) where the existing record is a table row instead of a JSON payload, and where the 1-to-many (one exchange, many checks) shape needs a count pair instead of a single flag.

## §5. `pyproject.toml`/dependency impact

**Decision**: None. `hashlib` is stdlib (already used by `cache_common/signature.py`); no new package.

## §6. Migration

**Decision**: One Alembic migration, chained off the current head (`824e2c5a0678`), adding both new tables plus the two new `tutor_exchanges` columns. Mirrors spec 015's `8e384ff83a4c_semantic_caching_tables.py` in shape (a single migration for a self-contained caching feature) but adds a column-alteration to an existing table too, which 015 didn't need.

## §7. Verification mechanism for SC-001/SC-002

**Decision**: A new script, `scripts/guardrail_cache_load_test.py`, not an extension of `scripts/cache_load_test.py`.

**Rationale**: `cache_load_test.py` is purpose-built around question-generation/grading's specific fakes (a patched `embed_answer` producing deterministic pseudo-embeddings, `GeneratedQuestionDraft`/`GradingResult` shapes) -- none of that machinery applies here (no embeddings at all, per §1). A new, much smaller script (fake `check_fn`/`classify_fn` returning a fixed verdict, replaying a mix of exact-duplicate and unique-text traffic, run with `--no-cache` for the same before/after comparison) is less code than bending the existing script around a fundamentally different matching strategy, while keeping the same "no live server, direct function calls, run twice and diff" shape spec 015 established.

## §8. Hit-rate report

**Decision**: Extend the existing `scripts/cache_hit_rate_report.py` (add `"free_text_submission_rejected"`-and-`"answer_submitted"`-sourced `moderation` rate, and a `tutor_exchanges`-sourced `shielding` rate) rather than a new script -- this one *is* a natural extension, since it already aggregates exactly the kind of existing-record payload flags this feature adds, just from a new event type and a new table for the shielding case instead of `AssessmentEvent` alone.

## §9. Test layout

**Decision**: `backend/tests/unit/caching/test_moderation_cache.py` and `test_shielding_cache.py` (signature scoping, instruction-version-bump-as-miss, fail-open), alongside the existing `test_question_cache.py`/`test_grading_cache.py` in the same directory. Integration coverage added to a new `backend/tests/integration/test_guardrail_caching.py` (hit/miss parity mirroring spec 015's SC-003, instruction-version invalidation mirroring SC-004) rather than folding into `test_semantic_caching.py`, keeping that file scoped to the two cache types its name already promises.

"""Cross-learner cache in front of the moderation guardrail's model call
(spec 026 FR-001/FR-003/FR-005/FR-006/FR-008, research.md §2/§3).

Exact-signature match only (FR-003) -- unlike `grading_cache/cache.py`,
a boolean allow/block verdict needs no equivalence-check safety net, so
a lookup hit is served directly.
"""

import datetime
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from src.models.moderation_cache import ModerationCache
from src.services.cache_common.outcome import CacheOutcome
from src.services.cache_common.signature import compute_text_signature


async def get_or_check_moderation(
    db: Session,
    *,
    text: str,
    instruction_version: str,
    check_fn: Callable[[], Awaitable[bool]],
) -> tuple[bool, CacheOutcome]:
    """Serves a cached allow/block verdict for an exact (normalized) text
    match at the current `instruction_version`, or calls `check_fn()` and
    stores its result as a new row.

    Fails open (FR-006): any lookup exception is a miss
    (`reason="storage_failure"`) -- `check_fn()` still runs so the
    request itself always succeeds. A failed write-back is swallowed the
    same way; caching is best-effort, never request-blocking.
    """
    text_signature = compute_text_signature(text)

    storage_failed = False
    row: ModerationCache | None = None
    try:
        row = (
            db.query(ModerationCache)
            .filter(
                ModerationCache.text_signature == text_signature,
                ModerationCache.moderation_instruction_version == instruction_version,
            )
            .first()
        )
    except Exception:  # noqa: BLE001 -- any lookup failure fails open (FR-006)
        storage_failed = True

    if row is not None:
        row.hit_count += 1
        row.last_served_at = datetime.datetime.now(datetime.UTC)
        db.flush()
        return row.allowed, CacheOutcome(hit=True, cache_entry_id=row.cache_entry_id)

    miss_reason = "storage_failure" if storage_failed else "no_matching_entry"

    allowed = await check_fn()

    try:
        new_row = ModerationCache(
            text_signature=text_signature,
            moderation_instruction_version=instruction_version,
            allowed=allowed,
        )
        db.add(new_row)
        db.flush()
    except Exception:  # noqa: BLE001 -- best-effort write, never blocks the request (FR-006)
        pass

    return allowed, CacheOutcome(hit=False, reason=miss_reason)

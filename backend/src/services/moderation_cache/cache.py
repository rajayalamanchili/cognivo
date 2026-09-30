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
    same way; caching is best-effort, never request-blocking. Every
    risky operation runs inside its own `db.begin_nested()` SAVEPOINT
    (Principle IX/FR-006 PR feedback): on Postgres, a failed statement
    aborts the whole transaction, so a bare `except` with no rollback
    would leave `db` -- the caller's own shared request session, not a
    private one -- unusable for every later query/commit in the same
    request. Rolling back only to the SAVEPOINT keeps the rest of the
    caller's transaction intact.
    """
    text_signature = compute_text_signature(text)

    storage_failed = False
    row: ModerationCache | None = None
    try:
        with db.begin_nested():
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
        try:
            with db.begin_nested():
                row.hit_count += 1
                row.last_served_at = datetime.datetime.now(datetime.UTC)
                db.flush()
        except Exception:  # noqa: BLE001 -- hit-count bump is best-effort too
            pass
        return row.allowed, CacheOutcome(hit=True, cache_entry_id=row.cache_entry_id)

    miss_reason = "storage_failure" if storage_failed else "no_matching_entry"

    allowed = await check_fn()

    try:
        with db.begin_nested():
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

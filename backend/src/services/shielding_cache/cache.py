"""Cross-learner cache in front of the Tutor Agent's shielding-match
classifier call (spec 026 FR-002/FR-003/FR-004/FR-005/FR-006/FR-008,
research.md §2/§3). Same exact-signature, fail-open shape as
`moderation_cache/cache.py`, keyed on the order-sensitive
(open_question_stem, tutor_question) pair signature instead of a single
text signature -- this is what makes matching scoped per open question
(FR-004).

`classify_fn` may itself raise `shielding.py`'s `ClassificationFailedError`
on a genuine classification failure -- that is not a caching concern and
MUST propagate unchanged so `determine_shielding`'s own FR-010 fail-safe
still triggers; only a cache-storage exception is swallowed here.
"""

import datetime
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from src.models.shielding_classification_cache import ShieldingClassificationCache
from src.services.cache_common.outcome import CacheOutcome
from src.services.cache_common.signature import compute_paired_signature


async def get_or_classify_match(
    db: Session,
    *,
    open_question_stem: str,
    tutor_question: str,
    instruction_version: str,
    classify_fn: Callable[[], Awaitable[bool]],
) -> tuple[bool, CacheOutcome]:
    """Serves a cached match/no-match verdict for an exact (normalized)
    (open_question_stem, tutor_question) pair at the current
    `instruction_version`, or calls `classify_fn()` and stores its
    result as a new row.

    Fails open on any cache-storage exception (`reason="storage_
    failure"`); `classify_fn()` still runs so the request always
    succeeds. A `classify_fn` exception itself (e.g. `ClassificationFailedError`)
    is never caught here -- it propagates to the caller unchanged.
    """
    pair_signature = compute_paired_signature(open_question_stem, tutor_question)

    storage_failed = False
    row: ShieldingClassificationCache | None = None
    try:
        row = (
            db.query(ShieldingClassificationCache)
            .filter(
                ShieldingClassificationCache.pair_signature == pair_signature,
                ShieldingClassificationCache.shielding_classification_instruction_version
                == instruction_version,
            )
            .first()
        )
    except Exception:  # noqa: BLE001 -- any lookup failure fails open (FR-006)
        storage_failed = True

    if row is not None:
        row.hit_count += 1
        row.last_served_at = datetime.datetime.now(datetime.UTC)
        db.flush()
        return row.matches, CacheOutcome(hit=True, cache_entry_id=row.cache_entry_id)

    miss_reason = "storage_failure" if storage_failed else "no_matching_entry"

    matches = await classify_fn()

    try:
        new_row = ShieldingClassificationCache(
            pair_signature=pair_signature,
            shielding_classification_instruction_version=instruction_version,
            matches=matches,
        )
        db.add(new_row)
        db.flush()
    except Exception:  # noqa: BLE001 -- best-effort write, never blocks the request (FR-006)
        pass

    return matches, CacheOutcome(hit=False, reason=miss_reason)

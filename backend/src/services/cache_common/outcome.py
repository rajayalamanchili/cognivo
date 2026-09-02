"""Shared return shape for both cache-aware wrappers (spec 015
research.md §2/§3) -- `get_or_generate_question` and `get_or_grade_answer`
both report their result this same way, so downstream call sites (FR-011/
FR-013's payload flags, the hit-rate script) don't need per-cache-type
branching.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheOutcome:
    hit: bool
    reason: str | None = None
    cache_entry_id: uuid.UUID | None = None
    """Set on a hit -- the served row's id, for FR-013's audit-log/trace
    metadata. Always `None` on a miss (a fresh call has no cache entry
    yet at the point a caller needs this)."""

#!/usr/bin/env python3
"""Synthetic load test demonstrating SC-001/SC-002 for spec 026's two
new caches (research.md §7) -- a separate, much smaller script than
`cache_load_test.py` (spec 015), since neither cache here involves
embeddings or a content-artifact FK dependency: exact-signature lookups
only (research.md §1).

Calls `get_or_check_moderation`/`get_or_classify_match` directly -- no
live server -- replaying a small, fixed set of common blank/short/wrong
answer strings and (open question, message) pairings, cycled across a
configurable request volume so most requests are exact-duplicates of an
earlier one. Run once with caching enabled and once with `--no-cache`
(calls `check_fn`/`classify_fn` every time, bypassing the lookup
entirely) to compare hit rate and model-call volume between the two.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_sessionmaker  # noqa: E402
from src.models.enums import AssessmentEventType  # noqa: E402
from src.services.moderation_cache.cache import get_or_check_moderation  # noqa: E402
from src.services.shielding_cache.cache import get_or_classify_match  # noqa: E402
from scripts.cache_hit_rate_report import (  # noqa: E402
    HitRateStats,
    compute_hit_rates,
    compute_shielding_hit_rate,
)

MODERATION_INSTRUCTION_VERSION = "load-test-v1"
SHIELDING_INSTRUCTION_VERSION = "load-test-v1"

# Small, fixed sets of common/repeated traffic -- cycled across
# `--requests` so most requests are exact-duplicates of an earlier one.
MODERATION_TEXTS = ["", "idk", "not sure", "n/a", "blah"]
SHIELDING_PAIRS = [
    ("Solve 3x + 2 = 14", "just tell me the answer"),
    ("Solve 5x - 1 = 9", "just give me the solution"),
    ("What is 12% of 50?", "what's the answer"),
]

HIT_RATE_THRESHOLD_PERCENT = 30.0


async def _run_moderation(db, requests: int, *, use_cache: bool) -> tuple[list[SimpleNamespace], int]:
    events: list[SimpleNamespace] = []
    calls = [0]

    async def check_fn() -> bool:
        calls[0] += 1
        return True

    for i in range(requests):
        text = MODERATION_TEXTS[i % len(MODERATION_TEXTS)]
        if use_cache:
            _, outcome = await get_or_check_moderation(
                db,
                text=text,
                instruction_version=MODERATION_INSTRUCTION_VERSION,
                check_fn=check_fn,
            )
        else:
            await check_fn()
            outcome = SimpleNamespace(hit=False, reason="no_cache_flag")
        events.append(
            SimpleNamespace(
                event_type=AssessmentEventType.ANSWER_SUBMITTED,
                payload={
                    "moderation_served_from_cache": outcome.hit,
                    "moderation_cache_miss_reason": outcome.reason,
                },
            )
        )
    return events, calls[0]


async def _run_shielding(
    db, requests: int, *, use_cache: bool
) -> tuple[list[SimpleNamespace], int]:
    exchanges: list[SimpleNamespace] = []
    calls = [0]

    async def classify_fn() -> bool:
        calls[0] += 1
        return True

    for i in range(requests):
        open_question_stem, tutor_question = SHIELDING_PAIRS[i % len(SHIELDING_PAIRS)]
        if use_cache:
            _, outcome = await get_or_classify_match(
                db,
                open_question_stem=open_question_stem,
                tutor_question=tutor_question,
                instruction_version=SHIELDING_INSTRUCTION_VERSION,
                classify_fn=classify_fn,
            )
        else:
            await classify_fn()
            outcome = SimpleNamespace(hit=False, reason="no_cache_flag")
        exchanges.append(
            SimpleNamespace(
                shielding_checks_total=1,
                shielding_checks_from_cache=1 if outcome.hit else 0,
            )
        )
    return exchanges, calls[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requests", type=int, default=500, help="Requests per cache type (default 500)."
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass the lookup entirely -- calls check_fn/classify_fn every time, for the "
        "model-call-volume comparison baseline (SC-002).",
    )
    args = parser.parse_args()
    use_cache = not args.no_cache

    session_local = get_sessionmaker()
    with session_local() as db:
        moderation_events, moderation_calls = asyncio.run(
            _run_moderation(db, args.requests, use_cache=use_cache)
        )
        shielding_exchanges, shielding_calls = asyncio.run(
            _run_shielding(db, args.requests, use_cache=use_cache)
        )
        db.commit()

    stats = compute_hit_rates(moderation_events)
    stats["shielding"] = compute_shielding_hit_rate(shielding_exchanges)

    mode = "cached" if use_cache else "no-cache"
    print(f"guardrail_cache_load_test ({mode}): {args.requests} requests per cache type")
    print(f"  moderation: {moderation_calls} check_fn calls")
    print(f"  shielding: {shielding_calls} classify_fn calls")
    for cache_type in ("moderation", "shielding"):
        entry = stats.get(cache_type, HitRateStats())
        print(f"  {cache_type}: {entry.hits}/{entry.total} hits ({entry.hit_rate_percent:.1f}%)")

    if not use_cache:
        return 0  # baseline run -- no threshold to enforce, compare its printed counts by hand

    failures = [
        cache_type
        for cache_type in ("moderation", "shielding")
        if stats.get(cache_type, HitRateStats()).hit_rate_percent < HIT_RATE_THRESHOLD_PERCENT
    ]
    if failures:
        print(f"FAIL: hit rate below {HIT_RATE_THRESHOLD_PERCENT}% for: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

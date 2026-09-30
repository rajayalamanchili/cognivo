#!/usr/bin/env python3
"""Maintainer-run hit-rate report for both semantic caches (spec 015
User Story 3, research.md §8).

No new dashboard or API route -- `served_from_cache`/`cache_miss_reason`
are already recorded on the exact same `AssessmentEvent` rows every
question-generation (`NEXT_TOPIC_SELECTED`) and free-text grading
(`ANSWER_SUBMITTED`) request already writes (spec 015 data-model.md §3),
so this just aggregates the existing audit log, matching this project's
existing script-based observability precedent (`batch_eval_questions.py`).

`compute_hit_rates` is pure (no DB) so it's unit-testable without a real
Postgres instance -- `main()` is the only part that queries one.
"""

import argparse
import datetime
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_sessionmaker  # noqa: E402
from src.models.assessment_event import AssessmentEvent  # noqa: E402
from src.models.enums import AssessmentEventType  # noqa: E402
from src.models.tutor_exchange import TutorExchange  # noqa: E402

# MC/numeric ANSWER_SUBMITTED events carry no served_from_cache key at
# all (grading cache only exists for free-text, spec 015 FR-002) -- they
# aren't counted as either a hit or a miss, they're simply not
# cache-eligible (research.md §8's per-type scoping).
CACHE_TYPE_BY_EVENT_TYPE = {
    AssessmentEventType.NEXT_TOPIC_SELECTED: "question_generation",
    AssessmentEventType.ANSWER_SUBMITTED: "grading",
}

# Moderation (spec 026) gains its own payload keys on both the
# moderation-allow path (ANSWER_SUBMITTED, same rows grading's own
# served_from_cache reads, prefixed moderation_ to avoid colliding) and
# the moderation-block path (FREE_TEXT_SUBMISSION_REJECTED, which
# carries no served_from_cache key at all). Scoped independently from
# grading's rate even though they share an event type.
MODERATION_EVENT_TYPES = {
    AssessmentEventType.ANSWER_SUBMITTED,
    AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED,
}

_DURATION_PATTERN = re.compile(r"^(\d+)([smhd])$")
_DURATION_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


def parse_duration(text: str) -> datetime.timedelta:
    match = _DURATION_PATTERN.match(text.strip())
    if not match:
        raise ValueError(f"invalid --since value {text!r} -- expected e.g. '1h', '30m', '2d'")
    amount, unit = match.groups()
    return datetime.timedelta(**{_DURATION_UNITS[unit]: int(amount)})


@dataclass
class HitRateStats:
    hits: int = 0
    total: int = 0
    miss_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def hit_rate_percent(self) -> float:
        return 100.0 * self.hits / self.total if self.total else 0.0


def compute_hit_rates(events: Iterable[AssessmentEvent]) -> dict[str, HitRateStats]:
    """Aggregates `served_from_cache`/`cache_miss_reason` per cache type,
    scoped independently (SC-001, Clarifications 2026-09-02) -- a
    question-generation hit rate never mixes with a grading one.

    Moderation (spec 026) reads a second, independent key pair
    (`moderation_served_from_cache`/`moderation_cache_miss_reason`) off
    the same `ANSWER_SUBMITTED` rows grading reads, plus
    `FREE_TEXT_SUBMISSION_REJECTED` rows grading never sees -- an event
    can contribute to both a grading entry and a moderation entry.
    """
    stats: dict[str, HitRateStats] = {}

    for event in events:
        cache_type = CACHE_TYPE_BY_EVENT_TYPE.get(event.event_type)
        if cache_type is not None:
            served_from_cache = event.payload.get("served_from_cache")
            if served_from_cache is not None:
                entry = stats.setdefault(cache_type, HitRateStats())
                entry.total += 1
                if served_from_cache:
                    entry.hits += 1
                else:
                    reason = event.payload.get("cache_miss_reason") or "unknown"
                    entry.miss_reasons[reason] = entry.miss_reasons.get(reason, 0) + 1

        if event.event_type in MODERATION_EVENT_TYPES:
            moderation_served_from_cache = event.payload.get("moderation_served_from_cache")
            if moderation_served_from_cache is not None:
                entry = stats.setdefault("moderation", HitRateStats())
                entry.total += 1
                if moderation_served_from_cache:
                    entry.hits += 1
                else:
                    reason = event.payload.get("moderation_cache_miss_reason") or "unknown"
                    entry.miss_reasons[reason] = entry.miss_reasons.get(reason, 0) + 1

    return stats


def compute_shielding_hit_rate(exchanges: Iterable[TutorExchange]) -> HitRateStats:
    """Shielding's rate (spec 026) is per-check, not per-exchange --
    `determine_shielding` can run several independent checks (one per
    open question) for a single `TutorExchange` row, so this sums
    `shielding_checks_total`/`shielding_checks_from_cache` across all
    exchanges in the window rather than treating each exchange as one
    hit-or-miss sample (data-model.md §3)."""
    stats = HitRateStats()
    for exchange in exchanges:
        stats.total += exchange.shielding_checks_total
        stats.hits += exchange.shielding_checks_from_cache
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        default="1h",
        help="Time window to report over, e.g. '1h', '30m', '2d' (default 1h).",
    )
    args = parser.parse_args()

    since_cutoff = datetime.datetime.now(datetime.UTC) - parse_duration(args.since)

    event_types = set(CACHE_TYPE_BY_EVENT_TYPE) | MODERATION_EVENT_TYPES
    session_local = get_sessionmaker()
    with session_local() as db:
        events = (
            db.query(AssessmentEvent)
            .filter(
                AssessmentEvent.event_type.in_(event_types),
                AssessmentEvent.created_at > since_cutoff,
            )
            .all()
        )
        exchanges = (
            db.query(TutorExchange).filter(TutorExchange.created_at > since_cutoff).all()
        )

    stats = compute_hit_rates(events)
    shielding_stats = compute_shielding_hit_rate(exchanges)
    if shielding_stats.total:
        stats["shielding"] = shielding_stats

    if not stats:
        print(f"cache_hit_rate_report: no cache-eligible events in the last {args.since}")
        return 0

    for cache_type in sorted(stats):
        entry = stats[cache_type]
        print(f"{cache_type}: {entry.hits}/{entry.total} hits ({entry.hit_rate_percent:.1f}%)")
        for reason, count in sorted(entry.miss_reasons.items()):
            print(f"  miss reason {reason!r}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

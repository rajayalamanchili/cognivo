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

# MC/numeric ANSWER_SUBMITTED events carry no served_from_cache key at
# all (grading cache only exists for free-text, spec 015 FR-002) -- they
# aren't counted as either a hit or a miss, they're simply not
# cache-eligible (research.md §8's per-type scoping).
CACHE_TYPE_BY_EVENT_TYPE = {
    AssessmentEventType.NEXT_TOPIC_SELECTED: "question_generation",
    AssessmentEventType.ANSWER_SUBMITTED: "grading",
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
    question-generation hit rate never mixes with a grading one."""
    stats: dict[str, HitRateStats] = {}
    for event in events:
        cache_type = CACHE_TYPE_BY_EVENT_TYPE.get(event.event_type)
        if cache_type is None:
            continue
        served_from_cache = event.payload.get("served_from_cache")
        if served_from_cache is None:
            continue  # not cache-eligible (e.g. a structured-answer ANSWER_SUBMITTED)

        entry = stats.setdefault(cache_type, HitRateStats())
        entry.total += 1
        if served_from_cache:
            entry.hits += 1
        else:
            reason = event.payload.get("cache_miss_reason") or "unknown"
            entry.miss_reasons[reason] = entry.miss_reasons.get(reason, 0) + 1
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

    session_local = get_sessionmaker()
    with session_local() as db:
        events = (
            db.query(AssessmentEvent)
            .filter(
                AssessmentEvent.event_type.in_(CACHE_TYPE_BY_EVENT_TYPE),
                AssessmentEvent.created_at > since_cutoff,
            )
            .all()
        )

    stats = compute_hit_rates(events)
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

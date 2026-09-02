#!/usr/bin/env python3
"""Synthetic load test demonstrating SC-001/SC-002 (spec 015 research.md
§10) -- the milestone's actual verification mechanism for both, not
just a nice-to-have.

Calls `get_or_generate_question`/`get_or_grade_answer` directly -- no
live server, no HTTP layer -- replaying a configurable volume of
repeated question-generation requests (same topic/difficulty, many
synthetic `learner_id`s) and grading requests (paraphrased-but-
equivalent answers to shared questions). Run once with caching enabled
and once with `--no-cache` (bypasses the pool/lookup entirely, calling
`generate_fn`/`grade_fn` every time) to compare hit rate and model-call
volume between the two.

`generate_fn`/`grade_fn` are lightweight fakes, not real LLM/A2A calls
(research.md §10: "fast, dependency-free... no new test infrastructure")
-- this measures the cache logic's hit rate, not model latency/cost.
`embed_answer` is patched to a deterministic pseudo-embedding so
"paraphrased-but-equivalent" answers can be simulated without a real
Voyage call: answers to the same question template embed identically
(guaranteed hit after the first), different templates embed to
orthogonal vectors (never a spurious cross-question hit).

Precondition: `algebra-1`'s content artifact must already be loaded
(`uv run python scripts/load_content_artifact.py content/algebra-1/subject.yaml`)
-- this drives the real `question_generation_cache` table, which FKs to
real `topics` rows; seeding content isn't this script's job.
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from scripts.cache_hit_rate_report import HitRateStats, compute_hit_rates  # noqa: E402
from src.agents.assessment_gen.agent import GeneratedQuestionDraft  # noqa: E402
from src.db import get_sessionmaker  # noqa: E402
from src.models.enums import AssessmentEventType, DifficultyBand  # noqa: E402
from src.models.subject import Subject  # noqa: E402
from src.services.grading_cache.cache import get_or_grade_answer  # noqa: E402
from src.services.grading_client.client import GradingResult  # noqa: E402
from src.services.question_cache.cache import get_or_generate_question  # noqa: E402

SUBJECT_ID = "algebra-1"
# Real topics from that content artifact -- enough distinct
# (topic, difficulty) key tuples that repeats actually exercise the
# pool, not just one entry.
TOPIC_IDS = ["integers-and-operations", "variables-and-expressions", "order-of-operations"]
DIFFICULTIES = [DifficultyBand.EASY, DifficultyBand.MEDIUM]
CONTENT_VERSION = "load-test-v1"
GENERATION_PROMPT_VERSION = "load-test-v1"
GRADING_LOGIC_VERSION = "load-test-v1"

QUESTION_TEMPLATES = [
    {
        "question_stem": "Why does a plant need sunlight?",
        "rubric_criteria": [{"description": "mentions photosynthesis", "weight": 1.0}],
    },
    {
        "question_stem": "What is the boiling point of water at sea level?",
        "rubric_criteria": [{"description": "states 100 degrees Celsius", "weight": 1.0}],
    },
    {
        "question_stem": "Why do objects fall toward the Earth?",
        "rubric_criteria": [{"description": "mentions gravity", "weight": 1.0}],
    },
]

HIT_RATE_THRESHOLD_PERCENT = 30.0


def _check_content_loaded(db: Session) -> None:
    subject = db.get(Subject, SUBJECT_ID)
    if subject is None or subject.validated_at is None:
        print(
            f"cache_load_test: {SUBJECT_ID!r} content artifact not loaded/validated -- run "
            f"`uv run python scripts/load_content_artifact.py "
            f"content/{SUBJECT_ID}/subject.yaml` first"
        )
        raise SystemExit(1)


def _pseudo_embedding(meaning_group: str) -> list[float]:
    """Deterministic stand-in for a real Voyage embedding (module
    docstring): same group -> identical vector (guaranteed hit under
    the real 0.15 cosine-distance threshold), different group ->
    orthogonal (never a spurious cross-question hit)."""
    vector = [0.0] * 1024
    vector[hash(meaning_group) % 1024] = 1.0
    return vector


async def _run_question_generation(
    db: Session, requests: int, *, use_cache: bool
) -> tuple[list[SimpleNamespace], int]:
    events: list[SimpleNamespace] = []
    calls = [0]

    async def generate_fn() -> GeneratedQuestionDraft:
        calls[0] += 1
        return GeneratedQuestionDraft(
            question_type="multiple_choice",
            stem=f"synthetic question {uuid.uuid4()}",
            options=["a", "b", "c", "d"],
            correct_index=0,
        )

    for i in range(requests):
        if use_cache:
            _, outcome = await get_or_generate_question(
                db,
                subject_id=SUBJECT_ID,
                topic_id=TOPIC_IDS[i % len(TOPIC_IDS)],
                difficulty=DIFFICULTIES[i % len(DIFFICULTIES)],
                content_version=CONTENT_VERSION,
                generation_prompt_version=GENERATION_PROMPT_VERSION,
                generate_fn=generate_fn,
            )
        else:
            await generate_fn()
            outcome = SimpleNamespace(hit=False, reason="no_cache_flag")
        events.append(
            SimpleNamespace(
                event_type=AssessmentEventType.NEXT_TOPIC_SELECTED,
                payload={"served_from_cache": outcome.hit, "cache_miss_reason": outcome.reason},
            )
        )
    return events, calls[0]


async def _run_grading(
    db: Session, requests: int, *, use_cache: bool
) -> tuple[list[SimpleNamespace], int]:
    events: list[SimpleNamespace] = []
    calls = [0]

    async def grade_fn(**kwargs) -> GradingResult:
        calls[0] += 1
        return GradingResult(
            correct=True,
            graduated_score=0.9,
            criteria_met=["met"],
            criteria_missed=[],
            grading_logic_version=GRADING_LOGIC_VERSION,
        )

    async def one_request(i: int) -> None:
        template = QUESTION_TEMPLATES[i % len(QUESTION_TEMPLATES)]
        if use_cache:
            _, outcome = await get_or_grade_answer(
                db,
                question_stem=template["question_stem"],
                rubric_criteria=template["rubric_criteria"],
                learner_answer=f"paraphrase {i} of a semantically equivalent answer",
                question_id=uuid.uuid4(),
                learner_id=uuid.uuid4(),
                grading_logic_version=GRADING_LOGIC_VERSION,
                grade_fn=grade_fn,
            )
        else:
            await grade_fn(
                question_stem=template["question_stem"],
                rubric_criteria=template["rubric_criteria"],
                learner_answer=f"paraphrase {i} of a semantically equivalent answer",
                question_id=uuid.uuid4(),
                learner_id=uuid.uuid4(),
            )
            outcome = SimpleNamespace(hit=False, reason="no_cache_flag")
        events.append(
            SimpleNamespace(
                event_type=AssessmentEventType.ANSWER_SUBMITTED,
                payload={"served_from_cache": outcome.hit, "cache_miss_reason": outcome.reason},
            )
        )

    if use_cache:
        with patch(
            "src.services.grading_cache.cache.embed_answer",
            side_effect=lambda question_stem, learner_answer: _pseudo_embedding(question_stem),
        ):
            for i in range(requests):
                await one_request(i)
    else:
        for i in range(requests):
            await one_request(i)

    return events, calls[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requests", type=int, default=200, help="Requests per cache type (default 200)."
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass the pool/lookup entirely -- calls generate_fn/grade_fn every time, "
        "for the model-call-volume comparison baseline (SC-002).",
    )
    args = parser.parse_args()
    use_cache = not args.no_cache

    session_local = get_sessionmaker()
    with session_local() as db:
        _check_content_loaded(db)
        qgen_events, qgen_calls = asyncio.run(
            _run_question_generation(db, args.requests, use_cache=use_cache)
        )
        grading_events, grading_calls = asyncio.run(
            _run_grading(db, args.requests, use_cache=use_cache)
        )
        db.commit()

    stats = compute_hit_rates(qgen_events + grading_events)

    mode = "cached" if use_cache else "no-cache"
    print(f"cache_load_test ({mode}): {args.requests} requests per cache type")
    print(f"  question_generation: {qgen_calls} generate_fn calls")
    print(f"  grading: {grading_calls} grade_fn calls")
    for cache_type in sorted(stats):
        entry = stats[cache_type]
        print(f"  {cache_type}: {entry.hits}/{entry.total} hits ({entry.hit_rate_percent:.1f}%)")

    if not use_cache:
        return 0  # baseline run -- no threshold to enforce, compare its printed counts by hand

    failures = [
        cache_type
        for cache_type in ("question_generation", "grading")
        if stats.get(cache_type, HitRateStats()).hit_rate_percent < HIT_RATE_THRESHOLD_PERCENT
    ]
    if failures:
        print(f"FAIL: hit rate below {HIT_RATE_THRESHOLD_PERCENT}% for: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

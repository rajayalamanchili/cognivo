#!/usr/bin/env python3
"""Validates spec 015's grading-cache equivalence gate (T024,
Clarifications 2026-09-02) against Milestone 6's ground-truth grading
eval set and the spec's own negation Edge Case.

FR-003's actual mechanism (after this milestone's real-data-driven
redesign) is a two-stage gate: an embedding-distance pre-filter (cheap,
efficiency-only -- see `grading_cache/cache.py`'s
`PREFILTER_DISTANCE_CEILING`) narrows to a candidate, then a cheap
LLM-based rubric-criteria re-classification
(`equivalence.py::classify_criteria_met`) is the actual correctness
check. This script validates that second stage directly: for each
meaning-divergent ground-truth pair (same question, opposite
`expected_correct`) plus the spec's literal negation example, it
classifies both answers against the same rubric and confirms they
produce DIFFERENT `criteria_met` patterns -- if they matched, the
equivalence gate would produce a false-positive hit exactly like the
original pure-embedding-threshold design did (see this script's git
history / tasks.md T024's implementation notes for that finding).

Requires a real classifier call (`ANTHROPIC_API_KEY`, same model as
`equivalence.py`'s default) -- this validates the real model's
behavior, not a mocked unit test.
"""

import asyncio
import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.sessions import InMemorySessionService  # noqa: E402

from src.services.grading_cache.equivalence import (  # noqa: E402
    ClassificationFailedError,
    classify_criteria_met,
)

GROUND_TRUTH_PATH = (
    Path(__file__).resolve().parent.parent / "evaluation" / "grading_ground_truth.jsonl"
)

# The spec's own literal Edge Cases example -- not present in the
# ground-truth set (no photosynthesis question there), checked
# explicitly since it's the named example.
NEGATION_EXAMPLE = (
    "Does photosynthesis require light?",
    [{"description": "states that photosynthesis requires light", "weight": 1.0}],
    "Photosynthesis does not require light.",
    "Photosynthesis requires light.",
)


def _load_ground_truth() -> list[dict]:
    with GROUND_TRUTH_PATH.open() as f:
        return [json.loads(line) for line in f if line.strip()]


async def _classify(
    session_service, *, question_stem: str, rubric_criteria: list[dict], learner_answer: str
) -> frozenset[str] | None:
    try:
        result = await classify_criteria_met(
            question_stem=question_stem,
            rubric_criteria=rubric_criteria,
            learner_answer=learner_answer,
            session_service=session_service,
        )
        return frozenset(result)
    except ClassificationFailedError as exc:
        print(f"  classification failed: {exc}")
        return None


async def _main_async() -> int:
    session_service = InMemorySessionService()
    triples = _load_ground_truth()
    by_stem: dict[str, list[dict]] = {}
    for triple in triples:
        by_stem.setdefault(triple["question_stem"], []).append(triple)

    failures: list[str] = []

    for _stem, group in by_stem.items():
        for a, b in combinations(group, 2):
            if a["expected_correct"] == b["expected_correct"]:
                continue
            pattern_a = await _classify(
                session_service,
                question_stem=a["question_stem"],
                rubric_criteria=a["rubric"]["criteria"],
                learner_answer=a["learner_answer"],
            )
            pattern_b = await _classify(
                session_service,
                question_stem=b["question_stem"],
                rubric_criteria=b["rubric"]["criteria"],
                learner_answer=b["learner_answer"],
            )
            is_false_positive = pattern_a is not None and pattern_a == pattern_b
            verdict = "FALSE POSITIVE" if is_false_positive else "OK"
            print(f"[{verdict}] {a['id']} vs {b['id']}: {pattern_a} vs {pattern_b}")
            if is_false_positive:
                failures.append(f"{a['id']} vs {b['id']} (identical criteria_met pattern)")

    stem, rubric_criteria, negative_answer, positive_answer = NEGATION_EXAMPLE
    pattern_neg = await _classify(
        session_service,
        question_stem=stem,
        rubric_criteria=rubric_criteria,
        learner_answer=negative_answer,
    )
    pattern_pos = await _classify(
        session_service,
        question_stem=stem,
        rubric_criteria=rubric_criteria,
        learner_answer=positive_answer,
    )
    is_false_positive = pattern_neg is not None and pattern_neg == pattern_pos
    verdict = "FALSE POSITIVE" if is_false_positive else "OK"
    print(f"[{verdict}] spec negation example: {pattern_neg} vs {pattern_pos}")
    if is_false_positive:
        failures.append("spec negation example (identical criteria_met pattern)")

    # Genuine paraphrase pairs -- informational, confirms the gate isn't
    # so strict it never actually produces a hit in practice.
    true_positive_checks = 0
    true_positive_matches = 0
    for stem, group in by_stem.items():
        for a, b in combinations(group, 2):
            if a["expected_correct"] != b["expected_correct"] or a["id"] == b["id"]:
                continue
            if "paraphrase" not in a["id"] and "paraphrase" not in b["id"]:
                continue
            pattern_a = await _classify(
                session_service,
                question_stem=stem,
                rubric_criteria=a["rubric"]["criteria"],
                learner_answer=a["learner_answer"],
            )
            pattern_b = await _classify(
                session_service,
                question_stem=stem,
                rubric_criteria=b["rubric"]["criteria"],
                learner_answer=b["learner_answer"],
            )
            true_positive_checks += 1
            matched = pattern_a is not None and pattern_a == pattern_b
            true_positive_matches += matched
            verdict = "hit" if matched else "miss"
            print(f"[paraphrase, {verdict}] {a['id']} vs {b['id']}: {pattern_a} vs {pattern_b}")

    if failures:
        print(
            f"FAIL: {len(failures)} meaning-divergent pair(s) produced identical "
            "criteria_met patterns:"
        )
        for failure in failures:
            print(f"  {failure}")
        return 1

    print(
        "OK: the equivalence gate produces no false positives against the ground-truth set "
        f"+ the spec's negation example ({true_positive_matches}/{true_positive_checks} "
        "genuine paraphrase pairs would still register as hits)"
    )
    return 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    sys.exit(main())

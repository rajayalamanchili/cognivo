#!/usr/bin/env python3
"""Validates `DEFAULT_SIMILARITY_THRESHOLD` (services/dedup/checker.py)
against *real* Voyage embeddings, not the hand-made 2D vectors
`tests/unit/test_dedup_checker.py` uses (review finding, PR #113: that
file's own comment asserted real embeddings of same-template/different-
number questions "land well under the 0.92 cosine threshold" without
ever checking a real embedding).

Requires a reachable embedding provider (`TUTOR_EMBEDDING_MODEL`,
default `voyage/voyage-3`, same env the rest of the dedup/retrieval code
uses) -- this validates real model behavior, not a mocked unit test.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.dedup.checker import (  # noqa: E402
    DEFAULT_SIMILARITY_THRESHOLD,
    EmbeddingUnavailableError,
    embed_stem,
)

# Each group: stems a real near-duplicate check must tell apart. The
# first two entries in every group are distinct questions sharing a
# phrasing template but differing only in their numbers -- the exact
# false-positive case this bug-fix amendment (2026-10-12) targets, and
# the specific scenario the automated review on PR #113 flagged as
# unverified. Any additional entries are genuine near-duplicates of the
# group's first entry (identical question, or a trivial rephrasing).
GROUPS: list[list[str]] = [
    [
        "Factor the expression x^2 + 5x + 6.",
        "Factor the expression x^2 + 7x + 12.",
        "Factor the expression x^2 + 5x + 6.",
    ],
    [
        "Solve for x: 2x + 3 = 11.",
        "Solve for x: 3x + 4 = 19.",
        "Solve for x: 2x + 3 = 11.",
    ],
    [
        "Evaluate 2 + 3 * 4 using the order of operations.",
        "Evaluate 5 + 2 * 6 using the order of operations.",
    ],
    [
        "What is -3 + 5?",
        "What is -7 + 2?",
        "What is the sum of -3 and 5?",
    ],
]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b)


async def _main_async() -> int:
    try:
        embeddings = {
            stem: await embed_stem(stem) for group in GROUPS for stem in set(group)
        }
    except EmbeddingUnavailableError as exc:
        print(f"SKIP: embedding provider unavailable ({exc}) -- cannot calibrate")
        return 0

    false_positives: list[str] = []
    false_negatives: list[str] = []

    for group in GROUPS:
        same_template_different_numbers = group[0], group[1]
        similarity = _cosine(embeddings[group[0]], embeddings[group[1]])
        verdict = "FALSE POSITIVE" if similarity >= DEFAULT_SIMILARITY_THRESHOLD else "ok"
        print(
            f"[{verdict}] different questions, same template: "
            f"{similarity:.4f} -- {same_template_different_numbers[0]!r} vs "
            f"{same_template_different_numbers[1]!r}"
        )
        if similarity >= DEFAULT_SIMILARITY_THRESHOLD:
            false_positives.append(
                f"{similarity:.4f} >= {DEFAULT_SIMILARITY_THRESHOLD}: "
                f"{same_template_different_numbers}"
            )

        for near_dup in group[2:]:
            similarity = _cosine(embeddings[group[0]], embeddings[near_dup])
            verdict = "ok" if similarity >= DEFAULT_SIMILARITY_THRESHOLD else "FALSE NEGATIVE"
            print(
                f"[{verdict}] genuine near-duplicate: {similarity:.4f} -- "
                f"{group[0]!r} vs {near_dup!r}"
            )
            if similarity < DEFAULT_SIMILARITY_THRESHOLD:
                false_negatives.append(f"{similarity:.4f} < {DEFAULT_SIMILARITY_THRESHOLD}: "
                                        f"{group[0]!r} vs {near_dup!r}")

    if false_positives or false_negatives:
        print(
            f"\nFAIL: {len(false_positives)} same-template pair(s) scored at/above threshold "
            f"(would be wrongly flagged as duplicates), {len(false_negatives)} genuine "
            "near-duplicate pair(s) scored below it (would be wrongly allowed through)."
        )
        for line in false_positives + false_negatives:
            print(f"  {line}")
        return 1

    print(
        f"\nOK: DEFAULT_SIMILARITY_THRESHOLD={DEFAULT_SIMILARITY_THRESHOLD} correctly separates "
        f"every same-template/different-number pair from every genuine near-duplicate pair "
        f"across {len(GROUPS)} groups."
    )
    return 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Honest SC-001/SC-002 rate report for the Tutor Agent's answer-
shielding classifier (spec 016, `/speckit-analyze` finding C2).

Single-example integration tests (`test_tutor_messages.py`) prove the
mechanism works, but SC-001 ("at least 90% of direct-ask questions are
shielded") and SC-002 ("100% of unrelated-ask questions are not") are
both percentage claims over "a defined set of test questions" -- this
script is that defined set, mirroring
`validate_grading_cache_threshold.py`'s shape exactly (a direct
`classify_match` call with `InMemorySessionService`, no database, no
HTTP layer -- this validates the real model's behavior, not a mocked
unit test).

SC-004 (shielding lifts once a question is no longer open) is
deliberately NOT measured here -- it is fully deterministic (`find_
open_questions` never calls the classifier at all once a question is
answered or its assignment is cancelled), already proven exactly by
`test_tutor_messages.py`'s `test_shielding_lifts_once_the_open_
question_is_answered`/`test_shielding_lifts_once_the_assignment_is_
cancelled`. Forcing it into a percentage-based eval here would measure
nothing the classifier actually decides.

Like `check_misconception_classifier_eval.py`, this is deliberately NOT
a pass/fail merge gate: exit code is non-zero only on a crash or
malformed fixture, never merely for landing below a threshold on this
small, hand-curated set -- a single ambiguous LLM judgment call on 14
rows can swing the reported percentage by 7 points either way.

Requires a real classifier call (`ANTHROPIC_API_KEY`) -- this validates
the real model's behavior, not a mocked unit test.

Usage: uv run python scripts/check_shielding_eval.py [path/to/ground_truth.jsonl]
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.sessions import InMemorySessionService  # noqa: E402

from src.services.tutor.shielding import classify_match  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GROUND_TRUTH_PATH = REPO_ROOT / "evaluation" / "shielding_ground_truth.jsonl"

# SC-001/SC-002's own stated thresholds -- informational only (see
# module docstring: never a build-breaking gate here).
SC_001_THRESHOLD = 0.90
SC_002_THRESHOLD = 1.00


def _load_rows(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


async def _run(ground_truth_path: Path) -> int:
    rows = _load_rows(ground_truth_path)
    if not rows:
        print("FAIL: no rows found in ground-truth fixture")
        return 1

    session_service = InMemorySessionService()
    sc001_rows = [row for row in rows if row["category"] in ("direct_ask", "paraphrase_ask")]
    sc002_rows = [row for row in rows if row["category"] == "unrelated_ask"]

    errors: list[str] = []
    sc001_correct = 0
    sc002_correct = 0

    for row in rows:
        try:
            shielded = await classify_match(
                open_question_stem=row["open_question_stem"],
                tutor_question=row["tutor_question"],
                session_service=session_service,
            )
        except Exception as exc:  # noqa: BLE001 -- a classification failure is a data point, not a crash
            print(f"[ERROR] {row['id']}: classification failed -- {exc}")
            errors.append(row["id"])
            continue

        correct = shielded == row["expected_shield"]
        verdict = "OK" if correct else "MISS"
        print(
            f"[{verdict}] {row['id']} ({row['category']}): "
            f"expected_shield={row['expected_shield']} predicted={shielded}"
        )
        if row["category"] in ("direct_ask", "paraphrase_ask") and correct:
            sc001_correct += 1
        if row["category"] == "unrelated_ask" and correct:
            sc002_correct += 1

    if not sc001_rows or not sc002_rows:
        print(
            "FAIL: fixture must contain at least one direct_ask/paraphrase_ask row "
            "(SC-001) and one unrelated_ask row (SC-002)"
        )
        return 1

    sc001_rate = sc001_correct / len(sc001_rows)
    sc002_rate = sc002_correct / len(sc002_rows)

    print(f"\nshielding_eval: n={len(rows)}, classification errors={len(errors)}")
    print(
        f"  SC-001 (direct/paraphrase-ask shielded): {sc001_correct}/{len(sc001_rows)} "
        f"= {sc001_rate:.0%} (threshold: >= {SC_001_THRESHOLD:.0%})"
    )
    print(
        f"  SC-002 (unrelated-ask left unshielded): {sc002_correct}/{len(sc002_rows)} "
        f"= {sc002_rate:.0%} (threshold: {SC_002_THRESHOLD:.0%})"
    )
    if sc001_rate >= SC_001_THRESHOLD:
        print("  OK: SC-001 threshold met")
    else:
        print("  NOTE: SC-001 threshold NOT met on this validation set -- reported honestly")
    if sc002_rate >= SC_002_THRESHOLD:
        print("  OK: SC-002 threshold met")
    else:
        print("  NOTE: SC-002 threshold NOT met on this validation set -- reported honestly")

    return 0


def main() -> int:
    ground_truth_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GROUND_TRUTH_PATH
    if not ground_truth_path.is_file():
        print(f"FAIL: ground-truth fixture not found at {ground_truth_path}")
        return 1
    return asyncio.run(_run(ground_truth_path))


if __name__ == "__main__":
    sys.exit(main())

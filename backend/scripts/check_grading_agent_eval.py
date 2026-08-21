#!/usr/bin/env python3
"""Ground-truth eval gate for the Grading Agent's scoring logic (spec 007
FR-008, SC-003, T040).

Runs `grading-agent/scripts/eval_runner.py` (under `grading-agent/`'s own
`uv` environment -- see that script's docstring for why this is a
subprocess call rather than a direct import) against the hand-labeled
ground-truth set (T039, `backend/evaluation/grading_ground_truth.jsonl`),
twice per triple, and checks two things against the thresholds locked in
research.md §11:
  - accuracy: fraction of triples whose first run's threshold-derived
    `correct` boolean matches `expected_correct`, >= 90%.
  - consistency: fraction of triples where both runs agree on the
    threshold-derived `correct` boolean, >= 95%.

This is a required merge gate (FR-008), not an advisory report -- a
scoring-logic change that regresses either metric below its locked
threshold must fail CI, not just print a warning.

Usage: python scripts/check_grading_agent_eval.py
Exit code 0 = both thresholds met; 1 = a threshold was missed or the
Grading Agent couldn't be evaluated at all (e.g. no live model
credentials -- see research.md §11 and this feature's quickstart.md
scenario 12).
"""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRADING_AGENT_DIR = REPO_ROOT / "grading-agent"
GROUND_TRUTH_PATH = REPO_ROOT / "backend" / "evaluation" / "grading_ground_truth.jsonl"

# Locked per research.md §11.
ACCURACY_THRESHOLD = 0.90
CONSISTENCY_THRESHOLD = 0.95


def _run_eval_runner() -> list[dict]:
    result = subprocess.run(
        ["uv", "run", "python", "scripts/eval_runner.py", str(GROUND_TRUTH_PATH)],
        cwd=GRADING_AGENT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"eval_runner.py exited {result.returncode}")
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def _score(runs: list[dict]) -> tuple[float, float, list[str]]:
    """Returns (accuracy, consistency, failure_details)."""
    by_id: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        by_id[run["id"]].append(run)

    accurate = 0
    consistent = 0
    failures: list[str] = []
    for triple_id, triple_runs in by_id.items():
        triple_runs.sort(key=lambda r: r["run_index"])
        errors = [r for r in triple_runs if "error" in r]
        if errors:
            failures.append(f"{triple_id}: run errored -- {errors[0]['error']}")
            continue

        expected = triple_runs[0]["expected_correct"]
        first_correct = triple_runs[0]["correct"]
        if first_correct == expected:
            accurate += 1
        else:
            failures.append(
                f"{triple_id} ({triple_runs[0]['category']}): expected correct={expected}, "
                f"got {first_correct} (graduated_score={triple_runs[0]['graduated_score']})"
            )

        run_corrects = {r["correct"] for r in triple_runs}
        if len(run_corrects) == 1:
            consistent += 1
        else:
            failures.append(
                f"{triple_id}: inconsistent across runs -- "
                f"{[r['correct'] for r in triple_runs]}"
            )

    total = len(by_id)
    if total == 0:
        return 0.0, 0.0, ["no triples found in ground-truth set"]
    return accurate / total, consistent / total, failures


def main() -> int:
    try:
        runs = _run_eval_runner()
    except (RuntimeError, OSError) as exc:
        print(f"FAIL: could not run the Grading Agent eval: {exc}")
        return 1

    accuracy, consistency, failures = _score(runs)
    print(
        f"grading_agent_eval: accuracy={accuracy:.0%} "
        f"(threshold {ACCURACY_THRESHOLD:.0%}), "
        f"consistency={consistency:.0%} (threshold {CONSISTENCY_THRESHOLD:.0%})"
    )
    for failure in failures:
        print(f"  {failure}")

    if accuracy < ACCURACY_THRESHOLD or consistency < CONSISTENCY_THRESHOLD:
        print("FAIL: ground-truth eval gate did not meet the locked threshold (FR-008/SC-003)")
        return 1

    print("OK: ground-truth eval gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

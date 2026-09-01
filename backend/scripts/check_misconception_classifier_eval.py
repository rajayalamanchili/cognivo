#!/usr/bin/env python3
"""Honest accuracy-vs-baseline report for the misconception classifier
(spec 013 FR-007, research.md §7) -- structurally mirrors
`check_grading_agent_eval.py`, but this is deliberately NOT a pass/fail
merge gate on accuracy: FR-007 requires the classifier-vs-baseline
comparison be recorded even when the fine-tuned classifier loses.
Exit code is non-zero ONLY on a crash or malformed fixture -- never
merely because the classifier scores below the baseline.

Classifier accuracy is measured via leave-one-out cross-validation, not
by scoring the shipped `classifier.joblib` against its own training
data (T031 correction, post-review 2026-09-01): with only 7 rows per
subject there's no volume for a real held-out split, but reusing
training rows for scoring is leakage -- it reports training-fit
accuracy, not a genuine generalization estimate, and isn't comparable
to the baseline's honest zero-shot number. For each row, a classifier
is fit on every *other* row for that subject and scored on the one held
out, so every prediction comes from a model that never saw that
example. The shipped artifact (trained on all rows, for production use)
is untouched by this script.

Usage: uv run python scripts/check_misconception_classifier_eval.py [path/to/ground_truth.jsonl]
"""

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.train_misconception_classifier import fit_classifier  # noqa: E402
from src.services.content_artifact.loader import load_content_artifact_file  # noqa: E402
from src.services.misconception.baseline import NONE_LABEL, classify_baseline  # noqa: E402
from src.services.misconception.embed import embed_answer  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GROUND_TRUTH_PATH = REPO_ROOT / "evaluation" / "misconception_ground_truth.jsonl"
CONTENT_DIR = REPO_ROOT / "content"


def compute_accuracy(expected_and_predicted: list[tuple[str, str]]) -> float:
    """Pure fraction of matching `(expected, predicted)` pairs -- T029.
    No thresholding, no gating -- just the raw match rate, so the two
    callers below (classifier, baseline) are compared on identical
    terms."""
    if not expected_and_predicted:
        return 0.0
    correct = sum(1 for expected, predicted in expected_and_predicted if expected == predicted)
    return correct / len(expected_and_predicted)


def _load_rows(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _taxonomy_by_subject_and_topic() -> dict[tuple[str, str], list[dict]]:
    taxonomy: dict[tuple[str, str], list[dict]] = {}
    for subject_yaml in sorted(CONTENT_DIR.glob("*/subject.yaml")):
        artifact = load_content_artifact_file(subject_yaml)
        for topic in artifact.topics:
            taxonomy[(artifact.subject_id, topic.topic_id)] = list(topic.misconceptions)
    return taxonomy


def _predict_classifier(model, embedding: list[float]) -> str:
    probabilities = model.predict_proba([embedding])[0]
    return str(model.classes_[probabilities.argmax()])


def _leave_one_out_pairs(
    subject_rows: list[dict], embedding_by_row_id: dict[str, list[float]]
) -> list[tuple[str, str]]:
    """Scores every row in `subject_rows` with a classifier fit on that
    subject's *other* rows only -- no row is ever scored by a model that
    trained on it, so this cannot leak."""
    pairs: list[tuple[str, str]] = []
    for held_out in subject_rows:
        train_rows = [r for r in subject_rows if r["id"] != held_out["id"]]
        train_embeddings = [embedding_by_row_id[r["id"]] for r in train_rows]
        train_labels = [r["expected_misconception_id"] or NONE_LABEL for r in train_rows]
        model = fit_classifier(train_embeddings, train_labels)
        expected = held_out["expected_misconception_id"] or NONE_LABEL
        predicted = _predict_classifier(model, embedding_by_row_id[held_out["id"]])
        pairs.append((expected, predicted))
    return pairs


async def _run(ground_truth_path: Path) -> int:
    rows = _load_rows(ground_truth_path)
    if not rows:
        print("FAIL: no rows found in ground-truth fixture")
        return 1

    taxonomy_by_topic = _taxonomy_by_subject_and_topic()
    rows_by_subject: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_subject[row["subject_id"]].append(row)

    classifier_pairs: list[tuple[str, str]] = []
    baseline_pairs: list[tuple[str, str]] = []
    errors: list[str] = []
    embedding_by_row_id: dict[str, list[float]] = {}

    for row in rows:
        try:
            embedding_by_row_id[row["id"]] = embed_answer(row["question"], row["learner_answer"])
        except Exception as exc:  # noqa: BLE001 -- any failure here fails the whole run
            errors.append(f"{row['id']}: embedding failed -- {exc}")

    if not errors:
        for subject_id, subject_rows in sorted(rows_by_subject.items()):
            if len(subject_rows) < 2:
                errors.append(
                    f"{subject_id}: only {len(subject_rows)} ground-truth row(s) -- "
                    "leave-one-out cross-validation needs at least 2 per subject"
                )
                continue
            try:
                classifier_pairs.extend(_leave_one_out_pairs(subject_rows, embedding_by_row_id))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{subject_id}: leave-one-out classifier failed -- {exc}")

    for row in rows:
        expected = row["expected_misconception_id"] or NONE_LABEL
        row_taxonomy = taxonomy_by_topic.get((row["subject_id"], row["topic_id"]), [])
        try:
            baseline_predicted = await classify_baseline(
                row["question"], row["learner_answer"], row_taxonomy
            )
            baseline_pairs.append((expected, baseline_predicted))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{row['id']}: baseline failed -- {exc}")

    if errors:
        print("FAIL: could not complete the eval run")
        for error in errors:
            print(f"  {error}")
        return 1

    classifier_accuracy = compute_accuracy(classifier_pairs)
    baseline_accuracy = compute_accuracy(baseline_pairs)

    print(f"misconception_classifier_eval: n={len(rows)}")
    print(f"  fine-tuned classifier accuracy (leave-one-out): {classifier_accuracy:.0%}")
    print(f"  prompted-only baseline accuracy: {baseline_accuracy:.0%}")
    if classifier_accuracy >= baseline_accuracy:
        print("  OK: the fine-tuned classifier meets or beats the baseline")
    else:
        print(
            "  NOTE: the fine-tuned classifier does NOT beat the baseline on this "
            "validation set -- reported honestly (FR-007), not treated as a failure"
        )

    return 0


def main() -> int:
    ground_truth_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GROUND_TRUTH_PATH
    if not ground_truth_path.is_file():
        print(f"FAIL: ground-truth fixture not found at {ground_truth_path}")
        return 1
    return asyncio.run(_run(ground_truth_path))


if __name__ == "__main__":
    sys.exit(main())

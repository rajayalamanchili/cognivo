"""Offline training for the per-subject misconception classifier
(research.md §1/§8, spec 013 FR-001/FR-007).

Trains on `evaluation/misconception_ground_truth.jsonl` -- the only
labeled data available, since no `AssessmentEvent` row has ever carried
a misconception label (research.md §6). Rows with no expected
misconception (`expected_misconception_id: null` -- a plain wrong
answer, or a correct one) train as an explicit `NONE_LABEL` class
rather than being dropped: this lets `classify.py`'s confidence
threshold correctly withhold a classification when "no specific
pattern" genuinely scores highest, instead of the classifier being
forced to always pick one of the named patterns.

Never run at request or deploy time -- a human runs this manually after
the labeled dataset changes, then checks the resulting artifact into
`backend/misconception_models/` (T019).

Usage (from `backend/`):
    uv run python scripts/train_misconception_classifier.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.misconception.embed import embed_answer  # noqa: E402

NONE_LABEL = "none"
GROUND_TRUTH_PATH = (
    Path(__file__).resolve().parent.parent / "evaluation" / "misconception_ground_truth.jsonl"
)
MODELS_DIR = Path(__file__).resolve().parent.parent / "misconception_models"
CLASSIFIER_VERSION = "v1"


def _load_rows() -> list[dict]:
    with GROUND_TRUTH_PATH.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def fit_classifier(embeddings: list[list[float]], labels: list[str]) -> LogisticRegression:
    """The one place `LogisticRegression` is constructed and fit --
    shared with `check_misconception_classifier_eval.py`'s leave-one-out
    cross-validation (T031 correction) so both scripts train on
    identically-configured models."""
    model = LogisticRegression(max_iter=1000)
    model.fit(embeddings, labels)
    return model


def train_all_subjects() -> dict[str, Path]:
    """Trains one classifier per `subject_id` present in the ground
    truth fixture, writing each to
    `misconception_models/<subject_id>/v1/classifier.joblib`."""
    rows_by_subject: dict[str, list[dict]] = defaultdict(list)
    for row in _load_rows():
        rows_by_subject[row["subject_id"]].append(row)

    written: dict[str, Path] = {}
    for subject_id, subject_rows in sorted(rows_by_subject.items()):
        embeddings = [
            embed_answer(row["question"], row["learner_answer"]) for row in subject_rows
        ]
        labels = [row["expected_misconception_id"] or NONE_LABEL for row in subject_rows]

        model = fit_classifier(embeddings, labels)

        output_dir = MODELS_DIR / subject_id / CLASSIFIER_VERSION
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "classifier.joblib"
        joblib.dump(model, output_path)
        written[subject_id] = output_path
        print(
            f"trained {subject_id}: {len(subject_rows)} examples, "
            f"classes={sorted(set(labels))} -> {output_path}"
        )

    return written


if __name__ == "__main__":
    train_all_subjects()

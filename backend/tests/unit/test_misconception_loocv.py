"""Unit test: `check_misconception_classifier_eval.py`'s
`_leave_one_out_pairs` never scores a row using a classifier trained on
that same row -- the fix for the train/validation leakage a review
flagged in `run_classification_batch`'s sibling eval script (T031
correction, post-review 2026-09-01): scoring the shipped classifier
against its own training data reports training-fit accuracy, not a
genuine generalization estimate.

Pure function test with a spy `fit_classifier` -- no real model/
embedding call.
"""

from unittest.mock import Mock, patch

import numpy as np

from scripts.check_misconception_classifier_eval import _leave_one_out_pairs


def test_leave_one_out_never_trains_on_the_held_out_row():
    subject_rows = [
        {"id": "r1", "expected_misconception_id": "a"},
        {"id": "r2", "expected_misconception_id": "a"},
        {"id": "r3", "expected_misconception_id": "b"},
    ]
    embedding_by_row_id = {"r1": [1.0], "r2": [2.0], "r3": [3.0]}
    seen_training_embeddings: list[list[list[float]]] = []

    def fake_fit(embeddings, labels):
        seen_training_embeddings.append(list(embeddings))
        model = Mock()
        model.classes_ = ["a", "b"]
        model.predict_proba = Mock(return_value=np.array([[1.0, 0.0]]))
        return model

    with patch(
        "scripts.check_misconception_classifier_eval.fit_classifier", side_effect=fake_fit
    ):
        pairs = _leave_one_out_pairs(subject_rows, embedding_by_row_id)

    assert len(pairs) == 3
    zipped = zip(subject_rows, seen_training_embeddings, strict=True)
    for held_out_row, training_embeddings in zipped:
        held_out_embedding = embedding_by_row_id[held_out_row["id"]]
        assert held_out_embedding not in training_embeddings
        assert len(training_embeddings) == len(subject_rows) - 1

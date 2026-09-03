"""Unit tests: `compute_question_signature()` is the deterministic
"same question" key `question_generation_cache` and `grading_response_
cache` share across different learners' distinct `GeneratedQuestion`
rows (spec 015 research.md §3).
"""

from src.services.cache_common.signature import compute_question_signature


def test_identical_input_hashes_identically():
    stem = "What is the slope of y = 3x + 2?"
    answer_key = {"correct_index": 1, "options_count": 4}
    assert compute_question_signature(stem, answer_key) == compute_question_signature(
        stem, answer_key
    )


def test_different_stem_hashes_differently():
    answer_key = {"correct_index": 1}
    assert compute_question_signature(
        "What is the slope of y = 3x + 2?", answer_key
    ) != compute_question_signature("What is the y-intercept of y = 3x + 2?", answer_key)


def test_different_answer_key_hashes_differently():
    stem = "What is the slope of y = 3x + 2?"
    assert compute_question_signature(stem, {"correct_index": 1}) != compute_question_signature(
        stem, {"correct_index": 2}
    )


def test_dict_key_ordering_does_not_change_the_hash():
    stem = "What is the slope of y = 3x + 2?"
    answer_key_a = {"correct_index": 1, "options_count": 4}
    answer_key_b = {"options_count": 4, "correct_index": 1}
    assert compute_question_signature(stem, answer_key_a) == compute_question_signature(
        stem, answer_key_b
    )

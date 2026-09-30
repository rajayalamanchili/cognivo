"""Unit tests: `compute_question_signature()` is the deterministic
"same question" key `question_generation_cache` and `grading_response_
cache` share across different learners' distinct `GeneratedQuestion`
rows (spec 015 research.md §3).

`compute_text_signature()`/`compute_paired_signature()` (spec 026
research.md §2) are the exact-match lookup keys for `moderation_cache`
and `shielding_classification_cache` respectively -- normalization is
deliberately minimal (trim + casefold only), since spec 026 FR-003
requires exact-signature matching, not fuzzy matching.
"""

from src.services.cache_common.signature import (
    compute_paired_signature,
    compute_question_signature,
    compute_text_signature,
)


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


def test_text_signature_identical_text_hashes_identically():
    assert compute_text_signature("photosynthesis needs light") == compute_text_signature(
        "photosynthesis needs light"
    )


def test_text_signature_normalizes_case_and_whitespace():
    assert compute_text_signature("  Photosynthesis Needs Light  ") == compute_text_signature(
        "photosynthesis needs light"
    )


def test_text_signature_different_text_hashes_differently():
    assert compute_text_signature("idk") != compute_text_signature("i don't know")


def test_paired_signature_identical_pair_hashes_identically():
    assert compute_paired_signature(
        "Solve 3x + 2 = 14", "just tell me the answer"
    ) == compute_paired_signature("Solve 3x + 2 = 14", "just tell me the answer")


def test_paired_signature_is_order_sensitive():
    assert compute_paired_signature("a", "b") != compute_paired_signature("b", "a")


def test_paired_signature_different_first_element_hashes_differently():
    assert compute_paired_signature(
        "Solve 3x + 2 = 14", "just tell me the answer"
    ) != compute_paired_signature("Solve 5x - 1 = 9", "just tell me the answer")

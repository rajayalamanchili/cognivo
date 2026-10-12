"""Unit tests: `is_near_duplicate`'s embedding-based comparison (bug-fix
amendment, 2026-10-12, spec 005 SC-004 / spec 001 SC-002).

Pure-function tests -- no DB, no real Voyage call. Embeddings are
synthetic vectors chosen to exercise specific cosine-similarity values,
not real `embed_stem()` output.
"""

from src.services.dedup.checker import DEFAULT_SIMILARITY_THRESHOLD, is_near_duplicate

# Same-template, different-number quadratics -- real embeddings for
# genuinely distinct questions sharing a phrasing template land well
# under the 0.92 cosine threshold even though they'd have scored
# 0.87-0.94 under the old difflib ratio (this is the exact false
# positive the bug-fix amendment exists to resolve). 0.3 stands in for
# "similar topic/phrasing, different content."
DIFFERENT_QUESTION_SAME_TEMPLATE = [0.3, 0.95393920141]  # normalized-ish, see below
IDENTICAL = [1.0, 0.0]
ORTHOGONAL = [0.0, 1.0]
NEAR_DUPLICATE = [0.99, 0.14106735979665883]  # cosine(IDENTICAL, NEAR_DUPLICATE) ~= 0.99
# cosine(IDENTICAL, PARAPHRASE) ~= 0.89 -- the real value
# `scripts/validate_dedup_threshold.py` measured for a genuine
# same-meaning paraphrase ("what is -3+5?" vs "what is the sum of -3
# and 5?") against real `voyage/voyage-3` output (review finding, PR
# #113: a regression test locking in the documented gap, not just a
# code comment).
PARAPHRASE_BELOW_THRESHOLD = [0.89, 0.45596392738895473]


def test_identical_embeddings_are_near_duplicate():
    assert (
        is_near_duplicate("a new question", IDENTICAL, [("a previous question", IDENTICAL)])
        is True
    )


def test_true_positive_near_duplicate_above_threshold():
    """A genuine near-duplicate (cosine ~0.99) is correctly flagged."""
    assert (
        is_near_duplicate("a new question", NEAR_DUPLICATE, [("a previous question", IDENTICAL)])
        is True
    )


def test_same_template_different_numbers_is_not_near_duplicate():
    """The exact false-positive pattern this bug-fix resolves: two
    distinct questions sharing a phrasing template but different
    content must NOT be flagged once their embeddings are genuinely
    dissimilar (unlike the old difflib check, which scored these as
    0.87-0.94 purely from shared boilerplate text)."""
    assert (
        is_near_duplicate(
            "a new question", DIFFERENT_QUESTION_SAME_TEMPLATE, [("a previous question", IDENTICAL)]
        )
        is False
    )


def test_orthogonal_embeddings_are_not_near_duplicate():
    assert (
        is_near_duplicate("a new question", ORTHOGONAL, [("a previous question", IDENTICAL)])
        is False
    )


def test_candidate_embedding_none_fails_open_to_not_near_duplicate():
    """The candidate itself couldn't be embedded (Voyage outage) --
    fail open rather than blocking generation (research.md §10)."""
    assert is_near_duplicate("a new question", None, [("a previous question", IDENTICAL)]) is False


def test_previous_entry_with_none_embedding_is_excluded_not_treated_as_a_match():
    """A pre-migration row (NULL stem_embedding) is excluded from
    comparison entirely -- not a match, not a non-match signal."""
    assert is_near_duplicate("a new question", IDENTICAL, [("a pre-migration row", None)]) is False


def test_empty_previous_is_never_a_duplicate():
    assert is_near_duplicate("a new question", IDENTICAL, []) is False


def test_threshold_boundary_is_inclusive():
    # A similarity exactly at the default threshold counts as a match.
    assert (
        is_near_duplicate(
            "a new question",
            [1.0, 0.0],
            [("boundary case", [1.0, 0.0])],
            threshold=DEFAULT_SIMILARITY_THRESHOLD,
        )
        is True
    )


def test_paraphrase_below_threshold_is_not_caught_known_gap():
    """Review finding, PR #113: locks in the documented known gap
    (checker.py's DEFAULT_SIMILARITY_THRESHOLD comment) rather than
    leaving it as a comment alone -- a genuine same-meaning paraphrase
    can score below 0.92 and therefore is NOT flagged. Different stem
    text, so the exact-match fallback doesn't catch it either. If this
    starts failing because the threshold changed, that's the point:
    come back and update the comment it mirrors."""
    assert (
        is_near_duplicate(
            "what is the sum of -3 and 5?",
            PARAPHRASE_BELOW_THRESHOLD,
            [("what is -3 + 5?", IDENTICAL)],
        )
        is False
    )


def test_exact_text_match_is_a_duplicate_even_with_no_embedding():
    """Review finding, PR #113: a text-identical repeat must be caught
    even during a Voyage outage (`candidate_embedding=None`), the one
    guarantee the old difflib-ratio check always provided and the new
    embedding-only check would otherwise drop."""
    assert (
        is_near_duplicate("What is -3 + 5?", None, [("What is -3 + 5?", None)]) is True
    )


def test_exact_text_match_is_case_and_whitespace_insensitive():
    assert (
        is_near_duplicate("  What IS -3 + 5?  ", None, [("what is -3 + 5?", None)]) is True
    )


def test_mismatched_embedding_dimensions_fail_open_instead_of_raising():
    """Review finding, PR #113: a dimension mismatch (e.g. a stale
    embedding from before `TUTOR_EMBEDDING_MODEL` changed) must not
    crash the request via `zip(strict=True)` -- it's simply not a
    comparable pair, so it fails open to "not similar"."""
    assert (
        is_near_duplicate("a new question", [1.0, 0.0, 0.0], [("a previous question", [1.0, 0.0])])
        is False
    )

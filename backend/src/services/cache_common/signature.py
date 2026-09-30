"""Content-hash key linking one generated question across different
learners' distinct `GeneratedQuestion` rows (spec 015 research.md §3).

Every generated question is its own per-learner row (`learner_id` is
NOT NULL on `GeneratedQuestion`), so the grading cache can't scope
"the same question" by `question_id` -- two learners served the same
question-generation-cache pool entry still get two different
`question_id`s. This hash is the stable key both `question_generation_
cache` (stored at write time) and `grading_response_cache` (used as a
lookup filter) share instead.
"""

import hashlib
import json


def compute_question_signature(stem: str, answer_key: dict) -> str:
    """Deterministic hash of a question's content. Identical `(stem,
    answer_key)` always hashes identically, independent of `answer_key`'s
    dict key ordering (`sort_keys=True`)."""
    canonical = json.dumps({"stem": stem, "answer_key": answer_key}, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    return text.strip().casefold()


def compute_text_signature(text: str) -> str:
    """Exact-match lookup key for `moderation_cache` (spec 026 research.md
    §2). Normalization is deliberately minimal (trim + casefold) -- FR-003
    requires exact-signature matching, not fuzzy matching, so this only
    absorbs incidental whitespace/case differences, never wording ones."""
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def compute_paired_signature(first: str, second: str) -> str:
    """Exact-match lookup key for `shielding_classification_cache`
    (spec 026 research.md §2), order-sensitive -- `(first, second)` and
    `(second, first)` hash differently, which is what makes matching
    scoped per open-question (FR-004)."""
    canonical = json.dumps([_normalize(first), _normalize(second)])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

"""Quiz session orchestration (spec 005).

`next_quiz_topic` is the pure round-robin rule (research.md §2),
directly unit-testable with no DB. The DB-orchestrating functions
(`start_quiz`, `generate_quiz_question`, `compute_quiz_summary`) that
call it are added in Phase 3 (User Story 1).
"""

from collections.abc import Sequence


def next_quiz_topic(topic_ids: Sequence[str], *, questions_generated_so_far: int) -> str:
    """The topic for this quiz's next question: round-robin through
    `topic_ids` in selection order, one question per topic per cycle
    (Clarifications, 2026-08-18)."""
    return topic_ids[questions_generated_so_far % len(topic_ids)]

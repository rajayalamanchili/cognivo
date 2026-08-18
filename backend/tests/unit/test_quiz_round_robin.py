"""Unit test: round-robin quiz-topic selection (research.md §2), T008.

Pure-function test, no DB -- `next_quiz_topic` is fully determined by
`topic_ids`'s selection order and how many questions this quiz has
generated so far.
"""

from src.services.quiz.session import next_quiz_topic


def test_cycles_through_topics_in_selection_order():
    topic_ids = ["a", "b", "c"]
    assert next_quiz_topic(topic_ids, questions_generated_so_far=0) == "a"
    assert next_quiz_topic(topic_ids, questions_generated_so_far=1) == "b"
    assert next_quiz_topic(topic_ids, questions_generated_so_far=2) == "c"


def test_wraps_around_after_completing_a_full_cycle():
    topic_ids = ["a", "b", "c"]
    assert next_quiz_topic(topic_ids, questions_generated_so_far=3) == "a"
    assert next_quiz_topic(topic_ids, questions_generated_so_far=4) == "b"
    assert next_quiz_topic(topic_ids, questions_generated_so_far=6) == "a"


def test_single_topic_quiz_always_returns_that_topic():
    topic_ids = ["only-topic"]
    for count in range(5):
        assert next_quiz_topic(topic_ids, questions_generated_so_far=count) == "only-topic"

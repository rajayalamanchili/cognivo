"""Unit tests: `grade_entry_topics` (spec 017 FR-002, research.md
Decision 2). Pure function, no DB -- constructs `Topic`/`PrerequisiteEdge`
instances directly rather than persisting them.
"""

from src.agents.diagnostic.agent import grade_entry_topics, preferred_question_type
from src.models.enums import QuestionType
from src.models.prerequisite_edge import PrerequisiteEdge
from src.models.topic import Topic


def _topic(topic_id: str, *, grade: int | None, is_entry_level: bool, order_index: int) -> Topic:
    return Topic(
        subject_id="test-subject",
        topic_id=topic_id,
        display_name=topic_id,
        is_entry_level=is_entry_level,
        skill_definition={},
        order_index=order_index,
        grade=grade,
    )


def _edge(from_topic_id: str, to_topic_id: str) -> PrerequisiteEdge:
    return PrerequisiteEdge(subject_id="test-subject", from_topic_id=from_topic_id, to_topic_id=to_topic_id)


def test_zero_prerequisite_topic_at_lowest_grade_is_entry():
    topic = _topic("t1", grade=6, is_entry_level=True, order_index=0)

    assert grade_entry_topics([topic], []) == [topic]


def test_topic_with_all_prerequisites_in_strictly_lower_grade_is_entry():
    t1 = _topic("t1", grade=6, is_entry_level=True, order_index=0)
    t2 = _topic("t2", grade=7, is_entry_level=False, order_index=1)
    edges = [_edge("t2", "t1")]

    assert grade_entry_topics([t1, t2], edges) == [t1, t2]


def test_topic_with_same_grade_prerequisite_is_not_entry():
    t1 = _topic("t1", grade=7, is_entry_level=True, order_index=0)
    t2 = _topic("t2", grade=7, is_entry_level=False, order_index=1)
    edges = [_edge("t2", "t1")]

    assert grade_entry_topics([t1, t2], edges) == [t1]


def test_topic_with_higher_grade_prerequisite_is_not_entry():
    t1 = _topic("t1", grade=6, is_entry_level=True, order_index=0)
    t2 = _topic("t2", grade=6, is_entry_level=True, order_index=1)
    edges = [_edge("t1", "t2")]  # t1 (grade 6) requires t2 (grade 6) -- not strictly lower

    assert grade_entry_topics([t1, t2], edges) == [t2]


def test_ungraded_subject_falls_back_to_is_entry_level():
    t1 = _topic("t1", grade=None, is_entry_level=True, order_index=0)
    t2 = _topic("t2", grade=None, is_entry_level=False, order_index=1)
    edges = [_edge("t2", "t1")]

    assert grade_entry_topics([t1, t2], edges) == [t1]


def _topic_with_preferred_types(
    preferred: list[str], *, step_grading_enabled: bool
) -> Topic:
    return Topic(
        subject_id="test-subject",
        topic_id="t1",
        display_name="t1",
        is_entry_level=True,
        skill_definition={"skill": {"preferred_question_types": preferred}},
        order_index=0,
        step_grading_enabled=step_grading_enabled,
    )


def test_multi_step_first_is_selected_when_step_grading_enabled():
    topic = _topic_with_preferred_types(["multi_step", "numeric"], step_grading_enabled=True)

    assert preferred_question_type(topic) == QuestionType.MULTI_STEP


def test_multi_step_first_is_skipped_when_step_grading_not_enabled():
    # spec 018 FR-001/data-model.md: step_grading_enabled is the actual
    # runtime gate, not just documentation -- listing multi_step in
    # preferred_question_types without opting in must never select it.
    topic = _topic_with_preferred_types(["multi_step", "numeric"], step_grading_enabled=False)

    assert preferred_question_type(topic) == QuestionType.NUMERIC


def test_multi_step_only_entry_falls_back_to_multiple_choice_when_not_enabled():
    topic = _topic_with_preferred_types(["multi_step"], step_grading_enabled=False)

    assert preferred_question_type(topic) == QuestionType.MULTIPLE_CHOICE

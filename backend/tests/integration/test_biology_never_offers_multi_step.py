"""Integration test: a `biology`-style ungraded topic that never opted
into step grading is never offered as a `multi_step` question -- SC-003's
regression guarantee (spec 018 US3), T028.

Checks every `biology` topic against `preferred_question_type()`, the
exact function `generate_next_question()` calls to pick a question's
type (`sequencing/agent.py`), rather than driving the full next-question
HTTP flow per topic -- `test_second_subject.py` already covers that
flow end to end.
"""

from src.agents.diagnostic.agent import preferred_question_type
from src.models.enums import QuestionType


def test_no_biology_topic_is_step_grading_enabled_or_offers_multi_step(
    db_session, biology_subject
):
    for topic in biology_subject.topics:
        assert topic.step_grading_enabled is False
        assert preferred_question_type(topic) != QuestionType.MULTI_STEP

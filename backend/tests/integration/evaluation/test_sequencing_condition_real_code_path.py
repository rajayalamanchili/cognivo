"""Integration test: the Sequencing Agent condition's topic choice comes
from calling `src.agents.sequencing.agent.select_next_topic` directly,
never a reimplementation of its eligibility/tie-break logic (FR-008,
SC-004; quickstart.md step 5).

Written first per this repo's TDD convention -- fails until
`run_sequencing_condition` (T010) lands in `conditions.py`.
"""

import inspect
import random
from unittest.mock import patch

from src.agents.sequencing.agent import select_next_topic
from src.models.topic import Topic
from src.services.evaluation import conditions


def test_conditions_module_imports_select_next_topic_directly():
    # An import, not a re-derivation -- source-level check per
    # quickstart.md step 5's "an import, not a re-derivation" wording.
    source = inspect.getsource(conditions)
    assert "from src.agents.sequencing.agent import" in source
    assert conditions.select_next_topic is select_next_topic


def test_sequencing_condition_actually_calls_select_next_topic(db_session, algebra_subject):
    topics = (
        db_session.query(Topic)
        .filter(Topic.subject_id == algebra_subject.subject_id)
        .order_by(Topic.order_index)
        .all()
    )
    # At least one topic must be genuinely masterable -- an all-False
    # ground truth would short-circuit before ever calling
    # select_next_topic (FR-004; Clarifications, session 2026-08-17).
    true_mastery = {topic.topic_id: False for topic in topics}
    true_mastery[topics[0].topic_id] = True

    with patch.object(conditions, "select_next_topic", wraps=conditions.select_next_topic) as spy:
        outcome = conditions.run_sequencing_condition(
            db_session,
            subject_id=algebra_subject.subject_id,
            topics=topics,
            true_mastery=true_mastery,
            max_questions_per_topic=1,
            rng=random.Random(1),
        )

    assert spy.call_count > 0
    assert outcome is not None

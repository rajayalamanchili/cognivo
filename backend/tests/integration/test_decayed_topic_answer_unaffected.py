"""Integration test: answering a decayed mastered topic updates
mastery through the exact same, unmodified BKT path as any other
answer (spec 024 US2, FR-002/FR-011/SC-003).

Requires a reachable `DATABASE_URL` (mirrors `test_mastery_tool.py`) --
tests `apply_mastery_update` directly against a real, backdated
`MasteryState` row rather than driving the full HTTP answer-submission
stack (grading/moderation/rate-limit), matching this repo's existing
test-boundary convention for this function. Independently seeds its
own scenario rather than sharing a fixture with
`test_next_topic_decay_fallback.py`, per that repo convention.
"""

import datetime

import pytest

from src.agents.sequencing.mastery_tool import apply_mastery_update
from src.models.enums import QuestionType
from src.models.mastery_state import MasteryState
from src.services.mastery.bkt import MasteryObservation, apply_bkt_update
from src.services.mastery.decay import GRACE_PERIOD, HALF_LIFE

pytestmark = pytest.mark.usefixtures("database_available")

_TOPIC_ID = "integers-and-operations"
_RAW_P_MASTERY = 0.8


def _seed_decayed_mastered_topic(db_session, *, learner_id, subject_id):
    backdated = datetime.datetime.now(datetime.UTC) - GRACE_PERIOD - HALF_LIFE * 3
    db_session.add(
        MasteryState(
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=_TOPIC_ID,
            p_mastery=_RAW_P_MASTERY,
            update_count=1,
            consecutive_mastered_observations=2,
            updated_at=backdated,
        )
    )
    db_session.commit()


def test_answering_a_decayed_topic_uses_the_raw_undecayed_prior(
    db_session, demo_learner, algebra_subject
):
    _seed_decayed_mastered_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )

    result = apply_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id=_TOPIC_ID,
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    db_session.commit()

    expected = apply_bkt_update(
        MasteryObservation(p_mastery=_RAW_P_MASTERY, consecutive_mastered_observations=2),
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )

    # FR-011: the decayed value (which would be well below _RAW_P_MASTERY
    # at this elapsed time) is never used -- prior is the raw, persisted
    # value, and the posterior matches apply_bkt_update from that prior
    # exactly, byte-identical to answering any other topic.
    assert result.prior_p_mastery == _RAW_P_MASTERY
    assert result.posterior_p_mastery == expected.p_mastery

    updated = db_session.get(
        MasteryState, (demo_learner.learner_id, algebra_subject.subject_id, _TOPIC_ID)
    )
    assert updated.p_mastery == expected.p_mastery
    # Decay restarts from this fresh answer.
    assert updated.updated_at > datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1)

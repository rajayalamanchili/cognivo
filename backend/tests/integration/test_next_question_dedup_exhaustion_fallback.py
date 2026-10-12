"""Integration test: Milestone 1's dedup-exhaustion fallback still works
under the embedding-based check (spec 001 Edge Cases, Clarifications
2026-10-12; `/speckit-analyze` finding E1).

Unlike the quiz path (`QuizEndedEarlyError` -> `ended_early`),
`generate_next_question` has no "give up visibly" state -- on retry
exhaustion it falls back to serving the last draft generated, even
though it's still a near-duplicate, since every `next-question` request
must return a question. This predates the bug-fix amendment; this test
confirms that fallback doesn't raise or hang once the comparison moved
from text similarity to embedding cosine similarity.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from src.agents.sequencing.agent import DEFAULT_MAX_DEDUP_ATTEMPTS, generate_next_question
from src.models.enums import DifficultyBand, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState
from src.observability.session import get_database_session_service
from tests.conftest import deterministic_embedding

_TARGET_TOPIC_ID = "integers-and-operations"
_OTHER_ALGEBRA_TOPIC_IDS = [
    "variables-and-expressions",
    "order-of-operations",
    "solving-one-step-equations",
    "solving-multi-step-equations",
    "linear-inequalities",
    "systems-of-linear-equations",
    "graphing-linear-equations",
]
_REPEATED_STEM = "Solve for x: (x - 3)(x + 7) = 0"


async def _run_agent_once(agent, session_service):
    import json

    return json.dumps(
        {
            "question_type": "multiple_choice",
            "stem": _REPEATED_STEM,
            "options": ["a", "b", "c", "d"],
            "correct_index": 1,
            "correct_value": None,
            "tolerance": None,
        }
    )


def test_generate_next_question_falls_back_to_last_draft_when_every_attempt_collides(
    db_session, demo_learner, algebra_subject
):
    db_session.merge(
        GradeProgress(
            learner_id=demo_learner.learner_id,
            subject_id=algebra_subject.subject_id,
            unlocked_grade=8,
        )
    )
    for topic_id in _OTHER_ALGEBRA_TOPIC_IDS:
        db_session.merge(
            MasteryState(
                learner_id=demo_learner.learner_id,
                subject_id=algebra_subject.subject_id,
                topic_id=topic_id,
                p_mastery=0.9,
                update_count=2,
                consecutive_mastered_observations=2,
            )
        )
    # Seed one prior question on the target topic with the *same* stem
    # the mock will keep returning -- every one of
    # DEFAULT_MAX_DEDUP_ATTEMPTS attempts below collides with this row
    # (identical text -> identical deterministic embedding -> cosine
    # 1.0), reproducing genuine retry exhaustion.
    db_session.add(
        GeneratedQuestion(
            learner_id=demo_learner.learner_id,
            subject_id=algebra_subject.subject_id,
            topic_id=_TARGET_TOPIC_ID,
            difficulty=DifficultyBand.EASY,
            question_type=QuestionType.MULTIPLE_CHOICE,
            stem=_REPEATED_STEM,
            stem_embedding=deterministic_embedding(_REPEATED_STEM),
            options=["a", "b", "c", "d"],
            answer_key={"correct_index": 1},
            validation_status=ValidationStatus.VALID,
            generation_prompt_version="v1",
        )
    )
    db_session.commit()

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_run_agent_once),
    ):
        result = asyncio.run(
            generate_next_question(
                db_session,
                learner_id=demo_learner.learner_id,
                subject_id=algebra_subject.subject_id,
                session_service=get_database_session_service(),
                max_dedup_attempts=DEFAULT_MAX_DEDUP_ATTEMPTS,
            )
        )

    # No exception -- the fallback kicks in and a (still-duplicate)
    # draft is returned rather than the request failing.
    assert result.draft.stem == _REPEATED_STEM
    assert result.selection.topic_id == _TARGET_TOPIC_ID
    assert result.stem_embedding is not None

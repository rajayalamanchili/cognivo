"""Shared helpers for free-text integration tests (spec 007, T013-T025).

Mirrors `quiz_helpers.py`'s pattern of mocking the Assessment-Generation
Agent's LLM call boundary (`_run_agent_once`), plus equivalent boundary
mocks for the Grading Agent's A2A response and the moderation check, so
these tests exercise the real guardrail/grading-orchestration path in
`api/routes/questions.py` without depending on any live LLM or A2A call.
"""

import json
import uuid
from collections.abc import Sequence
from unittest.mock import AsyncMock, patch

from src.models.mastery_state import MasteryState
from src.services.grading_client.client import SCORE_THRESHOLD, GradingResult

# The one algebra-1 topic opted into `free_text` (research.md §10,
# content/algebra-1/subject.yaml).
FREE_TEXT_TOPIC_ID = "graphing-linear-equations"

# Every other algebra-1 topic, in `Topic.order_index` order (mirrors
# `test_next_topic_fallback.py`'s `_ALGEBRA_TOPIC_IDS_IN_ORDER`).
_OTHER_ALGEBRA_TOPIC_IDS = [
    "integers-and-operations",
    "variables-and-expressions",
    "order-of-operations",
    "solving-one-step-equations",
    "solving-multi-step-equations",
    "linear-inequalities",
    "systems-of-linear-equations",
]

DEFAULT_RUBRIC_CRITERIA = [
    {"description": "Correctly identifies the independent variable", "weight": 0.4},
    {"description": "Correctly identifies the dependent variable", "weight": 0.6},
]


def make_free_text_topic_next_up(db_session, learner_id, subject_id) -> None:
    """Masters every algebra-1 topic except `FREE_TEXT_TOPIC_ID`, whose
    prerequisite (`solving-multi-step-equations`) is included -- leaving
    it the sole `unknown`-band, prerequisite-satisfied topic, and
    therefore `next-question`'s only eligible pick (data-model.md's
    Next-topic eligibility rule). Uses `merge` (not `add`), since some
    tests call this twice for the same learner/subject (e.g. to fetch
    two separate free-text questions) and a plain `add` would violate
    `mastery_states`' primary key on the second call."""
    for topic_id in _OTHER_ALGEBRA_TOPIC_IDS:
        db_session.merge(
            MasteryState(
                learner_id=learner_id,
                subject_id=subject_id,
                topic_id=topic_id,
                p_mastery=0.9,
                update_count=2,
                consecutive_mastered_observations=2,
            )
        )
    db_session.commit()


def free_text_draft_json(
    stem: str = "Identify the independent and dependent variables in: y = 3x + 2",
    criteria: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            "question_type": "free_text",
            "stem": stem,
            "options": None,
            "correct_index": None,
            "correct_value": None,
            "tolerance": None,
            "rubric_criteria": criteria if criteria is not None else DEFAULT_RUBRIC_CRITERIA,
        }
    )


def patch_free_text_generation(
    stems: Sequence[str] | None = None, criteria: list[dict] | None = None
):
    """Patches `_run_agent_once` (the same LLM-call boundary
    `quiz_helpers.patch_generation` mocks) to return a valid free-text
    draft -- a fresh UUID-suffixed stem per call unless `stems` is given."""
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        if stems is not None:
            stem = stems[(call_count["n"] - 1) % len(stems)]
        else:
            stem = f"free-text question {uuid.uuid4()}"
        return free_text_draft_json(stem, criteria)

    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    )


def get_free_text_question(client, db_session, learner, subject, *, stems=None, criteria=None):
    """Sets up eligibility for `FREE_TEXT_TOPIC_ID`, fetches it via the
    real `next-question` endpoint (mocked at the LLM-call boundary), and
    returns the parsed JSON response -- the common setup every
    answer-side test in this file needs."""
    make_free_text_topic_next_up(db_session, learner.learner_id, subject.subject_id)
    with patch_free_text_generation(stems=stems, criteria=criteria):
        response = client.get(
            f"/api/learners/{learner.learner_id}/next-question",
            params={"subject_id": subject.subject_id},
        )
    assert response.status_code == 200, response.text
    return response.json()


def patch_moderation(allowed: bool = True):
    """Patches the moderation check as imported into `questions.py`
    (bound by name at import time, so the patch target is the route
    module, not `services/grading_client/moderation.py` itself)."""
    return patch(
        "src.api.routes.questions.check_moderation",
        new=AsyncMock(return_value=allowed),
    )


def patch_grading_result(
    *,
    graduated_score: float,
    criteria_met: list[str] | None = None,
    criteria_missed: list[str] | None = None,
    grading_logic_version: str = "v1",
    side_effect=None,
):
    """Patches the Grading Agent A2A call as imported into
    `questions.py`. Pass `side_effect` (an exception or async callable)
    to simulate a failure instead of a graded result."""
    if side_effect is not None:
        mock = AsyncMock(side_effect=side_effect)
    else:
        result = GradingResult(
            correct=graduated_score >= SCORE_THRESHOLD,
            graduated_score=graduated_score,
            criteria_met=criteria_met or [],
            criteria_missed=criteria_missed or [],
            grading_logic_version=grading_logic_version,
        )
        mock = AsyncMock(return_value=result)
    return patch("src.api.routes.questions.grade_free_text_answer", new=mock)

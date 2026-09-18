"""Shared helpers for multi-step integration tests (spec 018, T011-T014,
T037).

Mirrors `free_text_helpers.py`'s pattern of mocking the Assessment-
Generation Agent's LLM call boundary (`_run_agent_once`) plus the Grading
Agent's A2A response and the moderation check, so these tests exercise
the real guardrail/grading-orchestration path in `api/routes/questions.py`
without depending on any live LLM or A2A call.

Unlike `free_text_helpers.py`, this feature's real content-artifact
retrofit (`process_level_grading: true` on an `algebra-1` topic) is
Phase 5's job (tasks.md T030), not yet applied to `content/algebra-1/
subject.yaml` at this point in the build -- so these helpers opt a topic
into step grading directly on its already-persisted `Topic` row instead
of relying on the YAML content artifact.
"""

import json
import uuid
from collections.abc import Sequence
from unittest.mock import AsyncMock, patch

from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState
from src.models.topic import Topic

# Named for exactly this purpose in content/algebra-1/subject.yaml
# (grade 7, prereqs solving-one-step-equations + order-of-operations).
MULTI_STEP_TOPIC_ID = "solving-multi-step-equations"

_OTHER_ALGEBRA_TOPIC_IDS = [
    "integers-and-operations",
    "variables-and-expressions",
    "order-of-operations",
    "solving-one-step-equations",
    "linear-inequalities",
    "graphing-linear-equations",
    "systems-of-linear-equations",
]

DEFAULT_STEPS = [
    {
        "step_prompt": "Isolate the variable term on one side.",
        "criteria": [
            {"description": "Chooses to subtract 2 from both sides", "weight": 0.5},
            {"description": "Correctly computes 3x = 12", "weight": 0.5},
        ],
    },
    {
        "step_prompt": "Solve for x.",
        "criteria": [
            {"description": "Chooses to divide both sides by 3", "weight": 0.5},
            {"description": "Correctly computes x = 4", "weight": 0.5},
        ],
    },
]


def opt_topic_into_step_grading(db_session, subject_id: str) -> None:
    """Directly opts `MULTI_STEP_TOPIC_ID` into step grading on its
    already-persisted `Topic` row (T030's real content-artifact retrofit
    is Phase 5, not yet applied here)."""
    topic = db_session.get(Topic, (subject_id, MULTI_STEP_TOPIC_ID))
    topic.step_grading_enabled = True
    skill_definition = dict(topic.skill_definition)
    skill = dict(skill_definition.get("skill") or {})
    skill["preferred_question_types"] = ["multi_step"]
    skill_definition["skill"] = skill
    topic.skill_definition = skill_definition
    db_session.commit()


def make_multi_step_topic_next_up(db_session, learner_id, subject_id) -> None:
    """Masters every algebra-1 topic except `MULTI_STEP_TOPIC_ID`, whose
    prerequisites are included -- leaving it the sole `unknown`-band,
    prerequisite-satisfied topic (data-model.md's Next-topic eligibility
    rule), mirroring `free_text_helpers.make_free_text_topic_next_up`."""
    db_session.merge(GradeProgress(learner_id=learner_id, subject_id=subject_id, unlocked_grade=8))
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


def multi_step_draft_json(
    stem: str = "Solve for x: 3x + 2 = 14", steps: list[dict] | None = None
) -> str:
    used_steps = steps if steps is not None else DEFAULT_STEPS
    return json.dumps(
        {
            "question_type": "multi_step",
            "stem": stem,
            "options": None,
            "correct_index": None,
            "correct_value": None,
            "tolerance": None,
            "rubric_criteria": None,
            "steps": [
                {
                    "step_prompt": step["step_prompt"],
                    "rubric_criteria": step["criteria"],
                }
                for step in used_steps
            ],
        }
    )


def patch_multi_step_generation(
    stems: Sequence[str] | None = None, steps: list[dict] | None = None
):
    """Patches `_run_agent_once` (the same LLM-call boundary
    `free_text_helpers.patch_free_text_generation` mocks) to return a
    valid multi_step draft -- a fresh UUID-suffixed stem per call unless
    `stems` is given."""
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        if stems is not None:
            stem = stems[(call_count["n"] - 1) % len(stems)]
        else:
            stem = f"multi-step question {uuid.uuid4()}"
        return multi_step_draft_json(stem, steps)

    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    )


def get_multi_step_question(client, db_session, learner, subject, *, stems=None, steps=None):
    """Sets up eligibility for `MULTI_STEP_TOPIC_ID`, fetches it via the
    real `next-question` endpoint (mocked at the LLM-call boundary), and
    returns the parsed JSON response -- the common setup every
    answer-side test in this file needs."""
    opt_topic_into_step_grading(db_session, subject.subject_id)
    make_multi_step_topic_next_up(db_session, learner.learner_id, subject.subject_id)
    with patch_multi_step_generation(stems=stems, steps=steps):
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


def stepwise_agent_response_json(
    *,
    graduated_score: float,
    first_diverging_step_index: int | None,
    step_results: list[dict],
    grading_logic_version: str = "v1",
) -> str:
    """Builds a raw Grading Agent A2A response matching contracts/api.md's
    multi-step shape -- for patching `_call_grading_agent_once`."""
    return json.dumps(
        {
            "graduated_score": graduated_score,
            "first_diverging_step_index": first_diverging_step_index,
            "step_results": step_results,
            "grading_logic_version": grading_logic_version,
        }
    )


def all_correct_agent_response(steps: list[dict] | None = None) -> str:
    used_steps = steps if steps is not None else DEFAULT_STEPS
    return stepwise_agent_response_json(
        graduated_score=1.0,
        first_diverging_step_index=None,
        step_results=[
            {
                "step_index": index,
                "criteria_results": [
                    {"description": c["description"], "met": True} for c in step["criteria"]
                ],
            }
            for index, step in enumerate(used_steps)
        ],
    )


def diverges_at_step_response(step_index: int, steps: list[dict] | None = None) -> str:
    """Every step up to `step_index` is fully correct; `step_index`
    itself has its first criterion met and its remaining criteria
    missed (a realistic "right method, wrong execution" divergence)."""
    used_steps = steps if steps is not None else DEFAULT_STEPS
    step_results = []
    for index in range(step_index + 1):
        criteria = used_steps[index]["criteria"]
        if index < step_index:
            met_flags = [True] * len(criteria)
        else:
            met_flags = [True] + [False] * (len(criteria) - 1)
        step_results.append(
            {
                "step_index": index,
                "criteria_results": [
                    {"description": c["description"], "met": met}
                    for c, met in zip(criteria, met_flags, strict=True)
                ],
            }
        )
    correct_step_count = step_index
    total_steps = len(used_steps)
    return stepwise_agent_response_json(
        graduated_score=correct_step_count / total_steps,
        first_diverging_step_index=step_index,
        step_results=step_results,
    )


def patch_grading_agent_call(*, response_text: str | None = None, side_effect=None):
    """Patches the Grading Agent A2A call boundary as imported into
    `grading_client/client.py` (`_call_grading_agent_once`) -- the same
    boundary `test_free_text_grading_unavailable.py`/`test_free_text_
    response_validation.py` patch, one level below `grade_stepwise_
    answer()` so the real request-building/validation/retry logic in
    `client.py` still runs."""
    if side_effect is not None:
        mock = AsyncMock(side_effect=side_effect)
    else:
        mock = AsyncMock(return_value=response_text)
    return patch("src.services.grading_client.client._call_grading_agent_once", new=mock)

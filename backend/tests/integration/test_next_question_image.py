"""Integration test: `GET /api/learners/{learner_id}/next-question`
returns `image_url`/`image_alt_text` for an image-bearing topic, and
`null` for both when the selected topic has no `image_asset` (User
Story 1 Acceptance Scenarios 1 & 3, spec 003).

Question generation is mocked at the LLM-call boundary
(`_run_agent_once`), mirroring `test_next_question_variety.py`'s own
convention, so this test exercises the real topic-selection +
image-attachment + persistence + response path without depending on a
live LLM call. Mastery state is hand-crafted (mirroring
`test_next_topic_eligibility.py`'s `_set_mastery` convention) to
deterministically force selection of `systems-of-linear-equations` --
the algebra-1 topic this feature's content authoring (tasks.md T022)
gave a real `image_asset`.
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.mastery_state import MasteryState

MASTERED_P = 0.9
MASTERED_CONSECUTIVE = 2


def _set_mastery(db_session, learner_id, subject_id, topic_id, *, p_mastery, consecutive=0):
    state = MasteryState(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        p_mastery=p_mastery,
        update_count=1,
        consecutive_mastered_observations=consecutive,
    )
    db_session.add(state)
    db_session.commit()
    return state


def _draft_json(question_type: str, stem: str) -> str:
    return json.dumps(
        {
            "question_type": question_type,
            "stem": stem,
            "options": ["a", "b", "c", "d"] if question_type == "multiple_choice" else None,
            "correct_index": 1 if question_type == "multiple_choice" else None,
            "correct_value": None,
            "tolerance": None,
        }
    )


def test_image_bearing_topic_returns_image_fields(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    # Master every other topic so systems-of-linear-equations is the
    # sole non-mastered (hence eligible) topic left, with its own
    # prerequisites also mastered so it's prereq-satisfied -- an
    # "unknown"-banded topic ranks ahead of any numeric p_mastery
    # (data-model.md's Next-topic eligibility rule), so leaving any
    # other topic unknown/eligible would win instead.
    for topic in algebra_subject.topics:
        if topic.topic_id == "systems-of-linear-equations":
            continue
        _set_mastery(
            db_session,
            demo_learner.learner_id,
            algebra_subject.subject_id,
            topic.topic_id,
            p_mastery=MASTERED_P,
            consecutive=MASTERED_CONSECUTIVE,
        )

    client = TestClient(app)
    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_draft_json("multiple_choice", "Which point solves the system?")),
    ):
        response = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": algebra_subject.subject_id},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["topic_id"] == "systems-of-linear-equations"
    assert body["image_url"] == "/content-images/algebra-1/systems-of-equations-graph.svg"
    assert body["image_alt_text"] == (
        "A coordinate plane showing two intersecting lines, y = x + 1 and "
        "y = -x + 5, crossing at the point (2, 3), which is the system's "
        "solution."
    )


def test_topic_without_image_asset_returns_null_image_fields(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    # One unrelated MasteryState row, only to satisfy the endpoint's
    # placement-completed gate -- systems-of-linear-equations' own
    # prerequisites are still unsatisfied, so it stays ineligible and
    # doesn't affect which topic actually gets ranked first. With no
    # other state, only the two zero-prerequisite entry topics
    # (integers-and-operations, variables-and-expressions) are
    # eligible, and neither has an image_asset.
    _set_mastery(
        db_session,
        demo_learner.learner_id,
        algebra_subject.subject_id,
        "systems-of-linear-equations",
        p_mastery=0.5,
    )
    client = TestClient(app)
    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_draft_json("multiple_choice", "What is -3 + 7?")),
    ):
        response = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": algebra_subject.subject_id},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["topic_id"] in ("integers-and-operations", "variables-and-expressions")
    assert body["image_url"] is None
    assert body["image_alt_text"] is None

"""Integration test: `POST /api/questions/{question_id}/answer` for an
image-based question produces the exact same response shape and
grading outcome as a text-only question of the same `question_type`
(User Story 1 Acceptance Scenario 2, FR-004, SC-001) -- no new fields,
no new error cases, same deterministic answer-key comparison.

Mocks `_run_agent_once` (same convention as
`test_next_question_image.py`/`test_next_question_variety.py`) so this
exercises the real grading + mastery-update path without a live LLM
call.
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


def _mc_draft_json(stem: str) -> str:
    return json.dumps(
        {
            "question_type": "multiple_choice",
            "stem": stem,
            "options": ["a", "b", "c", "d"],
            "correct_index": 1,
            "correct_value": None,
            "tolerance": None,
        }
    )


def _get_next_question(client, learner_id, subject_id):
    response = client.get(
        f"/api/learners/{learner_id}/next-question", params={"subject_id": subject_id}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _answer(client, question_id, response_value):
    response = client.post(
        f"/api/questions/{question_id}/answer", json={"response": response_value}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_image_and_text_only_answers_share_identical_shape_and_grading(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)

    # Force selection of the image-bearing topic (same technique as
    # test_next_question_image.py): master every other topic so
    # systems-of-linear-equations is the sole eligible one left.
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

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_mc_draft_json("Which point solves the system?")),
    ):
        image_question = _get_next_question(
            client, demo_learner.learner_id, algebra_subject.subject_id
        )
        assert image_question["image_url"] is not None

        image_correct_body = _answer(client, image_question["question_id"], 1)
        image_incorrect_body = _answer(
            client,
            _get_next_question(client, demo_learner.learner_id, algebra_subject.subject_id)[
                "question_id"
            ],
            0,
        )

    # A second, fresh learner gets a text-only entry-topic question of
    # the same question_type, with no mastery setup at all.
    from src.models.learner_profile import LearnerProfile

    text_only_learner = LearnerProfile(display_name="Text-Only Comparison Learner", is_demo=True)
    db_session.add(text_only_learner)
    db_session.commit()
    db_session.refresh(text_only_learner)
    # This learner also needs placement data before next-question will
    # serve it (routes/questions.py's has_placement_data gate) --
    # any MasteryState row satisfies it without affecting which entry
    # topic wins (both start "unknown").
    _set_mastery(
        db_session,
        text_only_learner.learner_id,
        algebra_subject.subject_id,
        "systems-of-linear-equations",
        p_mastery=0.5,
    )

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_mc_draft_json("What is -3 + 7?")),
    ):
        text_question = _get_next_question(
            client, text_only_learner.learner_id, algebra_subject.subject_id
        )
        assert text_question["image_url"] is None

        text_correct_body = _answer(client, text_question["question_id"], 1)
        text_incorrect_body = _answer(
            client,
            _get_next_question(client, text_only_learner.learner_id, algebra_subject.subject_id)[
                "question_id"
            ],
            0,
        )

    # Identical response shape (same key set) regardless of whether the
    # question that was answered carried an image.
    assert set(image_correct_body.keys()) == set(text_correct_body.keys())
    assert set(image_incorrect_body.keys()) == set(text_incorrect_body.keys())
    assert "image_url" not in image_correct_body
    assert "image_alt_text" not in image_correct_body

    # Identical deterministic grading outcome for the same response
    # against the same correct_index=1 answer key.
    assert image_correct_body["correct"] is True
    assert text_correct_body["correct"] is True
    assert image_incorrect_body["correct"] is False
    assert text_incorrect_body["correct"] is False

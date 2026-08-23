"""Shared setup helpers for quiz-assignment integration tests
(`test_quiz_assignment_*.py`) -- registering an instructor+roster and a
guardian+learner enrolled in it is common ~7-call setup every one of
these test files needs; this avoids re-implementing it independently in
each, the same role `quiz_helpers.py` plays for LLM-generation mocking.
"""

ENTRY_TOPIC = "integers-and-operations"


def register_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def login_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def register_guardian_with_learner(client, *, guardian_email, learner_name):
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": guardian_email, "password": "correct horse"},
    )
    assert register.status_code == 201, register.text
    learner = client.post("/api/learners", json={"display_name": learner_name})
    assert learner.status_code == 201, learner.text
    return register.json()["guardian_id"], learner.json()["learner_id"]


def login_guardian(client, email):
    response = client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def create_roster(client, *, subject_id, enrollment_mode="open"):
    response = client.post(
        "/api/rosters", json={"subject_id": subject_id, "enrollment_mode": enrollment_mode}
    )
    assert response.status_code == 201, response.text
    return response.json()["roster_id"], response.json()["join_code"]


def join_roster(client, *, learner_id, join_code):
    response = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert response.status_code == 201, response.text


def create_assignment(
    client,
    *,
    roster_id,
    topic_ids=(ENTRY_TOPIC,),
    question_count=3,
    due_at=None,
    learner_ids="all",
):
    response = client.post(
        f"/api/rosters/{roster_id}/assignments",
        json={
            "topic_ids": list(topic_ids),
            "question_count": question_count,
            "due_at": due_at,
            "learner_ids": learner_ids,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()

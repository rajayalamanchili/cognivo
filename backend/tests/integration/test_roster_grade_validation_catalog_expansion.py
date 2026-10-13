"""Integration test: Milestone 040's existing `POST /api/rosters`
`grade` validation (FR-009) is reused unchanged against all six new
subjects' own `grade_bands` (spec 046 User Story 2, tasks.md T014) --
including, for the first time, the low end of the grade range
(`elementary-math`/`elementary-science`, grades 1-5).

No new engine code is exercised here -- `ClassroomRoster.grade` and
`_check_grade_matches_subject` are Milestone 040's unmodified code;
this test only proves the mechanism generalizes to new `grade_bands`
data, mirroring `test_roster_grade_validation.py`'s existing pattern.
"""

import pytest

from tests.integration.quiz_assignment_helpers import login_instructor, register_instructor

pytestmark = pytest.mark.usefixtures("database_available")

_INSTRUCTOR_EMAIL = "roster-grade-catalog-expansion-instructor@example.com"

# (subject_id, grade_bands, a grade outside the band, a grade inside it)
_CASES = [
    ("pre-algebra", (6, 7), 9, 6),
    ("geometry", (9, 10), 8, 9),
    ("chemistry", (9, 10), 11, 10),
    ("earth-science", (6,), 7, 6),
    ("elementary-math", (1, 2, 3, 4, 5), 6, 3),
    ("elementary-science", (1, 2, 3, 4, 5), 8, 1),
]


def _client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


@pytest.mark.parametrize("subject_id,grade_bands,bad_grade,good_grade", _CASES)
def test_mismatched_grade_rejected_matching_grade_accepted(
    request, monkeypatch, subject_id, grade_bands, bad_grade, good_grade
):
    # Load the subject's content artifact (GradeBand rows) via the
    # matching conftest fixture, e.g. "pre_algebra_subject".
    request.getfixturevalue(subject_id.replace("-", "_") + "_subject")

    client = _client(monkeypatch)
    register_instructor(client, _INSTRUCTOR_EMAIL + subject_id)
    login_instructor(client, _INSTRUCTOR_EMAIL + subject_id)

    rejected = client.post(
        "/api/rosters",
        json={"subject_id": subject_id, "enrollment_mode": "open", "grade": bad_grade},
    )
    assert rejected.status_code == 422, (subject_id, rejected.text)

    accepted = client.post(
        "/api/rosters",
        json={"subject_id": subject_id, "enrollment_mode": "open", "grade": good_grade},
    )
    assert accepted.status_code == 201, (subject_id, accepted.text)
    assert accepted.json()["grade"] == good_grade

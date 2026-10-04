"""Unit tests: the content artifact's optional per-topic
`career_connection` field (spec 039 FR-001/FR-002, data-model.md). Pure
validation tests against `validate_content_artifact()` directly -- no
filesystem/DB access, mirroring `test_content_artifact_standards_
validation.py`. `test_career_connection_persists_and_round_trips` is the
one exception, exercising `persist_content_artifact` against a real DB
(skips cleanly without one, per `tests/conftest.py`).
"""

import pytest

from src.models.topic import Topic
from src.services.content_artifact.loader import persist_content_artifact
from src.services.content_artifact.validator import (
    ContentArtifactValidationError,
    validate_content_artifact,
)

_CAREER_CONNECTION = {
    "career": "Civil Engineer",
    "description": "Civil engineers use the same equations to calculate load limits on bridges.",
}


def _artifact(topic_overrides: dict, *, graded: bool = False) -> dict:
    topic = {
        "topic_id": "topic-1",
        "display_name": "Topic One",
        "skill_definition": {"summary": "A topic used only to test career_connection validation."},
        **topic_overrides,
    }
    artifact: dict = {
        "subject_id": "test-subject",
        "display_name": "Test Subject",
        "content_version": "1.0.0",
        "topics": [topic],
    }
    if graded:
        artifact["grade_bands"] = [6]
        topic["grade"] = 6
    return artifact


def test_no_career_connection_field_validates_cleanly():
    artifact = validate_content_artifact(_artifact({}))

    assert artifact.topics[0].career_connection is None


def test_valid_career_connection_validates_and_normalizes():
    artifact = validate_content_artifact(_artifact({"career_connection": _CAREER_CONNECTION}))

    assert artifact.topics[0].career_connection == _CAREER_CONNECTION


def test_career_connection_on_ungraded_topic_validates_cleanly():
    """research.md Decision 2: unlike `standards`, there is no grade-gate
    -- a career connection may be declared on an ungraded topic."""
    artifact = validate_content_artifact(
        _artifact({"career_connection": _CAREER_CONNECTION}, graded=False)
    )

    assert artifact.topics[0].career_connection == _CAREER_CONNECTION


def test_career_connection_not_a_mapping_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="must be a mapping"):
        validate_content_artifact(_artifact({"career_connection": ["not", "a", "mapping"]}))


def test_career_connection_missing_career_fails_validation():
    bad = {k: v for k, v in _CAREER_CONNECTION.items() if k != "career"}
    with pytest.raises(ContentArtifactValidationError, match="career_connection.career"):
        validate_content_artifact(_artifact({"career_connection": bad}))


def test_career_connection_missing_description_fails_validation():
    bad = {k: v for k, v in _CAREER_CONNECTION.items() if k != "description"}
    with pytest.raises(ContentArtifactValidationError, match="career_connection.description"):
        validate_content_artifact(_artifact({"career_connection": bad}))


def test_career_connection_persists_and_round_trips(db_session):
    """T006: `persist_content_artifact` upserts `Topic.career_connection`
    in place, the same way it already sets `image_asset`."""
    artifact = validate_content_artifact(_artifact({"career_connection": _CAREER_CONNECTION}))

    persist_content_artifact(db_session, artifact)

    row = db_session.get(Topic, ("test-subject", "topic-1"))
    assert row.career_connection == _CAREER_CONNECTION

    # Reloading without the field clears it in place -- upsert, not
    # delete-and-recreate (there is no separate row to drop).
    reloaded = validate_content_artifact(_artifact({}))
    persist_content_artifact(db_session, reloaded)

    db_session.refresh(row)
    assert row.career_connection is None

"""Unit tests: the content artifact's optional per-topic `standards`
field (spec 038 FR-001/FR-003/FR-012, data-model.md). Pure validation
tests against `validate_content_artifact()` directly -- no filesystem/DB
access, mirroring `test_content_artifact_misconceptions_validation.py`.
`test_standards_tags_persist_and_round_trip` is the one exception,
exercising `persist_content_artifact` against a real DB (skips cleanly
without one, per `tests/conftest.py`).
"""

import pytest

from src.models.standards_tag import StandardsTag
from src.services.content_artifact.loader import persist_content_artifact
from src.services.content_artifact.validator import (
    ContentArtifactValidationError,
    validate_content_artifact,
)

_GRADED_TOPIC = {
    "topic_id": "topic-1",
    "display_name": "Topic One",
    "grade": 6,
    "skill_definition": {"summary": "A topic used only to test standards validation."},
}

_STANDARD = {
    "framework": "Common Core Math",
    "code": "CCSS.MATH.CONTENT.6.NS.C.5",
    "title": "Understand that positive and negative numbers represent opposite quantities.",
}


def _graded_artifact(topic_overrides: dict) -> dict:
    return {
        "subject_id": "test-subject",
        "display_name": "Test Subject",
        "content_version": "1.0.0",
        "grade_bands": [6],
        "topics": [{**_GRADED_TOPIC, **topic_overrides}],
    }


def test_no_standards_field_validates_cleanly():
    artifact = validate_content_artifact(_graded_artifact({}))

    assert artifact.topics[0].standards == ()


def test_valid_standards_entry_validates_and_normalizes():
    artifact = validate_content_artifact(_graded_artifact({"standards": [_STANDARD]}))

    assert artifact.topics[0].standards == (_STANDARD,)


def test_standards_not_a_list_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="must be a list"):
        validate_content_artifact(_graded_artifact({"standards": {"not": "a list"}}))


def test_standards_entry_missing_framework_fails_validation():
    bad = {k: v for k, v in _STANDARD.items() if k != "framework"}
    with pytest.raises(ContentArtifactValidationError, match="framework"):
        validate_content_artifact(_graded_artifact({"standards": [bad]}))


def test_standards_entry_missing_code_fails_validation():
    bad = {k: v for k, v in _STANDARD.items() if k != "code"}
    with pytest.raises(ContentArtifactValidationError, match="code"):
        validate_content_artifact(_graded_artifact({"standards": [bad]}))


def test_standards_entry_missing_title_fails_validation():
    bad = {k: v for k, v in _STANDARD.items() if k != "title"}
    with pytest.raises(ContentArtifactValidationError, match="title"):
        validate_content_artifact(_graded_artifact({"standards": [bad]}))


def test_standards_entry_on_ungraded_topic_fails_validation():
    """FR-003: a standards tag may only be declared on a graded topic."""
    artifact = {
        "subject_id": "test-subject",
        "display_name": "Test Subject",
        "content_version": "1.0.0",
        "topics": [
            {
                "topic_id": "topic-1",
                "display_name": "Topic One",
                "skill_definition": {"summary": "An ungraded topic."},
                "standards": [_STANDARD],
            }
        ],
    }

    with pytest.raises(ContentArtifactValidationError, match="grade"):
        validate_content_artifact(artifact)


def test_same_code_different_topics_matching_title_succeeds():
    """research.md Decision 2: a standard spanning several topics is the
    normal, expected shape, not an anomaly -- as long as the title
    matches exactly across every occurrence (FR-012)."""
    artifact = {
        "subject_id": "test-subject",
        "display_name": "Test Subject",
        "content_version": "1.0.0",
        "grade_bands": [6],
        "topics": [
            {**_GRADED_TOPIC, "standards": [_STANDARD]},
            {
                "topic_id": "topic-2",
                "display_name": "Topic Two",
                "grade": 6,
                "skill_definition": {"summary": "A second topic."},
                "standards": [_STANDARD],
            },
        ],
    }

    validated = validate_content_artifact(artifact)

    assert validated.topics[0].standards == (_STANDARD,)
    assert validated.topics[1].standards == (_STANDARD,)


def test_same_code_different_topics_mismatched_title_fails_validation():
    """FR-012: two topics sharing a (framework, code) MUST carry the
    identical title -- otherwise `coverage.py` has no defined answer for
    which title to surface."""
    artifact = {
        "subject_id": "test-subject",
        "display_name": "Test Subject",
        "content_version": "1.0.0",
        "grade_bands": [6],
        "topics": [
            {**_GRADED_TOPIC, "standards": [_STANDARD]},
            {
                "topic_id": "topic-2",
                "display_name": "Topic Two",
                "grade": 6,
                "skill_definition": {"summary": "A second topic."},
                "standards": [{**_STANDARD, "title": "A conflicting title."}],
            },
        ],
    }

    with pytest.raises(ContentArtifactValidationError, match="title"):
        validate_content_artifact(artifact)


def test_standards_tags_persist_and_round_trip(db_session):
    """T005: `persist_content_artifact` delete-and-recreates a subject's
    `StandardsTag` rows on every reload, matching `PrerequisiteEdge`."""
    artifact = validate_content_artifact(_graded_artifact({"standards": [_STANDARD]}))

    persist_content_artifact(db_session, artifact)

    rows = db_session.query(StandardsTag).filter_by(subject_id="test-subject").all()
    assert len(rows) == 1
    assert rows[0].topic_id == "topic-1"
    assert rows[0].framework == _STANDARD["framework"]
    assert rows[0].code == _STANDARD["code"]
    assert rows[0].title == _STANDARD["title"]

    # Reloading without the standards entry removes the stale tag row --
    # delete-and-recreate, not an append-only log.
    reloaded = validate_content_artifact(_graded_artifact({}))
    persist_content_artifact(db_session, reloaded)

    assert db_session.query(StandardsTag).filter_by(subject_id="test-subject").count() == 0

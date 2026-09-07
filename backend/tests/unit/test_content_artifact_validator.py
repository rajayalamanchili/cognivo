"""Unit tests: the content artifact's optional `grade_bands` / per-topic
`grade` fields (spec 017 FR-001/FR-009, research.md Decision 1). Pure
validation tests against `validate_content_artifact()` directly -- no
filesystem/DB access.
"""

import pytest

from src.services.content_artifact.validator import (
    ContentArtifactValidationError,
    validate_content_artifact,
)


def _base_topic(topic_id: str = "topic-1", **overrides: object) -> dict:
    return {
        "topic_id": topic_id,
        "display_name": f"Topic {topic_id}",
        "skill_definition": {"summary": "A topic used only to test grade-band validation."},
        **overrides,
    }


def _artifact(*, grade_bands: object = None, topics: list[dict] | None = None) -> dict:
    artifact: dict = {
        "subject_id": "test-subject",
        "display_name": "Test Subject",
        "content_version": "1.0.0",
        "topics": topics if topics is not None else [_base_topic()],
    }
    if grade_bands is not None:
        artifact["grade_bands"] = grade_bands
    return artifact


def test_no_grade_bands_and_no_topic_grades_validates_cleanly():
    artifact = validate_content_artifact(_artifact())

    assert artifact.grade_bands == ()
    assert artifact.topics[0].grade is None


def test_valid_graded_artifact_validates_and_normalizes():
    artifact = validate_content_artifact(
        _artifact(
            grade_bands=[7, 6],
            topics=[_base_topic("topic-1", grade=6), _base_topic("topic-2", grade=7)],
        )
    )

    assert artifact.grade_bands == (6, 7)
    assert {t.topic_id: t.grade for t in artifact.topics} == {"topic-1": 6, "topic-2": 7}


def test_some_topics_graded_some_not_fails_validation():
    """Decision 1: grade-banding is all-or-nothing per subject."""
    with pytest.raises(ContentArtifactValidationError, match="missing 'grade'"):
        validate_content_artifact(
            _artifact(
                grade_bands=[6, 7],
                topics=[_base_topic("topic-1", grade=6), _base_topic("topic-2")],
            )
        )


def test_topic_grade_without_declared_grade_bands_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="all-or-nothing"):
        validate_content_artifact(_artifact(topics=[_base_topic("topic-1", grade=6)]))


def test_topic_grade_not_in_declared_grade_bands_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="not one of"):
        validate_content_artifact(
            _artifact(grade_bands=[6, 7], topics=[_base_topic("topic-1", grade=8)])
        )


def test_grade_bands_out_of_range_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="1-12"):
        validate_content_artifact(
            _artifact(grade_bands=[13], topics=[_base_topic("topic-1", grade=13)])
        )


def test_grade_bands_not_a_list_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="must be a list"):
        validate_content_artifact(_artifact(grade_bands={"not": "a list"}))


def test_duplicate_grade_bands_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="duplicates"):
        validate_content_artifact(
            _artifact(grade_bands=[6, 6], topics=[_base_topic("topic-1", grade=6)])
        )

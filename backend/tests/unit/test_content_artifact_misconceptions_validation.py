"""Unit tests: the content artifact's optional per-topic `misconceptions`
field (spec 013 FR-002, data-model.md). Pure validation tests against
`validate_content_artifact()` directly -- no filesystem/DB access, since
this field (unlike `image_asset`) never touches either.
"""

import pytest

from src.services.content_artifact.validator import (
    ContentArtifactValidationError,
    validate_content_artifact,
)

_BASE_TOPIC = {
    "topic_id": "topic-1",
    "display_name": "Topic One",
    "skill_definition": {"summary": "A topic used only to test misconceptions validation."},
}


def _artifact(topic_overrides: dict) -> dict:
    return {
        "subject_id": "test-subject",
        "display_name": "Test Subject",
        "content_version": "1.0.0",
        "topics": [{**_BASE_TOPIC, **topic_overrides}],
    }


def test_no_misconceptions_field_validates_cleanly():
    artifact = validate_content_artifact(_artifact({}))

    assert artifact.topics[0].misconceptions == ()


def test_valid_misconceptions_list_validates_and_normalizes():
    artifact = validate_content_artifact(
        _artifact(
            {
                "misconceptions": [
                    {
                        "misconception_id": "confuses-x-with-y",
                        "description": "Consistently confuses X with Y.",
                    }
                ]
            }
        )
    )

    assert artifact.topics[0].misconceptions == (
        {"misconception_id": "confuses-x-with-y", "description": "Consistently confuses X with Y."},
    )


def test_misconceptions_not_a_list_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="must be a list"):
        validate_content_artifact(_artifact({"misconceptions": {"not": "a list"}}))


def test_misconception_missing_id_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="misconception_id"):
        validate_content_artifact(
            _artifact({"misconceptions": [{"description": "no id given"}]})
        )


def test_misconception_missing_description_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="description"):
        validate_content_artifact(
            _artifact({"misconceptions": [{"misconception_id": "confuses-x-with-y"}]})
        )


def test_duplicate_misconception_id_fails_validation():
    with pytest.raises(ContentArtifactValidationError, match="duplicate"):
        validate_content_artifact(
            _artifact(
                {
                    "misconceptions": [
                        {"misconception_id": "dup", "description": "first"},
                        {"misconception_id": "dup", "description": "second"},
                    ]
                }
            )
        )

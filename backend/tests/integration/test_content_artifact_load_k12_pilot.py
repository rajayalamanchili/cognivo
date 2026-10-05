"""Integration tests: the Algebra II/Physics pilot content artifacts
load and validate through the exact same gate Algebra I and Biology
already pass (spec 040 User Story 3, FR-002/FR-003, tasks.md T001).

(a) exercises the real files on disk via `load_content_artifact_file`
(pure parse+validate, no DB) -- no filesystem/DB access beyond reading
the YAML itself. (b)/(c) exercise `validate_content_artifact` directly
against small in-memory dicts, mirroring
`test_content_artifact_validator.py`'s existing pattern, rather than
writing scratch YAML files to disk.
"""

from src.services.content_artifact.loader import load_content_artifact_file
from src.services.content_artifact.validator import (
    ContentArtifactValidationError,
    validate_content_artifact,
)

_SUBJECTS = {
    "algebra-2": {"path": "content/algebra-2/subject.yaml", "grade_bands": (9, 10)},
    "physics": {"path": "content/physics/subject.yaml", "grade_bands": (9, 10, 11)},
}


def test_both_new_subjects_load_with_eight_complete_topics():
    for subject_id, expected in _SUBJECTS.items():
        artifact = load_content_artifact_file(expected["path"])

        assert artifact.subject_id == subject_id
        assert len(artifact.topics) == 8
        assert artifact.grade_bands == expected["grade_bands"]

        for topic in artifact.topics:
            assert topic.skill_definition.get("summary"), (subject_id, topic.topic_id)
            assert set(topic.difficulty_calibration) == {"easy", "medium", "hard"}, (
                subject_id,
                topic.topic_id,
            )
            assert topic.standards, (subject_id, topic.topic_id)
            assert topic.career_connection is not None, (subject_id, topic.topic_id)
            assert topic.grade in expected["grade_bands"], (subject_id, topic.topic_id)


def test_both_new_subjects_exercise_free_text_and_multi_step():
    for subject_id, expected in _SUBJECTS.items():
        artifact = load_content_artifact_file(expected["path"])
        all_types = {
            question_type
            for topic in artifact.topics
            for question_type in topic.skill_definition.get("preferred_question_types", [])
        }
        assert "free_text" in all_types, subject_id
        assert "multi_step" in all_types, subject_id


def _base_topic(topic_id: str, **overrides: object) -> dict:
    return {
        "topic_id": topic_id,
        "display_name": topic_id,
        "skill_definition": {"summary": "A topic used only to test k12-pilot rejection cases."},
        **overrides,
    }


def test_missing_required_field_rejected_with_existing_error_class():
    artifact = {
        "subject_id": "algebra-2",
        "display_name": "Algebra II",
        "content_version": "1.0.0",
        "topics": [{"topic_id": "incomplete-topic", "display_name": "Incomplete Topic"}],
    }

    try:
        validate_content_artifact(artifact)
        assert False, "expected ContentArtifactValidationError"
    except ContentArtifactValidationError as exc:
        assert "missing required field" in str(exc)


def test_cross_subject_prerequisite_rejected_as_undefined():
    """research.md Decision 2: prerequisites resolve only within the
    same subject -- a topic can never list a topic from the *other*
    new subject as a prerequisite."""
    artifact = {
        "subject_id": "algebra-2",
        "display_name": "Algebra II",
        "content_version": "1.0.0",
        "topics": [
            _base_topic("quadratic-equations-and-functions", prerequisites=[]),
            # "forces-and-newtons-laws" only exists in physics, not algebra-2.
            _base_topic(
                "radical-expressions-and-equations", prerequisites=["forces-and-newtons-laws"]
            ),
        ],
    }

    try:
        validate_content_artifact(artifact)
        assert False, "expected ContentArtifactValidationError"
    except ContentArtifactValidationError as exc:
        assert "undefined" in str(exc)

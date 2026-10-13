"""Integration tests: the six remaining-catalog content artifacts
(Pre-Algebra, Geometry, Chemistry, Earth Science, Elementary Math,
Elementary Science) load and validate through the exact same gate the
four existing subjects already pass (spec 046 User Story 3,
FR-002/FR-003, tasks.md T001).

(a)/(a1)/(a2) exercise the real files on disk via
`load_content_artifact_file` (pure parse+validate, no DB) -- no
filesystem/DB access beyond reading the YAML itself. (b)/(c)/(d)
exercise `validate_content_artifact` directly against small in-memory
dicts, mirroring `test_content_artifact_load_k12_pilot.py`'s existing
pattern, rather than writing scratch YAML files to disk.
"""

from src.services.content_artifact.loader import load_content_artifact_file
from src.services.content_artifact.validator import (
    ContentArtifactValidationError,
    validate_content_artifact,
)

_SUBJECTS = {
    "pre-algebra": {"path": "content/pre-algebra/subject.yaml", "grade_bands": (6, 7)},
    "geometry": {"path": "content/geometry/subject.yaml", "grade_bands": (9, 10)},
    "chemistry": {"path": "content/chemistry/subject.yaml", "grade_bands": (9, 10)},
    "earth-science": {"path": "content/earth-science/subject.yaml", "grade_bands": (6,)},
    "elementary-math": {
        "path": "content/elementary-math/subject.yaml",
        "grade_bands": (1, 2, 3, 4, 5),
    },
    "elementary-science": {
        "path": "content/elementary-science/subject.yaml",
        "grade_bands": (1, 2, 3, 4, 5),
    },
}

# spec.md Edge Cases/Assumptions: the two elementary subjects are
# deliberately authored with zero free-text-capable topics, making the
# "no free-text-capable topics at all" Edge Case real for this feature.
_ZERO_FREE_TEXT_SUBJECTS = {"elementary-math", "elementary-science"}


def test_all_six_new_subjects_load_with_eight_complete_topics():
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


def test_four_non_elementary_subjects_exercise_free_text_and_multi_step():
    for subject_id, expected in _SUBJECTS.items():
        if subject_id in _ZERO_FREE_TEXT_SUBJECTS:
            continue
        artifact = load_content_artifact_file(expected["path"])
        all_types = {
            question_type
            for topic in artifact.topics
            for question_type in topic.skill_definition.get("preferred_question_types", [])
        }
        assert "free_text" in all_types, subject_id
        assert "multi_step" in all_types, subject_id


def test_elementary_subjects_have_zero_free_text_capable_topics():
    """spec.md Edge Cases: 'a new subject has no free-text-capable
    topics at all' is real for elementary-math/elementary-science, not
    hypothetical -- process-level grading, notation, and the
    misconception classifier must simply have nothing to do for these
    two subjects."""
    for subject_id in _ZERO_FREE_TEXT_SUBJECTS:
        artifact = load_content_artifact_file(_SUBJECTS[subject_id]["path"])
        all_types = {
            question_type
            for topic in artifact.topics
            for question_type in topic.skill_definition.get("preferred_question_types", [])
        }
        assert "free_text" not in all_types, subject_id
        assert "multi_step" not in all_types, subject_id


def _base_topic(topic_id: str, **overrides: object) -> dict:
    return {
        "topic_id": topic_id,
        "display_name": topic_id,
        "skill_definition": {
            "summary": "A topic used only to test stem-catalog-expansion rejection cases."
        },
        **overrides,
    }


def test_missing_required_field_rejected_with_existing_error_class():
    artifact = {
        "subject_id": "geometry",
        "display_name": "Geometry",
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
    same subject -- a topic can never list a topic from a *different*
    new subject as a prerequisite."""
    artifact = {
        "subject_id": "geometry",
        "display_name": "Geometry",
        "content_version": "1.0.0",
        "topics": [
            _base_topic("points-lines-and-planes", prerequisites=[]),
            # "ratios-and-proportional-relationships" only exists in
            # pre-algebra, not geometry.
            _base_topic(
                "angle-relationships",
                prerequisites=["ratios-and-proportional-relationships"],
            ),
        ],
    }

    try:
        validate_content_artifact(artifact)
        assert False, "expected ContentArtifactValidationError"
    except ContentArtifactValidationError as exc:
        assert "undefined" in str(exc)


def test_same_subject_prerequisite_cycle_rejected():
    """spec.md US3 Acceptance Scenario 2: a same-subject prerequisite
    cycle is rejected before any learner can reach it -- the same
    error class every existing subject's cycle-check already
    produces."""
    artifact = {
        "subject_id": "geometry",
        "display_name": "Geometry",
        "content_version": "1.0.0",
        "topics": [
            _base_topic("topic-a", prerequisites=["topic-b"]),
            _base_topic("topic-b", prerequisites=["topic-a"]),
        ],
    }

    try:
        validate_content_artifact(artifact)
        assert False, "expected ContentArtifactValidationError"
    except ContentArtifactValidationError as exc:
        assert "cycle" in str(exc).lower()

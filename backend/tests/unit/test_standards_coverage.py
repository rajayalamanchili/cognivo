"""Unit tests: `compute_standards_coverage` (spec 038 FR-004/FR-006,
data-model.md). Exercises the real DB (`db_session`, skips cleanly
without one, per `tests/conftest.py`) since this is a query function,
not a pure one.
"""

from src.models.mastery_state import MasteryState
from src.models.standards_tag import StandardsTag
from src.services.content_artifact.loader import persist_content_artifact
from src.services.content_artifact.validator import validate_content_artifact
from src.services.standards.coverage import compute_standards_coverage

_STANDARD = {
    "framework": "Common Core Math",
    "code": "CCSS.MATH.CONTENT.6.NS.C.5",
    "title": "Understand that positive and negative numbers represent opposite quantities.",
}


def _load_two_tagged_topics(db_session):
    """A subject with two topics both tagged with the same standard --
    the multi-topic-per-code case Clarifications' all-topics rule
    applies to."""
    artifact = validate_content_artifact(
        {
            "subject_id": "coverage-test-subject",
            "display_name": "Coverage Test Subject",
            "content_version": "1.0.0",
            "grade_bands": [6],
            "topics": [
                {
                    "topic_id": "topic-a",
                    "display_name": "Topic A",
                    "grade": 6,
                    "skill_definition": {"summary": "Topic A."},
                    "standards": [_STANDARD],
                },
                {
                    "topic_id": "topic-b",
                    "display_name": "Topic B",
                    "grade": 6,
                    "skill_definition": {"summary": "Topic B."},
                    "standards": [_STANDARD],
                },
            ],
        }
    )
    persist_content_artifact(db_session, artifact)


def _set_mastery(db_session, *, learner_id, topic_id, p_mastery, mastered_streak=0):
    db_session.add(
        MasteryState(
            learner_id=learner_id,
            subject_id="coverage-test-subject",
            topic_id=topic_id,
            p_mastery=p_mastery,
            consecutive_mastered_observations=mastered_streak,
        )
    )
    db_session.commit()


def test_empty_result_for_subject_with_zero_standards_tags(db_session, demo_learner):
    assert (
        compute_standards_coverage(
            db_session, learner_id=demo_learner.learner_id, subject_id="algebra-1"
        )
        == []
    )


def test_met_only_when_every_tagged_topic_is_mastered(db_session, demo_learner):
    _load_two_tagged_topics(db_session)
    _set_mastery(db_session, learner_id=demo_learner.learner_id, topic_id="topic-a", p_mastery=0.9, mastered_streak=2)
    _set_mastery(db_session, learner_id=demo_learner.learner_id, topic_id="topic-b", p_mastery=0.9, mastered_streak=2)

    [entry] = compute_standards_coverage(
        db_session, learner_id=demo_learner.learner_id, subject_id="coverage-test-subject"
    )

    assert entry.framework == _STANDARD["framework"]
    assert entry.code == _STANDARD["code"]
    assert entry.title == _STANDARD["title"]
    assert set(entry.topic_ids) == {"topic-a", "topic-b"}
    assert entry.status == "met"


def test_in_progress_when_one_of_two_tagged_topics_not_yet_mastered(db_session, demo_learner):
    _load_two_tagged_topics(db_session)
    _set_mastery(db_session, learner_id=demo_learner.learner_id, topic_id="topic-a", p_mastery=0.9, mastered_streak=2)
    _set_mastery(db_session, learner_id=demo_learner.learner_id, topic_id="topic-b", p_mastery=0.5)

    [entry] = compute_standards_coverage(
        db_session, learner_id=demo_learner.learner_id, subject_id="coverage-test-subject"
    )

    assert entry.status == "in_progress"


def test_not_yet_reached_when_no_tagged_topic_has_any_mastery_state(db_session, demo_learner):
    _load_two_tagged_topics(db_session)

    [entry] = compute_standards_coverage(
        db_session, learner_id=demo_learner.learner_id, subject_id="coverage-test-subject"
    )

    assert entry.status == "not_yet_reached"


def test_in_progress_when_only_one_of_two_tagged_topics_has_any_mastery_state(
    db_session, demo_learner
):
    """Not `not_yet_reached` -- the learner HAS touched this standard,
    just not finished it."""
    _load_two_tagged_topics(db_session)
    _set_mastery(db_session, learner_id=demo_learner.learner_id, topic_id="topic-a", p_mastery=0.5)

    [entry] = compute_standards_coverage(
        db_session, learner_id=demo_learner.learner_id, subject_id="coverage-test-subject"
    )

    assert entry.status == "in_progress"

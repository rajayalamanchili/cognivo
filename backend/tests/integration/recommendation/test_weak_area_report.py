"""Integration test: weak-area report matches the expected flagged set,
every flag cites real evidence, ties both surface, not-yet-assessed and
in-progress topics are explicitly reported (SC-001, SC-002, FR-002,
FR-003, FR-003a, spec.md Edge Cases), T009.

Exercises `classify_topics` directly against a real Postgres-backed
content artifact and scripted scenarios -- classification itself must
be fully deterministic given DB state (Constitution Principle I),
independent of any LLM call (FR-011).
"""

from src.services.recommendation.weak_area import classify_topics
from tests.integration.recommendation.scenarios import (
    make_in_progress_topic,
    make_mastered_topic,
    make_weak_topic,
)


def test_weak_area_report_matches_expected_set_with_citations_and_ties(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    # Two topics tied for weakest -- both must surface (Edge Cases).
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="integers-and-operations",
        p_mastery=0.2,
    )
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="variables-and-expressions",
        p_mastery=0.2,
    )
    make_in_progress_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="order-of-operations",
        p_mastery=0.5,
    )
    # Padding the confidently-assessed denominator so this fixture's
    # struggling proportion (2/5 = 40%) stays under FR-005's 60%
    # broad-review threshold -- that behavior gets its own dedicated
    # test (test_broad_review_threshold.py).
    make_mastered_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="solving-one-step-equations",
    )
    make_mastered_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="solving-multi-step-equations",
    )
    # linear-inequalities, graphing-linear-equations,
    # systems-of-linear-equations are left untouched -- not yet assessed.

    report = classify_topics(db_session, learner_id=learner_id, subject_id=subject_id)

    assert report.data_sufficiency == "confident"
    assert report.broad_review_needed is False

    # SC-001: flagged weak areas match the expected set exactly.
    weak_topic_ids = {flag.topic_id for flag in report.weak_areas}
    assert weak_topic_ids == {"integers-and-operations", "variables-and-expressions"}

    # SC-002: every flag cites specific supporting assessment events --
    # never just a topic name and a bare number.
    for flag in report.weak_areas:
        assert flag.evidence, f"{flag.topic_id} has no citations"
        for citation in flag.evidence:
            assert citation.event_id is not None
            assert citation.question_stem
            assert citation.posterior_p_mastery == flag.p_mastery

    assert report.in_progress_topic_ids == ["order-of-operations"]

    assert report.not_yet_assessed_topic_ids == [
        "linear-inequalities",
        "graphing-linear-equations",
        "systems-of-linear-equations",
    ]

    # Mastered topics are intentionally absent from every bucket
    # (spec.md Key Entities / CHK002).
    all_reported = (
        weak_topic_ids
        | set(report.in_progress_topic_ids)
        | set(report.not_yet_assessed_topic_ids)
        | set(report.insufficient_data_topic_ids)
    )
    assert "solving-one-step-equations" not in all_reported
    assert "solving-multi-step-equations" not in all_reported

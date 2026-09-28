"""Unit tests: `MasteryUpdateResult.prior_band` and `refreshed_from_bands`
(spec 025 User Story 4 / FR-011, Foundational T001; `had_been_mastered_
before` gating added per PR #90 review).

`refreshed_from_bands` is a pure function (mirrors `test_mastery_bkt.py`'s
DB-free style, no fixtures) -- "refreshed" is exactly a below-to-above
`MASTERED` crossing on a topic that had reached `mastered` at some
earlier point already, reusing `mastery_band_for`'s own compound
condition rather than a naive `p_mastery` threshold (research.md §5).
`prior_band`/`has_been_mastered` themselves require `apply_mastery_
update`'s real DB read-modify-write, so those tests use the same
`db_session`/`demo_learner`/`algebra_subject` fixtures
`test_mastery_tool.py` already establishes -- each test pulls them in
directly rather than via a module-wide `usefixtures`, so the pure
`refreshed_from_bands` tests above never require a reachable
`DATABASE_URL`.
"""

import pytest

from src.agents.sequencing.mastery_tool import apply_mastery_update, refreshed_from_bands
from src.models.enums import MasteryBand, QuestionType

# --- Pure: refreshed_from_bands ---------------------------------------


@pytest.mark.parametrize(
    "prior_band,posterior_band,expected",
    [
        (MasteryBand.STRUGGLING, MasteryBand.MASTERED, True),
        (MasteryBand.DEVELOPING, MasteryBand.MASTERED, True),
        (MasteryBand.MASTERED, MasteryBand.MASTERED, False),
        (MasteryBand.STRUGGLING, MasteryBand.DEVELOPING, False),
        (MasteryBand.MASTERED, MasteryBand.DEVELOPING, False),
        (MasteryBand.MASTERED, MasteryBand.STRUGGLING, False),
    ],
)
def test_refreshed_from_bands_when_previously_mastered(prior_band, posterior_band, expected):
    assert (
        refreshed_from_bands(prior_band, posterior_band, had_been_mastered_before=True) is expected
    )


def test_refreshed_from_bands_false_when_never_mastered_before():
    """PR #90 review: any crossing into `mastered` -- including a topic's
    completely ordinary, never-decayed first-time progression from
    struggling/developing up to mastered -- satisfies `prior_band !=
    MASTERED and posterior_band == MASTERED`. Without gating on
    `had_been_mastered_before`, that ordinary first-time achievement
    (which happens far more often than genuine decay recovery) would be
    misreported as "refreshed", even though there was nothing to
    recover."""
    assert (
        refreshed_from_bands(
            MasteryBand.DEVELOPING, MasteryBand.MASTERED, had_been_mastered_before=False
        )
        is False
    )
    assert (
        refreshed_from_bands(
            MasteryBand.STRUGGLING, MasteryBand.MASTERED, had_been_mastered_before=False
        )
        is False
    )


# --- DB-backed: MasteryUpdateResult.prior_band --------------------------
# `db_session` pulls in `database_available` transitively (db_session ->
# _schema_engine -> database_available), so these tests skip gracefully
# without a reachable DATABASE_URL, same as the pure tests above run
# unconditionally.

TOPIC_ID = "integers-and-operations"


def test_first_answer_ever_reports_struggling_prior_band(db_session, demo_learner, algebra_subject):
    result = apply_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_id=TOPIC_ID,
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    db_session.commit()
    # No prior MasteryState row existed -- never mastered by construction.
    assert result.prior_band == MasteryBand.STRUGGLING


def test_prior_band_reflects_existing_unmastered_state(db_session, demo_learner, algebra_subject):
    apply_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_id=TOPIC_ID,
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    db_session.commit()

    second = apply_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_id=TOPIC_ID,
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    db_session.commit()
    # One correct answer alone isn't enough to be "mastered" (needs the
    # 2-consecutive-observation confirmation streak too).
    assert second.prior_band != MasteryBand.MASTERED


def test_prior_band_reports_mastered_once_already_confirmed(db_session, demo_learner, algebra_subject):
    for _ in range(3):
        result = apply_mastery_update(
            db_session,
            learner_id=demo_learner.learner_id,
            subject_id="algebra-1",
            topic_id=TOPIC_ID,
            correct=True,
            question_type=QuestionType.MULTIPLE_CHOICE,
        )
        db_session.commit()
    assert result.posterior_band == MasteryBand.MASTERED

    # A subsequent answer's *prior* band now reflects the already-mastered state.
    reanswer = apply_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_id=TOPIC_ID,
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    db_session.commit()
    assert reanswer.prior_band == MasteryBand.MASTERED


def test_had_been_mastered_before_false_until_first_mastered_crossing(
    db_session, demo_learner, algebra_subject
):
    # Ordinary first-time progression: `had_been_mastered_before` stays
    # False right up through -- and including -- the very update that
    # first reaches `mastered` (it reflects state *before* this update).
    for _ in range(2):
        result = apply_mastery_update(
            db_session,
            learner_id=demo_learner.learner_id,
            subject_id="algebra-1",
            topic_id=TOPIC_ID,
            correct=True,
            question_type=QuestionType.MULTIPLE_CHOICE,
        )
        db_session.commit()
        assert result.had_been_mastered_before is False

    crossing = apply_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_id=TOPIC_ID,
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    db_session.commit()
    assert crossing.posterior_band == MasteryBand.MASTERED
    assert crossing.had_been_mastered_before is False

    # Sticky: once mastered, later updates report True even after the
    # topic drops back out of mastered (simulating a wrong answer).
    after = apply_mastery_update(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_id=TOPIC_ID,
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    db_session.commit()
    assert after.had_been_mastered_before is True

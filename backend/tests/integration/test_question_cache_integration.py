"""Integration test: `get_or_generate_question()`'s hit/miss output is
indistinguishable (SC-003), and a `content_version` bump makes a prior
entry unreachable (SC-004) -- spec 015 User Story 1.
"""

import pytest

from src.agents.assessment_gen.agent import GeneratedQuestionDraft
from src.models.enums import DifficultyBand
from src.services.question_cache.cache import get_or_generate_question

pytestmark = pytest.mark.usefixtures("database_available")


def _generate_fn(stem: str):
    async def _fn():
        return GeneratedQuestionDraft(
            question_type="multiple_choice",
            stem=stem,
            options=["a", "b", "c", "d"],
            correct_index=0,
        )

    return _fn


async def test_second_call_is_a_hit_with_identical_content(db_session, algebra_subject):
    first_draft, first_outcome, first_embedding = await get_or_generate_question(
        db_session,
        subject_id="algebra-1",
        topic_id="integers-and-operations",
        difficulty=DifficultyBand.EASY,
        content_version="v1",
        generation_prompt_version="v1",
        generate_fn=_generate_fn("What is -3 + 5?"),
    )
    db_session.commit()
    assert first_outcome.hit is False
    assert first_embedding is not None

    second_draft, second_outcome, second_embedding = await get_or_generate_question(
        db_session,
        subject_id="algebra-1",
        topic_id="integers-and-operations",
        difficulty=DifficultyBand.EASY,
        content_version="v1",
        generation_prompt_version="v1",
        # A different learner's history -- irrelevant to this combination's
        # pool, deliberately empty to confirm the hit is purely key-based.
        generate_fn=_generate_fn("this must never be called"),
    )

    assert second_outcome.hit is True
    # Not exact equality: `stem_embedding` round-trips through a
    # pgvector column (float4), so a value read back from `row.
    # stem_embedding` loses precision relative to the in-memory value
    # computed just before the write -- `pytest.approx` tolerates that,
    # while still proving the hit path returns the row's own stored
    # embedding rather than silently recomputing a fresh one.
    assert second_embedding == pytest.approx(first_embedding, rel=1e-6)
    assert second_draft.stem == first_draft.stem
    assert second_draft.options == first_draft.options
    assert second_draft.correct_index == first_draft.correct_index


async def test_content_version_bump_invalidates_the_prior_entry(db_session, algebra_subject):
    _, first_outcome, _ = await get_or_generate_question(
        db_session,
        subject_id="algebra-1",
        topic_id="variables-and-expressions",
        difficulty=DifficultyBand.EASY,
        content_version="v1",
        generation_prompt_version="v1",
        generate_fn=_generate_fn("What does x represent in 2x = 10?"),
    )
    db_session.commit()
    assert first_outcome.hit is False

    draft, outcome, _ = await get_or_generate_question(
        db_session,
        subject_id="algebra-1",
        topic_id="variables-and-expressions",
        difficulty=DifficultyBand.EASY,
        content_version="v2",
        generation_prompt_version="v1",
        generate_fn=_generate_fn("a fresh v2 question"),
    )

    assert outcome.hit is False
    assert draft.stem == "a fresh v2 question"

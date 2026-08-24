"""Unit test: `passage_search.py`'s `pgvector` cosine-similarity
ranking (spec 012 research.md §2/§5), T018.

Requires a reachable `DATABASE_URL` (the `pgvector` extension/index
only exist in real Postgres) -- see tests/conftest.py. Skips otherwise.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.models.content_passage_embedding import EMBEDDING_DIMENSION, ContentPassageEmbedding
from src.models.enums import PassageField
from src.services.retrieval.passage_search import search_passages

pytestmark = pytest.mark.usefixtures("database_available")


def _one_hot(index: int, *, sign: float = 1.0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[index] = sign
    return vector


def _add_passage(db_session, *, subject_id, topic_id, field, text, embedding, content_version):
    passage = ContentPassageEmbedding(
        passage_id=uuid.uuid4(),
        subject_id=subject_id,
        topic_id=topic_id,
        field=field,
        text=text,
        embedding=embedding,
        content_version=content_version,
    )
    db_session.add(passage)
    return passage


def _patch_query_embedding(vector: list[float]):
    fake_response = SimpleNamespace(data=[{"embedding": vector}])
    return patch("litellm.aembedding", new=AsyncMock(return_value=fake_response))


async def test_ranks_nearest_passages_first_and_respects_top_k(db_session, biology_subject):
    close = _add_passage(
        db_session,
        subject_id=biology_subject.subject_id,
        topic_id="photosynthesis",
        field=PassageField.SKILL_SUMMARY,
        text="Closest passage",
        embedding=_one_hot(0),
        content_version=biology_subject.content_version,
    )
    middle = _add_passage(
        db_session,
        subject_id=biology_subject.subject_id,
        topic_id="photosynthesis",
        field=PassageField.DIFFICULTY_EASY,
        text="Orthogonal passage",
        embedding=_one_hot(1),
        content_version=biology_subject.content_version,
    )
    farthest = _add_passage(
        db_session,
        subject_id=biology_subject.subject_id,
        topic_id="photosynthesis",
        field=PassageField.DIFFICULTY_HARD,
        text="Opposite passage",
        embedding=_one_hot(0, sign=-1.0),
        content_version=biology_subject.content_version,
    )
    db_session.commit()

    with _patch_query_embedding(_one_hot(0)):
        results = await search_passages(
            db_session,
            subject_id=biology_subject.subject_id,
            query_text="why does light matter?",
            top_k=2,
        )

    assert [r.passage_id for r in results] == [close.passage_id, middle.passage_id]
    assert farthest.passage_id not in [r.passage_id for r in results]


async def test_never_crosses_subject_boundary(db_session, biology_subject, algebra_subject):
    biology_passage = _add_passage(
        db_session,
        subject_id=biology_subject.subject_id,
        topic_id="photosynthesis",
        field=PassageField.SKILL_SUMMARY,
        text="Biology passage",
        embedding=_one_hot(0),
        content_version=biology_subject.content_version,
    )
    _add_passage(
        db_session,
        subject_id=algebra_subject.subject_id,
        topic_id="integers-and-operations",
        field=PassageField.SKILL_SUMMARY,
        text="Algebra passage, identical embedding",
        embedding=_one_hot(0),
        content_version=algebra_subject.content_version,
    )
    db_session.commit()

    with _patch_query_embedding(_one_hot(0)):
        results = await search_passages(
            db_session, subject_id=biology_subject.subject_id, query_text="anything", top_k=5
        )

    assert [r.passage_id for r in results] == [biology_passage.passage_id]

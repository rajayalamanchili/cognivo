"""`pgvector` cosine-similarity retrieval over `content_passage_embeddings`
(spec 012 research.md §2/§5) -- step 4 of `contracts/api.md`'s
`POST /api/tutor/sessions/{id}/messages` server steps.

The backend runs this query itself (it owns Postgres); `tutor-agent/`
never touches the database (research.md §2). A passage is *offered*
here -- whether the Tutor Agent's answer actually *used* it (and is
therefore "grounded") is decided downstream, from the Tutor Agent's own
streamed response (contracts/api.md's internal contract).
"""

import os
from dataclasses import dataclass
from uuid import UUID

import litellm
from sqlalchemy.orm import Session

from src.models.content_passage_embedding import ContentPassageEmbedding
from src.models.enums import PassageField

# Locked per research.md §5: retrieval offers the top few candidates,
# not an exhaustive scan -- the Tutor Agent decides which (if any) it
# actually grounds its answer in.
TOP_K = 5


@dataclass(frozen=True)
class RetrievedPassage:
    passage_id: UUID
    topic_id: str
    field: PassageField
    text: str


async def _embed_query(query_text: str) -> list[float]:
    model_name = os.environ.get("TUTOR_EMBEDDING_MODEL", "voyage/voyage-3")
    response = await litellm.aembedding(model=model_name, input=[query_text])
    return response.data[0]["embedding"]


async def search_passages(
    db: Session, *, subject_id: str, query_text: str, top_k: int = TOP_K
) -> list[RetrievedPassage]:
    """Returns up to `top_k` passages from `subject_id`'s content
    artifact, ranked by cosine similarity to `query_text` (nearest
    first). Never crosses subject boundaries -- a session is scoped to
    one subject (data-model.md's `tutoring_sessions`)."""
    query_embedding = await _embed_query(query_text)
    rows = (
        db.query(ContentPassageEmbedding)
        .filter(ContentPassageEmbedding.subject_id == subject_id)
        .order_by(ContentPassageEmbedding.embedding.cosine_distance(query_embedding))
        .limit(top_k)
        .all()
    )
    return [
        RetrievedPassage(
            passage_id=row.passage_id, topic_id=row.topic_id, field=row.field, text=row.text
        )
        for row in rows
    ]

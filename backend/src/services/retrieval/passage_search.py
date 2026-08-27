"""`pgvector` cosine-similarity retrieval over `content_passage_embeddings`
(spec 012 research.md §2/§5) -- step 4 of `contracts/api.md`'s
`POST /api/tutor/sessions/{id}/messages` server steps.

The backend runs this query itself (it owns Postgres); `tutor-agent/`
never touches the database (research.md §2). A passage is *offered*
here -- whether the Tutor Agent's answer actually *used* it (and is
therefore "grounded") is decided downstream, from the Tutor Agent's own
streamed response (contracts/api.md's internal contract).
"""

import asyncio
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
# Same shape as tutor_agent_client/client.py's and grading_client/
# client.py's own retry constants -- 1 retry (2 total attempts) covers
# a transient network blip or a momentary provider hiccup. Confirmed
# live (T038 grounding investigation, roadmap.md) that this alone
# doesn't paper over a sustained rate limit (a Voyage account with no
# payment method on file caps embedding calls at 3 RPM) -- that needs
# the caller to pace requests, not a longer/more-attempts retry here.
MAX_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.2


@dataclass(frozen=True)
class RetrievedPassage:
    passage_id: UUID
    topic_id: str
    field: PassageField
    text: str


class EmbeddingUnavailableError(Exception):
    """Every attempt to embed `query_text` failed (e.g. a transient
    network error, or a Voyage rate-limit/billing rejection).

    Found live (T038 grounding investigation, roadmap.md): a raw
    embedding-provider exception was previously left completely
    uncaught here, propagating as an unhandled 500 with no
    `TutorExchange` row, no audit-log event, and no trace of any kind
    -- worse than `/speckit-analyze` finding H2's original deadlock,
    since that at least left a row behind to notice. `services/tutor/
    session.py`'s `prepare_message` catches this specific type (after
    `MAX_ATTEMPTS` are exhausted here) and maps it to a clean
    `TutorUnavailableError` (503) plus a persisted failed exchange,
    mirroring how it already handles an A2A-stream-open failure.
    """


async def _embed_query(query_text: str) -> list[float]:
    model_name = os.environ.get("TUTOR_EMBEDDING_MODEL", "voyage/voyage-3")
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = await litellm.aembedding(model=model_name, input=[query_text])
            return response.data[0]["embedding"]
        except Exception as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS)
    raise EmbeddingUnavailableError() from last_error


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

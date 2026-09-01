"""Voyage `voyage-3` embedding of a learner's incorrect free-text answer,
for the misconception classifier (research.md §1).

Reuses the exact model/env-var configuration `content_artifact/loader.py`'s
`generate_passage_embeddings()` and `services/retrieval/passage_search.py`
already establish for the Tutor Agent (`TUTOR_EMBEDDING_MODEL`, default
`voyage/voyage-3`) -- this project's existing pattern is same-model reuse
via `litellm`, not a shared private helper across service modules. Sync,
matching this module's caller (`classify.py`, invoked from a sync cron
route -- `api/routes/cron.py`'s existing `reset-demo-data` route is sync
too).
"""

import os

import litellm

MAX_ATTEMPTS = 2


class EmbeddingUnavailableError(Exception):
    """Every attempt to embed the given text failed (e.g. a transient
    network error, or a Voyage rate-limit/billing rejection) -- mirrors
    `services/retrieval/passage_search.py`'s error of the same name."""


def embed_answer(question_stem: str, answer_text: str) -> list[float]:
    """Embeds one free-text answer for classification, in the context of
    the question that produced it -- the question stem alone doesn't
    reveal the misconception, and the answer alone can be ambiguous
    without knowing what was asked (research.md §1)."""
    model_name = os.environ.get("TUTOR_EMBEDDING_MODEL", "voyage/voyage-3")
    text = f"{question_stem}\n\n{answer_text}"
    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            response = litellm.embedding(model=model_name, input=[text])
            return response.data[0]["embedding"]
        except Exception as exc:  # noqa: BLE001 -- any provider failure retries, then surfaces
            last_error = exc
    raise EmbeddingUnavailableError() from last_error

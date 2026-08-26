"""Shared setup/mocking helpers for Tutor Agent integration tests
(`test_tutor_*.py`).

Mirrors `free_text_helpers.py`'s pattern of patching each external
call's boundary exactly where it's imported into the calling module
(`services/tutor/session.py`, bound by name at import time) -- these
tests exercise the real guardrail/streaming/persistence orchestration
without depending on any live LLM, embedding, or A2A call.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

from src.api.errors import TutorUnavailableError
from src.services.retrieval.passage_search import RetrievedPassage
from src.services.tutor_agent_client.client import (
    TutorAnswerDelta,
    TutorAnswerResult,
    TutorStreamEvent,
    TutorStreamInterruptedError,
)


def patch_moderation(allowed: bool = True):
    return patch("src.services.tutor.session.check_moderation", new=AsyncMock(return_value=allowed))


def patch_search_passages(passages: list[RetrievedPassage]):
    return patch("src.services.tutor.session.search_passages", new=AsyncMock(return_value=passages))


def make_passage(
    *,
    topic_id: str = "photosynthesis",
    field="skill_summary",
    text: str = "Plants use light to make sugar.",
):
    from src.models.enums import PassageField

    return RetrievedPassage(
        passage_id=uuid.uuid4(),
        topic_id=topic_id,
        field=PassageField(field),
        text=text,
    )


def patch_grounded_stream(deltas: list[str], grounded_passage_ids: list[uuid.UUID]):
    """A fake `stream_tutor_answer` that yields `deltas` in order, then a
    final `TutorAnswerResult` grounded in `grounded_passage_ids`."""

    async def _fake_stream(**kwargs) -> AsyncIterator[TutorStreamEvent]:
        for delta in deltas:
            yield TutorAnswerDelta(text=delta)
        yield TutorAnswerResult(
            answer_text="".join(deltas), grounded_passage_ids=list(grounded_passage_ids)
        )

    return patch("src.services.tutor.session.stream_tutor_answer", new=_fake_stream)


def patch_unavailable_stream():
    """A fake `stream_tutor_answer` that fails before any content
    streams back (contracts/api.md's `503 tutor_unavailable`)."""

    async def _fake_stream(**kwargs) -> AsyncIterator[TutorStreamEvent]:
        raise TutorUnavailableError()
        yield  # pragma: no cover -- unreachable, makes this a generator function

    return patch("src.services.tutor.session.stream_tutor_answer", new=_fake_stream)


def patch_unexpected_exception_opening_stream():
    """A fake `stream_tutor_answer` that fails with an exception type
    OTHER than `TutorUnavailableError` before any event is yielded --
    confirmed live against production (a misconfigured Tutor Agent
    endpoint raised something other than `TutorUnavailableError` while
    opening the A2A stream): `prepare_message`'s `anext(stream)` call
    used to only catch `TutorUnavailableError`, reproducing finding
    H2's deadlock for this earlier failure point too."""

    async def _fake_stream(**kwargs) -> AsyncIterator[TutorStreamEvent]:
        raise ValueError("simulated unexpected bug opening the stream")
        yield  # pragma: no cover -- unreachable, makes this a generator function

    return patch("src.services.tutor.session.stream_tutor_answer", new=_fake_stream)


def patch_interrupted_stream(deltas: list[str]):
    """A fake `stream_tutor_answer` that starts streaming successfully,
    then fails mid-response (`/speckit-analyze` finding H2)."""

    async def _fake_stream(**kwargs) -> AsyncIterator[TutorStreamEvent]:
        for delta in deltas:
            yield TutorAnswerDelta(text=delta)
        raise TutorStreamInterruptedError("simulated mid-stream failure")

    return patch("src.services.tutor.session.stream_tutor_answer", new=_fake_stream)


def patch_unexpected_exception_stream(deltas: list[str]):
    """A fake `stream_tutor_answer` that fails with an exception type
    OTHER than `TutorStreamInterruptedError` mid-response -- PR #32
    review finding: only that one exception type used to be caught,
    reproducing finding H2's deadlock for any other failure mode."""

    async def _fake_stream(**kwargs) -> AsyncIterator[TutorStreamEvent]:
        for delta in deltas:
            yield TutorAnswerDelta(text=delta)
        raise ValueError("simulated unexpected bug")

    return patch("src.services.tutor.session.stream_tutor_answer", new=_fake_stream)


def patch_disconnected_stream(deltas: list[str]):
    """A fake `stream_tutor_answer` that fails with
    `asyncio.CancelledError` mid-response -- simulates a real client
    disconnect/Vercel function timeout (contracts/api.md names this
    scenario explicitly). PR #34 review finding: `except Exception`
    alone does not catch this -- `CancelledError` is a `BaseException`
    subclass, not an `Exception` subclass."""

    async def _fake_stream(**kwargs) -> AsyncIterator[TutorStreamEvent]:
        for delta in deltas:
            yield TutorAnswerDelta(text=delta)
        raise asyncio.CancelledError()

    return patch("src.services.tutor.session.stream_tutor_answer", new=_fake_stream)


def parse_sse_events(response_text: str) -> list[dict]:
    """Parses `data: {...}` lines out of a raw SSE response body into a
    list of decoded JSON payloads, in order."""
    import json

    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events

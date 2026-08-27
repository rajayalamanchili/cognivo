"""A2A streaming client for the Tutor Agent (spec 012 FR-002/FR-005/
FR-010, contracts/api.md's internal contract).

The backend is an A2A *client* here -- `tutor-agent/` is a genuinely
separate, independently deployed service (research.md §2), reached at
`TUTOR_AGENT_URL`. Mirrors `services/grading_client/client.py`'s
overall shape (shared-secret header, Vercel bypass header, retry), but
retry only ever covers the *connection* -- once the Tutor Agent has
started streaming, a mid-stream failure is reported as
`TutorStreamInterruptedError` rather than retried (contracts/api.md:
"no learner-facing response for this case beyond the connection simply
ending... the next POST .../messages on that session succeeds
normally" -- retrying after partial text has already reached the
learner would mean silently repeating or duplicating an answer they've
already started reading).
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.client.errors import A2AClientError
from a2a.helpers import get_message_text, new_text_message
from a2a.types import Role, SendMessageRequest, StreamResponse, TaskState

from src.api.errors import TutorUnavailableError

# MUST match `tutor-agent/src/agent.py`'s copy of this literal exactly
# -- duplicated, not imported, since `tutor-agent/` and `backend` are
# genuinely separate deployable units (research.md §2).
GROUNDING_MARKER = "===GROUNDED_PASSAGE_IDS==="

# `maxDuration: 60` on both the backend's tutor endpoint and the
# tutor-agent/ Vercel function (research.md §6) -- a full streamed
# conversational answer plausibly runs longer than Grading's single
# blocking call, so this stays comfortably under that ceiling rather
# than matching grading_client's much tighter 8s budget.
REQUEST_TIMEOUT_SECONDS = 55.0
# 1 retry (2 total attempts) -- same shape as grading_client's
# MAX_ATTEMPTS, but only ever covers the pre-first-byte connection
# phase here (see module docstring).
MAX_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.2

_RETRIABLE_CONNECTION_ERRORS = (A2AClientError, httpx.HTTPError, OSError, StopAsyncIteration)


class TutorStreamInterruptedError(Exception):
    """The Tutor Agent's stream started successfully (at least one
    event was received) but failed or timed out before completing.

    Deliberately not a `DomainError` (`src/api/errors.py`) -- by the
    time this can be raised, the caller has already started streaming
    a response to the learner, so there is no single HTTP status left
    to map this to (contracts/api.md's `503` section, data-model.md's
    `failed_at`). The caller is responsible for setting
    `TutorExchange.failed_at` and ending the response.
    """


@dataclass(frozen=True)
class TutorAnswerDelta:
    """One incremental chunk of the Tutor Agent's visible answer text
    (FR-005), already stripped of `GROUNDING_MARKER` and its trailing
    JSON footer."""

    text: str


@dataclass(frozen=True)
class TutorAnswerResult:
    """Yielded exactly once, after every `TutorAnswerDelta`, once the
    Tutor Agent's stream completes. `grounded_passage_ids` is filtered
    to only IDs that were actually offered in the request -- a
    fabricated or stale ID from the model is dropped, never trusted
    blindly (contracts/api.md: "this is what... TutorExchange.grounded/
    retrieved_passage_ids is filtered down to")."""

    answer_text: str
    grounded_passage_ids: list[UUID]


TutorStreamEvent = TutorAnswerDelta | TutorAnswerResult


def _build_headers(*, exchange_id: UUID, session_id: UUID) -> dict[str, str]:
    # The Tutor Agent's endpoint is a public Vercel URL with none of
    # this backend's guardrails (length cap, rate limit, moderation)
    # running inside it -- it authenticates every request via this
    # shared secret (tutor-agent/src/agent.py's
    # _SharedSecretAuthMiddleware), same reasoning as
    # grading_client/client.py's copy of this.
    shared_secret = os.environ["TUTOR_AGENT_SHARED_SECRET"]
    headers = {"X-Tutor-Agent-Secret": shared_secret}
    # Optional. Vercel's own Deployment Protection sits in front of
    # non-production deployments by default -- a separate, earlier
    # gate than the shared secret above (see backend/.env.example).
    vercel_bypass_secret = os.environ.get("TUTOR_AGENT_VERCEL_BYPASS_SECRET", "")
    if vercel_bypass_secret:
        headers["x-vercel-protection-bypass"] = vercel_bypass_secret
    # Trace-correlation only, no auth role -- tutor-agent/'s Langfuse
    # trace previously had no link back to this TutorExchange row at
    # all (found during the T038 grounding investigation, roadmap.md):
    # the two could only be matched by question text + rough timestamp,
    # which isn't reliable in a tight sequential batch. `tracing.py`'s
    # `traced_exchange()` on the tutor-agent/ side reads these back and
    # attaches them as trace metadata, mirroring how this backend's own
    # `traced_request()` already tags its own spans with learner_id/
    # session_id (Constitution Principle V).
    headers["X-Tutor-Exchange-Id"] = str(exchange_id)
    headers["X-Tutor-Session-Id"] = str(session_id)
    return headers


async def _stream_once(
    request_payload: dict, *, exchange_id: UUID, session_id: UUID
) -> AsyncIterator[StreamResponse]:
    tutor_agent_url = os.environ["TUTOR_AGENT_URL"]
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers=_build_headers(exchange_id=exchange_id, session_id=session_id),
    ) as httpx_client:
        factory = ClientFactory(ClientConfig(streaming=True, httpx_client=httpx_client))
        client = await factory.create_from_url(tutor_agent_url)
        message = new_text_message(json.dumps(request_payload), role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)
        async for response in client.send_message(request):
            yield response


def _response_text_and_state(response: StreamResponse) -> tuple[str, int | None]:
    """The incremental delta text this response carries, plus its task
    state if it's a status update -- `None` state means "not a
    terminal signal, keep streaming".

    Only `status_update`-typed responses carry genuinely new delta text
    for a `to_a2a()`-streamed ADK agent -- the final `artifact_update`
    event `A2aAgentExecutor` publishes duplicates the *last*
    `status_update`'s text verbatim as a protocol-required task result,
    rather than carrying new content (google-adk's
    `TaskResultAggregator` tracks only the most recent status message,
    not an accumulated one). Treating every response type as "append
    this text" would double-count that final chunk.
    """
    if response.HasField("status_update"):
        status = response.status_update.status
        text = get_message_text(status.message) if status.HasField("message") else ""
        return text, status.state
    if response.HasField("task") and response.task.status.state == TaskState.TASK_STATE_FAILED:
        return "", TaskState.TASK_STATE_FAILED
    return "", None


def _parse_grounded_ids(footer_text: str, offered_passage_ids: set[UUID]) -> list[UUID]:
    try:
        raw_ids = json.loads(footer_text.strip())
    except json.JSONDecodeError:
        return []
    if not isinstance(raw_ids, list):
        return []
    grounded_ids: list[UUID] = []
    for raw_id in raw_ids:
        try:
            passage_id = UUID(str(raw_id))
        except ValueError:
            continue
        # Never trust a passage_id the model didn't actually receive --
        # a fabricated/stale ID is dropped, not persisted as grounded.
        if passage_id in offered_passage_ids:
            grounded_ids.append(passage_id)
    return grounded_ids


async def _process_raw_events(
    raw_events: AsyncIterator[StreamResponse], *, offered_passage_ids: set[UUID]
) -> AsyncIterator[TutorStreamEvent]:
    visible_text = ""
    buffer = ""
    footer_buffer: str | None = None
    marker_hold_len = len(GROUNDING_MARKER) - 1

    async for response in raw_events:
        text, state = _response_text_and_state(response)

        if state == TaskState.TASK_STATE_FAILED:
            raise TutorStreamInterruptedError("Tutor Agent reported a failed task state")

        if not text:
            continue

        if footer_buffer is not None:
            footer_buffer += text
            continue

        buffer += text
        if GROUNDING_MARKER in buffer:
            before, _, after = buffer.partition(GROUNDING_MARKER)
            if before:
                visible_text += before
                yield TutorAnswerDelta(text=before)
            buffer = ""
            footer_buffer = after
            continue

        # Flush everything except a trailing window long enough to
        # still contain a marker split across two chunk boundaries.
        safe_len = max(0, len(buffer) - marker_hold_len)
        if safe_len > 0:
            flushable, buffer = buffer[:safe_len], buffer[safe_len:]
            visible_text += flushable
            yield TutorAnswerDelta(text=flushable)

    # Stream ended with `buffer` still non-empty only if the marker was
    # never found at all (the model didn't follow the grounding
    # protocol) -- if it was found, `buffer` was already cleared above
    # and any remaining text lives in `footer_buffer` instead. Flush
    # what's left as visible text and fail safe to "not grounded"
    # rather than guessing.
    if buffer:
        visible_text += buffer
        yield TutorAnswerDelta(text=buffer)

    grounded_ids = (
        _parse_grounded_ids(footer_buffer, offered_passage_ids) if footer_buffer is not None else []
    )
    yield TutorAnswerResult(answer_text=visible_text, grounded_passage_ids=grounded_ids)


async def stream_tutor_answer(
    *,
    question: str,
    subject_id: str,
    retrieved_passages: list[dict],
    delegation_context: list[dict],
    exchange_id: UUID,
    session_id: UUID,
) -> AsyncIterator[TutorStreamEvent]:
    """Streams the Tutor Agent's answer to `question`, grounded in
    `retrieved_passages` and any `delegation_context` (contracts/api.md's
    internal contract's request shape -- the same structured-array shape
    the backend persists, one representation, not two).

    `exchange_id`/`session_id` are not part of the A2A request payload
    (tutor-agent/ never touches the database and has no use for them at
    the agent-instruction level) -- they're sent as headers purely for
    trace correlation (`_build_headers()`'s docstring).

    Yields zero or more `TutorAnswerDelta` (visible answer text, in
    order) followed by exactly one `TutorAnswerResult`. Raises
    `TutorUnavailableError` if every connection attempt fails before
    any event is received; raises `TutorStreamInterruptedError` if the
    stream started but failed/timed out before completing (no more
    retries past that point -- see module docstring).
    """
    request_payload = {
        "question": question,
        "subject_id": subject_id,
        "retrieved_passages": retrieved_passages,
        "delegation_context": delegation_context,
    }
    offered_passage_ids = {UUID(str(passage["passage_id"])) for passage in retrieved_passages}

    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        raw_stream = _stream_once(request_payload, exchange_id=exchange_id, session_id=session_id)
        try:
            first_response = await anext(raw_stream)
        except _RETRIABLE_CONNECTION_ERRORS as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS)
                continue
            raise TutorUnavailableError() from last_error

        async def _chain(
            first: StreamResponse, rest: AsyncIterator[StreamResponse]
        ) -> AsyncIterator[StreamResponse]:
            yield first
            async for response in rest:
                yield response

        async for event in _process_raw_events(
            _chain(first_response, raw_stream), offered_passage_ids=offered_passage_ids
        ):
            yield event
        return

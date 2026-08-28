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


# Found live (T038 grounding investigation, roadmap.md): a strict
# `json.loads(footer_text.strip())` silently returned `[]` on any
# deviation from a bare JSON array (code fence, trailing prose, a
# leading label) -- plausible LLM formatting, not a protocol violation.
# Two narrower fixes (PR #42 review, two rounds) each reproduced the
# same failure via a different trigger: a greedy `\[.*\]` regex swallowed
# trailing prose containing its own bracket (e.g. interval notation like
# `[0, 1]`) into one invalid JSON blob; a bracket-balanced version that
# stopped at the *first* balanced pair then mistook a *leading* bracketed
# aside (e.g. "Sources for the interval [0, 5]: [...]") for the array,
# since `[0, 5]` is itself valid JSON. `_extract_grounded_id_candidates()`
# instead walks every `[` in order and returns the first bracket-balanced
# candidate that actually parses as a list of UUID-shaped strings (or
# `[]`) -- a bracket-containing aside anywhere in the footer, before or
# after the real array, fails that check and is skipped in favor of the
# next `[`.
def _matching_bracket_end(text: str, start: int) -> int | None:
    """Index of the `]` that balances the `[` at `start`, tracking
    (JSON) string literals so a bracket inside a quoted string doesn't
    unbalance the count. `None` if `start` is never balanced."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return i
    return None


def _is_uuid_shaped(item: object) -> bool:
    try:
        UUID(str(item))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _candidate_score(items: list) -> tuple[float, int] | None:
    """Rank a candidate array by how much it looks like a real citation
    list: `(fraction UUID-shaped, count UUID-shaped)`, so a fully-clean
    array always beats a mixed one regardless of length, and among two
    equally-clean arrays the larger one wins. `None` if `items` has no
    UUID-shaped element at all -- not a candidate.

    Requiring only *at least one* UUID-shaped element (rather than
    every element) matters because a real citation array with one
    stray non-UUID element (e.g. a hallucinated "n/a" placeholder)
    must not be rejected outright (PR #43 review, round 6);
    `_parse_grounded_ids` below still filters per-element, dropping
    only the invalid one."""
    if not items:
        return None
    uuid_count = sum(1 for item in items if _is_uuid_shaped(item))
    if uuid_count == 0:
        return None
    return (uuid_count / len(items), uuid_count)


def _extract_grounded_id_candidates(text: str) -> list | None:
    # An empty-list candidate (`[]`) is *vacuously* valid -- but not
    # preferred over a real, non-empty citation array appearing
    # anywhere else in the same footer (PR #42 review, round 5: an
    # incidental empty-bracket aside before the real array, e.g. "No
    # citations here: []. Sources: [...]", would otherwise be accepted
    # immediately and the real array never even reached). Remembered as
    # a fallback and only returned if no non-empty candidate ever turns
    # up.
    fallback: list | None = None
    best: list | None = None
    best_score: tuple[float, int] | None = None
    search_from = 0
    while True:
        start = text.find("[", search_from)
        if start == -1:
            return best if best is not None else fallback
        end = _matching_bracket_end(text, start)
        if end is None:
            # This `[` never balances -- e.g. half-open interval
            # notation like `[0, 5)`, which pairs `[` with `)`, not `]`
            # (PR #42 review, round 4). That doesn't mean *no* array
            # exists in `text`: it only means starting from *this* `[`
            # can't find one, since every subsequent `[`/`]` in the rest
            # of the string gets folded into this same unresolved depth
            # count. Skip past just this one bracket and keep scanning,
            # the same way an unqualifying-but-balanced candidate is
            # skipped below -- giving up here would reproduce the exact
            # "silently persisted as ungrounded" failure this whole
            # function exists to prevent.
            search_from = start + 1
            continue
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            if not parsed:
                if fallback is None:
                    fallback = parsed
            else:
                # Score every non-empty candidate found anywhere in the
                # footer and keep the best one, rather than returning
                # the first that merely qualifies (PR #44 review, round
                # 7): a leading bracketed aside that happens to contain
                # one coincidentally UUID-shaped token (e.g. mixed with
                # ordinary numbers) would otherwise be accepted before
                # the real, purer citation array later in the text is
                # ever reached -- the same silent under-grounding
                # failure this whole function exists to prevent, just
                # via a mixed-leading-array trigger instead of an
                # all-non-UUID one.
                score = _candidate_score(parsed)
                if score is not None and (best_score is None or score > best_score):
                    best_score = score
                    best = parsed
        search_from = start + 1


def _parse_grounded_ids(footer_text: str, offered_passage_ids: set[UUID]) -> list[UUID]:
    raw_ids = _extract_grounded_id_candidates(footer_text)
    if raw_ids is None:
        return []
    grounded_ids: list[UUID] = []
    for raw_id in raw_ids:
        # `_extract_grounded_id_candidates` only confirms *at least one*
        # element is UUID-shaped, not every element (PR #43 review,
        # round 6) -- so a stray non-UUID element (e.g. a hallucinated
        # "n/a") is dropped individually here, the same tolerance the
        # pre-fix code always had, rather than voiding the whole array.
        if not _is_uuid_shaped(raw_id):
            continue
        passage_id = UUID(str(raw_id))
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

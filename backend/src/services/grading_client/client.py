"""A2A client for the Grading Agent (spec 007 FR-003/FR-005/FR-010/FR-014,
contracts/api.md's internal contract section).

The backend is an A2A *client* here -- `grading-agent/` is a genuinely
separate, independently deployed service (research.md §1/§2), reached at
`GRADING_AGENT_URL`. Its response is untrusted output: validated against
the question's own rubric shape before acceptance, never trusted blindly
(same generate-then-validate discipline `assessment_gen/agent.py`'s
`_validate_draft` already applies to LLM output).
"""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.client.errors import A2AClientError
from a2a.helpers import get_stream_response_text, new_text_message
from a2a.types import Role, SendMessageRequest, TaskState

from src.api.errors import GradingUnavailableError

# Locked per research.md §7. Revised 2026-08-21 (/speckit-clarify on spec
# 007): the original values (REQUEST_TIMEOUT_SECONDS=5.0, MAX_ATTEMPTS=3)
# were sized against an assumed 5-second SC-006 budget that covered only
# this call in isolation -- never the length/rate-limit/moderation checks
# or mastery-state write `answer_question` also awaits in the same request
# (questions.py) -- and had no real latency data behind it. CI's
# ground-truth eval gate measured ~3.3s average per grading call
# in-process, with no network hop at all; a production A2A call adds a
# real network round-trip and Vercel cold start on top. A timeout below
# real latency doesn't protect the budget, it guarantees a retry
# (httpx.TimeoutException is caught as retriable below, same as any other
# transient failure) -- too tight a timeout makes `grading_unavailable`
# *more* likely for an answer the agent was grading correctly, not less.
SCORE_THRESHOLD = 0.7
# 1 retry (2 total attempts), not the original 2 retries (3 total) --
# worst-case latency (2 * REQUEST_TIMEOUT_SECONDS + 1 * RETRY_BACKOFF_
# SECONDS) now stays comfortably under vercel.json's maxDuration: 30
# ceiling, while still satisfying FR-010's "automatic retry" requirement.
MAX_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.2
# Grounded in the ~3.3s in-process baseline above, plus margin for a real
# A2A network hop and Vercel cold start.
REQUEST_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class GradingResult:
    correct: bool
    graduated_score: float
    criteria_met: list[str]
    criteria_missed: list[str]
    grading_logic_version: str


class _InvalidGradingResponse(Exception):
    """The Grading Agent replied, but its response failed FR-014's
    rubric-shape validation. Caught by the retry loop below like any
    other transient failure."""


def _validate_and_parse(raw_text: str, rubric_criteria: list[dict]) -> GradingResult:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise _InvalidGradingResponse(f"non-JSON Grading Agent response: {exc}") from exc

    graduated_score = data.get("graduated_score")
    if isinstance(graduated_score, bool) or not isinstance(graduated_score, (int, float)):
        raise _InvalidGradingResponse(
            f"graduated_score missing or not a number: {graduated_score!r}"
        )
    if not (0.0 <= graduated_score <= 1.0):
        raise _InvalidGradingResponse(f"graduated_score out of range [0,1]: {graduated_score!r}")

    criteria_results = data.get("criteria_results")
    if not isinstance(criteria_results, list) or len(criteria_results) != len(rubric_criteria):
        raise _InvalidGradingResponse(
            "criteria_results count doesn't match the rubric's criteria count"
        )

    grading_logic_version = data.get("grading_logic_version")
    if not grading_logic_version or not isinstance(grading_logic_version, str):
        raise _InvalidGradingResponse("missing grading_logic_version")

    criteria_met: list[str] = []
    criteria_missed: list[str] = []
    for expected, actual in zip(rubric_criteria, criteria_results, strict=True):
        if not isinstance(actual, dict) or actual.get("description") != expected["description"]:
            raise _InvalidGradingResponse(
                "criteria_results order/description doesn't match the rubric"
            )
        if actual.get("met"):
            criteria_met.append(expected["description"])
        else:
            criteria_missed.append(expected["description"])

    return GradingResult(
        correct=graduated_score >= SCORE_THRESHOLD,
        graduated_score=float(graduated_score),
        criteria_met=criteria_met,
        criteria_missed=criteria_missed,
        grading_logic_version=grading_logic_version,
    )


def _build_headers(*, question_id: uuid.UUID, learner_id: uuid.UUID) -> dict[str, str]:
    # The Grading Agent's endpoint is a public Vercel URL with none of
    # this backend's guardrails (length cap, rate limit, moderation)
    # running inside it -- it authenticates every request via this
    # shared secret (agent.py's _SharedSecretAuthMiddleware) so it can't
    # be called directly, bypassing those guardrails (PR #18 review).
    shared_secret = os.environ["GRADING_AGENT_SHARED_SECRET"]
    headers = {"X-Grading-Agent-Secret": shared_secret}
    # Vercel's own Deployment Protection (Vercel Authentication/SSO) sits
    # in front of non-production deployments by default -- a separate,
    # earlier gate than _SharedSecretAuthMiddleware above, discovered via
    # a live 401 "Protected deployment" response from Vercel itself, not
    # from grading-agent's own code. Optional (only added if configured)
    # since not every deployment target has this protection enabled --
    # see tech-stack.md's A2A deployment row for the bypass-secret setup.
    vercel_bypass_secret = os.environ.get("GRADING_AGENT_VERCEL_BYPASS_SECRET", "")
    if vercel_bypass_secret:
        headers["x-vercel-protection-bypass"] = vercel_bypass_secret
    # Trace-correlation only, no auth role -- grading-agent/'s Langfuse
    # trace previously had no link back to this backend's own
    # `question_id`/`learner_id` at all (same gap `tutor_agent_client/
    # client.py`'s copy of this docstring describes, found during the
    # T038 grounding investigation, roadmap.md). grading-agent/'s
    # `_TraceCorrelationMiddleware` reads these back and attaches them
    # as trace metadata via `tracing.traced_exchange()`, mirroring
    # `backend/src/observability/tracing.py`'s `traced_request()`.
    headers["X-Grading-Question-Id"] = str(question_id)
    headers["X-Grading-Learner-Id"] = str(learner_id)
    return headers


async def _call_grading_agent_once(
    *,
    question_stem: str,
    rubric_criteria: list[dict],
    learner_answer: str,
    question_id: uuid.UUID,
    learner_id: uuid.UUID,
) -> str:
    grading_agent_url = os.environ["GRADING_AGENT_URL"]
    request_payload = {
        "question_stem": question_stem,
        "rubric": {"criteria": rubric_criteria},
        "learner_answer": learner_answer,
    }
    headers = _build_headers(question_id=question_id, learner_id=learner_id)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, headers=headers) as httpx_client:
        factory = ClientFactory(ClientConfig(streaming=False, httpx_client=httpx_client))
        client = await factory.create_from_url(grading_agent_url)
        message = new_text_message(json.dumps(request_payload), role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        async for response in client.send_message(request):
            if (
                response.HasField("task")
                and response.task.status.state != TaskState.TASK_STATE_COMPLETED
            ):
                raise _InvalidGradingResponse(
                    f"Grading Agent task did not complete: state={response.task.status.state}"
                )
            return get_stream_response_text(response)

    raise _InvalidGradingResponse("Grading Agent returned no response")


async def grade_free_text_answer(
    *,
    question_stem: str,
    rubric_criteria: list[dict],
    learner_answer: str,
    question_id: uuid.UUID,
    learner_id: uuid.UUID,
) -> GradingResult:
    """Calls the Grading Agent over A2A, validates its response against
    `rubric_criteria`'s shape (FR-014), and retries on any transport or
    validation failure (FR-010, research.md §7). Safe to retry
    unconditionally -- the Grading Agent is stateless (research.md §3),
    so a retry can never duplicate a write. Raises
    `GradingUnavailableError` once every attempt is exhausted.

    `question_id`/`learner_id` are not part of the A2A request payload
    (grading-agent/ never touches the database and has no use for them
    at the agent-instruction level) -- they're sent as headers purely
    for trace correlation (`_build_headers()`'s docstring).
    """
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            raw_text = await _call_grading_agent_once(
                question_stem=question_stem,
                rubric_criteria=rubric_criteria,
                question_id=question_id,
                learner_id=learner_id,
                learner_answer=learner_answer,
            )
            return _validate_and_parse(raw_text, rubric_criteria)
        except (_InvalidGradingResponse, A2AClientError, httpx.HTTPError, OSError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS)

    raise GradingUnavailableError() from last_error

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
from dataclasses import dataclass

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.client.errors import A2AClientError
from a2a.helpers import get_stream_response_text, new_text_message
from a2a.types import Role, SendMessageRequest, TaskState

from src.api.errors import GradingUnavailableError

# Locked per research.md §7.
SCORE_THRESHOLD = 0.7
MAX_ATTEMPTS = 3  # 1 initial attempt + 2 retries (FR-010)
RETRY_BACKOFF_SECONDS = 0.2
REQUEST_TIMEOUT_SECONDS = 5.0


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


async def _call_grading_agent_once(
    *, question_stem: str, rubric_criteria: list[dict], learner_answer: str
) -> str:
    grading_agent_url = os.environ["GRADING_AGENT_URL"]
    request_payload = {
        "question_stem": question_stem,
        "rubric": {"criteria": rubric_criteria},
        "learner_answer": learner_answer,
    }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as httpx_client:
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
    *, question_stem: str, rubric_criteria: list[dict], learner_answer: str
) -> GradingResult:
    """Calls the Grading Agent over A2A, validates its response against
    `rubric_criteria`'s shape (FR-014), and retries on any transport or
    validation failure (FR-010, research.md §7). Safe to retry
    unconditionally -- the Grading Agent is stateless (research.md §3),
    so a retry can never duplicate a write. Raises
    `GradingUnavailableError` once every attempt is exhausted."""
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            raw_text = await _call_grading_agent_once(
                question_stem=question_stem,
                rubric_criteria=rubric_criteria,
                learner_answer=learner_answer,
            )
            return _validate_and_parse(raw_text, rubric_criteria)
        except (_InvalidGradingResponse, A2AClientError, httpx.HTTPError, OSError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS)

    raise GradingUnavailableError() from last_error

"""Grading Agent (spec 007 FR-003) -- this project's first remote A2A
service, not a local ADK sub-agent (research.md §1/§2).

Deployed as its own Vercel project (plan.md's Project Structure), with
no database connection of its own (research.md §3) -- it is a pure
function of its A2A request (question rubric + learner answer in,
graduated score + criteria breakdown + Grading Logic Version out). The
calling backend (`backend/src/services/grading_client/`) is solely
responsible for validating this agent's response (FR-014) and
persisting it -- this module never writes to a database.
"""

import os

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field

from src.prompt_defense import build_instruction

APP_NAME = "cognivo-grading-agent"

# Bumped whenever this agent's scoring prompt/logic changes (FR-008's
# ground-truth eval gate protects any such change before it ships).
# A code constant, not a database row (research.md §8) -- git history is
# the audit trail for when/why this changed.
GRADING_LOGIC_VERSION = "v1"


class CriterionResult(BaseModel):
    """One rubric criterion's grading outcome (contracts/api.md)."""

    description: str
    met: bool


class GradingResult(BaseModel):
    """The Grading Agent's structured A2A response shape (contracts/api.md).

    The caller (`services/grading_client/client.py`) validates this
    against the question's own rubric -- same criteria count/order,
    score in range -- before ever accepting it (FR-014); this schema
    only guarantees the *shape* is well-formed, not that the *content*
    is trustworthy.
    """

    graduated_score: float = Field(ge=0.0, le=1.0)
    criteria_results: list[CriterionResult]
    grading_logic_version: str


def _build_agent(model_name: str) -> LlmAgent:
    return LlmAgent(
        name="grading_agent",
        model=LiteLlm(model=model_name),
        instruction=build_instruction(grading_logic_version=GRADING_LOGIC_VERSION),
        output_schema=GradingResult,
    )


# Constructed once at import time (unlike assessment_gen/agent.py's
# per-call `_build_agent`, this agent's instruction is fixed and
# request-independent -- see prompt_defense.py) because `to_a2a()` needs
# a module-level ASGI `app` object for Vercel's Python runtime to find
# (research.md §1). Falls back to the same default model
# `ASSESSMENT_GEN_MODEL` uses in `backend/.env.example` so importing
# this module never crashes when the env var isn't set (e.g. during
# lint/test collection); real grading calls should set
# `GRADING_AGENT_MODEL` explicitly.
_MODEL_NAME = os.environ.get("GRADING_AGENT_MODEL", "anthropic/claude-sonnet-4-5")
_agent = _build_agent(_MODEL_NAME)

app = to_a2a(_agent)

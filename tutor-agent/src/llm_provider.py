"""Budget-driven LLM provider switch.

Own copy of `backend/src/services/llm_provider.py` -- this A2A service
has no import path into `backend/` (Constitution Principle VI), so the
tiny lookup table is duplicated here rather than shared, the same
pattern `guardrails.py`'s moderation check already mirrors from the
backend's own moderation module. `LLM_PROVIDER` overrides this
service's per-call-site defaults (`TUTOR_AGENT_MODEL`,
`MODERATION_MODEL`) when those specific vars aren't set; a specific
`_MODEL` var always wins. Recognizes `openai` and `gemini`.
"""

import os
from typing import Literal

_CHEAP_MODELS = {
    "anthropic": "anthropic/claude-haiku-4-5",
    "openai": "openai/gpt-5.6-luna",
    "gemini": "gemini/gemini-3.5-flash-lite",
}
_CAPABLE_MODELS = {
    "anthropic": "anthropic/claude-sonnet-4-5",
    "openai": "openai/gpt-5.6-sol",
    "gemini": "gemini/gemini-3.8-flash",
}


def default_model(role: Literal["cheap", "capable"]) -> str:
    """`role` is "cheap" (moderation/classification calls) or "capable"
    (primary generation/tutoring calls) -- an unrecognized role raises
    rather than silently picking the more expensive model. Falls back
    to the Anthropic default for an unrecognized `LLM_PROVIDER` value."""
    if role == "cheap":
        table = _CHEAP_MODELS
    elif role == "capable":
        table = _CAPABLE_MODELS
    else:
        raise ValueError(f"unrecognized role: {role!r} (expected 'cheap' or 'capable')")
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    return table.get(provider, table["anthropic"])

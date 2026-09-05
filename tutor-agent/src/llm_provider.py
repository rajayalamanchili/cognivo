"""Budget-driven LLM provider switch.

Own copy of `backend/src/services/llm_provider.py` -- this A2A service
has no import path into `backend/` (Constitution Principle VI), so the
tiny lookup table is duplicated here rather than shared, the same
pattern `guardrails.py`'s moderation check already mirrors from the
backend's own moderation module. `LLM_PROVIDER` overrides this
service's per-call-site defaults (`TUTOR_AGENT_MODEL`,
`MODERATION_MODEL`) when those specific vars aren't set; a specific
`_MODEL` var always wins.
"""

import os

_CHEAP_MODELS = {
    "anthropic": "anthropic/claude-haiku-4-5",
    "openai": "openai/gpt-5.6-luna",
}
_CAPABLE_MODELS = {
    "anthropic": "anthropic/claude-sonnet-4-5",
    "openai": "openai/gpt-5.6-sol",
}


def default_model(role: str) -> str:
    """`role` is "cheap" (moderation/classification calls) or "capable"
    (primary generation/tutoring calls). Falls back to the Anthropic
    default for an unrecognized `LLM_PROVIDER` value."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    table = _CHEAP_MODELS if role == "cheap" else _CAPABLE_MODELS
    return table.get(provider, table["anthropic"])

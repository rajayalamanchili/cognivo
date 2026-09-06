"""Budget-driven LLM provider switch.

Every LLM call in this codebase already goes through ADK's `LiteLlm`
wrapper with a per-call-site model string read from its own env var
(`MODERATION_MODEL`, `ASSESSMENT_GEN_MODEL`, etc.), defaulting to
Anthropic (tech-stack.md's locked default). `LLM_PROVIDER` is a single
override on top of those per-site defaults -- set it to `openai` or
`gemini` to flip every site that doesn't have its own specific
`_MODEL` var set to that provider's equivalent instead, without
touching each var individually. A specific `_MODEL` env var, when set,
always wins over this default.
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

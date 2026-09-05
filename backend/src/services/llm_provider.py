"""Budget-driven LLM provider switch.

Every LLM call in this codebase already goes through ADK's `LiteLlm`
wrapper with a per-call-site model string read from its own env var
(`MODERATION_MODEL`, `ASSESSMENT_GEN_MODEL`, etc.), defaulting to
Anthropic (tech-stack.md's locked default). `LLM_PROVIDER` is a single
override on top of those per-site defaults -- set it to `openai` to
flip every site that doesn't have its own specific `_MODEL` var set to
an OpenAI equivalent instead, without touching each var individually.
A specific `_MODEL` env var, when set, always wins over this default.
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

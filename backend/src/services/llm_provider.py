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

Which provider is actually *live* in a given deployment is a config
concern, not a code concern: set the `LLM_PROVIDER` env var directly
in that deployment (`backend/.env.example`'s own copy is the template
mirrored into each Vercel project's environment variables) rather than
editing this file's fallback -- e.g. when an Anthropic budget/credit
constraint hits, flip `LLM_PROVIDER=openai` in Vercel and redeploy,
no PR needed.
"""

import os
from typing import Literal

_CHEAP_MODELS = {
    "anthropic": "anthropic/claude-haiku-4-5",
    "openai": "openai/gpt-5.6-luna",
    "gemini": "gemini/gemini-3.5-flash-lite",
}
_CAPABLE_MODELS = {
    "anthropic": "anthropic/claude-sonnet-5",
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


def resolve_model(specific_var: str, role: Literal["cheap", "capable"]) -> str:
    """Resolves one LLM call site's model string, with `LLM_PROVIDER`
    grouped as the single per-deployment lever it's meant to be: when
    `LLM_PROVIDER` is explicitly set, it wins over every call site in
    this deployment, `specific_var` included. A budget-constrained
    provider switch should never require hunting down and editing N
    separate per-call-site `_MODEL` env vars one at a time (2026-09-18
    incident: switching off Anthropic meant `ASSESSMENT_GEN_MODEL`, a
    leftover explicit pin from this project's original Milestone 1
    setup, silently kept calling Anthropic even after `LLM_PROVIDER`
    was set).

    `specific_var` (e.g. `ASSESSMENT_GEN_MODEL`) still wins over the
    provider-table default when `LLM_PROVIDER` itself is left unset --
    the per-call-site pin `default_model()`'s own callers already
    supported, unchanged for anyone relying on it today."""
    if os.environ.get("LLM_PROVIDER"):
        return default_model(role)
    return os.environ.get(specific_var) or default_model(role)

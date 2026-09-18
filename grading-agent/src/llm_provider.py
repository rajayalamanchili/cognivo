"""Budget-driven LLM provider switch.

Own copy of `backend/src/services/llm_provider.py` -- this A2A service
has no import path into `backend/` (Constitution Principle VI), so the
tiny lookup table is duplicated here rather than shared, the same
pattern `guardrails.py`'s moderation check already mirrors from the
backend's own moderation module. `LLM_PROVIDER` is this deployment's
single grouped lever: when set, it overrides every call site here
(`GRADING_AGENT_MODEL`, `MODERATION_MODEL`) via `resolve_model()`
below, even one with its own specific `_MODEL` var already pinned --
`default_model()` alone (the un-grouped per-role lookup) is what a
specific `_MODEL` var still wins over. Recognizes `openai` and
`gemini`.

Which provider is actually *live* here is a config concern, not a code
concern: set this A2A service's own `LLM_PROVIDER` env var directly in
its Vercel project (independent of `backend/`'s) rather than editing
this file's fallback -- e.g. when an Anthropic budget/credit
constraint hits, flip `LLM_PROVIDER=openai` there and redeploy, no PR
needed, and no hunting down every individual `_MODEL` var this service
happens to have pinned (2026-09-18 incident: exactly that happened
with `backend/`'s `ASSESSMENT_GEN_MODEL`).
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
    (primary generation calls) -- an unrecognized role raises rather
    than silently picking the more expensive model. Falls back to the
    Anthropic default for an unrecognized `LLM_PROVIDER` value."""
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
    grouped as the single lever for this whole service: when set, it
    wins over every call site here, `specific_var` included. Falls
    back to `specific_var` (a per-call-site pin) over the Anthropic
    default only when `LLM_PROVIDER` itself is left unset."""
    if os.environ.get("LLM_PROVIDER"):
        return default_model(role)
    return os.environ.get(specific_var) or default_model(role)

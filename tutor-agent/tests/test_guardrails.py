"""Unit tests: compensating guardrails against a leaked A2A shared
secret (`src/guardrails.py`) -- mirrors `grading-agent/tests/
test_guardrails.py`'s coverage for the equivalent surface (PR #32
review: this project's newest A2A service shipped with zero unit tests
for the code enforcing Constitution Principle VI's compensating-control
requirement).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.guardrails import (
    _MODERATION_INSTRUCTION,
    MAX_REQUEST_LENGTH,
    before_model_guardrail,
    check_length,
    extract_latest_user_text,
)


def test_moderation_instruction_does_not_block_prompt_injection_attempts():
    # This project's own instruction-level defense
    # (tutor-agent/src/agent.py's "CRITICAL SECURITY RULE") is what's
    # actually responsible for resisting an embedded directive -- this
    # moderation check must not intercept it first, matching the
    # explicit carve-out this instruction text states.
    lowered = _MODERATION_INSTRUCTION.lower()
    assert "ignore your previous instructions" in lowered
    assert "not a moderation concern" in lowered or "never a moderation concern" in lowered


def test_check_length_accepts_text_at_the_limit():
    assert check_length("a" * MAX_REQUEST_LENGTH) is True


def test_check_length_rejects_text_over_the_limit():
    assert check_length("a" * (MAX_REQUEST_LENGTH + 1)) is False


def _content(role: str, text: str | None):
    part = SimpleNamespace(text=text)
    return SimpleNamespace(role=role, parts=[part] if text is not None else [])


def test_extract_latest_user_text_returns_the_most_recent_user_message():
    llm_request = SimpleNamespace(
        contents=[
            _content("user", "first"),
            _content("model", "reply"),
            _content("user", "second"),
        ]
    )
    assert extract_latest_user_text(llm_request) == "second"


def test_extract_latest_user_text_returns_none_when_no_user_content():
    llm_request = SimpleNamespace(contents=[_content("model", "reply")])
    assert extract_latest_user_text(llm_request) is None


@pytest.mark.asyncio
async def test_before_model_guardrail_passes_through_when_allowed():
    llm_request = SimpleNamespace(contents=[_content("user", "a normal tutoring question")])
    with patch("src.guardrails.check_moderation", new=AsyncMock(return_value=True)):
        result = await before_model_guardrail(callback_context=None, llm_request=llm_request)
    assert result is None


@pytest.mark.asyncio
async def test_before_model_guardrail_rejects_oversized_request_without_calling_moderation():
    llm_request = SimpleNamespace(contents=[_content("user", "a" * (MAX_REQUEST_LENGTH + 1))])
    moderation_mock = AsyncMock(return_value=True)
    with patch("src.guardrails.check_moderation", new=moderation_mock):
        result = await before_model_guardrail(callback_context=None, llm_request=llm_request)
    assert result is not None
    assert result.error_code == "request_too_large"
    moderation_mock.assert_not_called()


@pytest.mark.asyncio
async def test_before_model_guardrail_rejects_when_moderation_blocks():
    llm_request = SimpleNamespace(contents=[_content("user", "abusive content")])
    with patch("src.guardrails.check_moderation", new=AsyncMock(return_value=False)):
        result = await before_model_guardrail(callback_context=None, llm_request=llm_request)
    assert result is not None
    assert result.error_code == "moderation_rejected"


@pytest.mark.asyncio
async def test_before_model_guardrail_lets_missing_user_text_through():
    llm_request = SimpleNamespace(contents=[])
    with patch("src.guardrails.check_moderation", new=AsyncMock(return_value=False)):
        result = await before_model_guardrail(callback_context=None, llm_request=llm_request)
    assert result is None

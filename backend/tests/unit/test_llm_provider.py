"""Unit tests: `src/services/llm_provider.py`'s budget-driven provider switch."""

import pytest

from src.services.llm_provider import default_model


def test_defaults_to_anthropic_when_unset(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert default_model("cheap") == "anthropic/claude-haiku-4-5"
    assert default_model("capable") == "anthropic/claude-sonnet-4-5"


def test_openai_provider_switches_both_roles(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    assert default_model("cheap").startswith("openai/")
    assert default_model("capable").startswith("openai/")


def test_gemini_provider_switches_both_roles(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert default_model("cheap").startswith("gemini/")
    assert default_model("capable").startswith("gemini/")


def test_unrecognized_provider_falls_back_to_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    assert default_model("cheap") == "anthropic/claude-haiku-4-5"


def test_unrecognized_role_raises_instead_of_picking_capable():
    with pytest.raises(ValueError, match="unrecognized role"):
        default_model("chep")  # typo -- must not silently resolve to "capable"

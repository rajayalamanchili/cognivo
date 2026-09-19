"""Unit tests: `src/llm_provider.py`'s budget-driven provider switch."""

import pytest

from src.llm_provider import default_model, resolve_model


def test_defaults_to_anthropic_when_unset(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert default_model("cheap") == "anthropic/claude-haiku-4-5"
    assert default_model("capable") == "anthropic/claude-sonnet-5"


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


def test_resolve_model_llm_provider_wins_over_a_pinned_specific_var(monkeypatch):
    # 2026-09-18 incident: a leftover pinned _MODEL var kept calling
    # Anthropic even after LLM_PROVIDER was set to openai -- LLM_PROVIDER
    # must win when explicitly set, full stop.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("GRADING_AGENT_MODEL", "anthropic/claude-sonnet-5")
    assert resolve_model("GRADING_AGENT_MODEL", "capable").startswith("openai/")


def test_resolve_model_specific_var_still_wins_when_llm_provider_is_unset(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("GRADING_AGENT_MODEL", "openai/gpt-5.6-sol")
    assert resolve_model("GRADING_AGENT_MODEL", "capable") == "openai/gpt-5.6-sol"


def test_resolve_model_falls_back_to_provider_default_when_neither_is_set(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GRADING_AGENT_MODEL", raising=False)
    assert resolve_model("GRADING_AGENT_MODEL", "capable") == "anthropic/claude-sonnet-5"

"""Unit tests: the `cite_passages` terminal tool call (`src/agent.py`,
FR-016, research.md §9) that replaced the marker+JSON-in-text grounding
protocol (roadmap.md's Milestone 9 section, PRs #42/#44) -- verifies
the tool ends the agent's turn without a second model call, and that
`_INSTRUCTION` reflects the tool-call protocol rather than the retired
marker.
"""

import os
from types import SimpleNamespace

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-test-only")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-test-only")

from src.agent import _INSTRUCTION, cite_passages  # noqa: E402


def _tool_context():
    return SimpleNamespace(actions=SimpleNamespace(skip_summarization=None))


def test_cite_passages_sets_skip_summarization():
    tool_context = _tool_context()
    cite_passages(["11111111-1111-1111-1111-111111111111"], tool_context)
    assert tool_context.actions.skip_summarization is True


def test_cite_passages_accepts_empty_list():
    tool_context = _tool_context()
    cite_passages([], tool_context)
    assert tool_context.actions.skip_summarization is True


def test_instruction_no_longer_references_grounding_marker():
    assert "GROUNDING_MARKER" not in _INSTRUCTION
    assert "===GROUNDED_PASSAGE_IDS===" not in _INSTRUCTION


def test_instruction_requires_calling_cite_passages():
    assert "cite_passages" in _INSTRUCTION
    assert "passage_id" in _INSTRUCTION

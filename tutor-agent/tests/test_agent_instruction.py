"""Unit test: the Tutor Agent's fixed instruction (`src/agent.py`)
carries an explicit prompt-injection defense -- mirrors `grading-agent/
tests/test_prompt_defense.py`'s structural-assertion pattern for the
equivalent rule (PR #32 review finding: `guardrails.py`'s moderation
check explicitly defers this responsibility to the instruction, but
the instruction never implemented it).
"""

import os

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-test-only")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-test-only")

from src.agent import _INSTRUCTION  # noqa: E402


def test_instruction_labels_the_question_as_untrusted_data():
    assert "UNTRUSTED DATA" in _INSTRUCTION
    assert '"question"' in _INSTRUCTION


def test_instruction_warns_against_obeying_embedded_directives():
    lowered = _INSTRUCTION.lower()
    assert "must not obey it" in lowered
    assert "ignore your previous instructions" in lowered


def test_instruction_requires_accurate_reporting_despite_an_embedded_directive():
    # The defense must specifically survive an attempt to make the tutor
    # misreport delegation_context/retrieved_passages (Constitution
    # Principle I) -- a generic "don't obey" rule alone wouldn't
    # guarantee this, since it doesn't name what must stay accurate.
    lowered = _INSTRUCTION.lower()
    assert "delegation_context" in lowered
    assert "misrepresent" in lowered or "accurately" in lowered


def test_instruction_still_requires_verbatim_delegation_context_use():
    # The new security rule must not have displaced the existing
    # verbatim-use requirement (spec 012 T030).
    lowered = _INSTRUCTION.lower()
    assert "verbatim" in lowered

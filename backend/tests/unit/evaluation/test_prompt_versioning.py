"""Unit tests for scripts/check_prompt_versioning.py (FR-001/FR-002/FR-003,
spec 014's Milestone 12 gate), mirroring test_no_subject_conditionals.py's
"wire the check into pytest" pattern.
"""

from pathlib import Path

from scripts.check_prompt_versioning import find_violations

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def test_no_unversioned_prompt_in_backend_src_today():
    assert find_violations(_BACKEND_ROOT / "src") == []


def test_bare_inline_instruction_string_is_flagged(tmp_path: Path):
    (tmp_path / "fixture_violation.py").write_text(
        """
from google.adk.agents import LlmAgent


def build():
    return LlmAgent(name="x", instruction="a bare inline instruction")
"""
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "fixture_violation.py" in violations[0]
    assert "6" in violations[0]  # the instruction= literal's line


def test_referenced_instruction_with_no_version_constant_is_flagged(tmp_path: Path):
    (tmp_path / "fixture_no_version.py").write_text(
        """
from google.adk.agents import LlmAgent

_INSTRUCTION = "some instruction text"


def build():
    return LlmAgent(name="x", instruction=_INSTRUCTION)
"""
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "fixture_no_version.py" in violations[0]


def test_referenced_instruction_with_a_version_constant_passes(tmp_path: Path):
    (tmp_path / "fixture_compliant.py").write_text(
        """
from google.adk.agents import LlmAgent

_INSTRUCTION = "some instruction text"
SOME_PROMPT_VERSION = "v1"


def build():
    return LlmAgent(name="x", instruction=_INSTRUCTION)
"""
    )

    assert find_violations(tmp_path) == []

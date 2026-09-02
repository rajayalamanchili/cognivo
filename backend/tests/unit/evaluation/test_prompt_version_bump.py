"""Unit tests for scripts/check_prompt_versioning.py's version-bump
enforcement (FR-008), using two in-memory source strings rather than a
real git repo -- pure logic, no subprocess/git dependency.
"""

import subprocess
from pathlib import Path

from scripts.check_prompt_versioning import find_bump_violations_for_tree, find_version_bump_violations

_OLD = '''
_INSTRUCTION = "the original instruction text"
SOME_VERSION = "v1"
'''


def test_content_changed_without_version_bump_is_flagged():
    new_source = _OLD.replace("the original instruction text", "a changed instruction text")

    violations = find_version_bump_violations(_OLD, new_source, filename="fixture.py")

    assert len(violations) == 1
    assert "fixture.py" in violations[0]


def test_content_changed_with_version_bump_passes():
    new_source = _OLD.replace(
        "the original instruction text", "a changed instruction text"
    ).replace('"v1"', '"v2"')

    assert find_version_bump_violations(_OLD, new_source, filename="fixture.py") == []


def test_unrelated_change_elsewhere_in_file_passes():
    new_source = _OLD + "\n_UNRELATED = 'a new constant elsewhere in the file'\n"

    assert find_version_bump_violations(_OLD, new_source, filename="fixture.py") == []


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo_with_grading_agent_shape(repo_dir: Path) -> None:
    """Mirrors grading-agent/src's real layout: prompt content in one
    file, its paired version constant in a different file -- PR #55
    review's exact reported scenario."""
    _git("init", "-q", cwd=repo_dir)
    _git("config", "user.email", "test@example.com", cwd=repo_dir)
    _git("config", "user.name", "Test", cwd=repo_dir)

    (repo_dir / "prompt_defense.py").write_text(
        '_GRADING_INSTRUCTION_TEMPLATE = "the original scoring instruction"\n'
    )
    (repo_dir / "agent.py").write_text(
        'from prompt_defense import _GRADING_INSTRUCTION_TEMPLATE\n'
        'GRADING_LOGIC_VERSION = "v2"\n'
    )
    _git("add", ".", cwd=repo_dir)
    _git("commit", "-q", "-m", "initial", cwd=repo_dir)


def test_cross_file_content_and_version_pairing_passes_when_both_bumped(tmp_path: Path, monkeypatch):
    """PR #55 review: a same-file-only check would permanently fail this
    -- the real Grading Agent shape, where content and version live in
    different files, but both are legitimately updated together.

    `_git_show` runs `git show` in whatever the caller's actual cwd is
    (correct in production: this script is always invoked from within
    the one real repo it's checking) -- so this test must `chdir` into
    its throwaway repo and pass a *relative* `src_dir` (`.`), the same
    shape real CLI usage always has, rather than the absolute `tmp_path`
    itself (which would silently query this actual project's own repo
    instead of the throwaway one -- a real gotcha this test hit while
    being written, not a hypothetical one)."""
    _init_repo_with_grading_agent_shape(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "prompt_defense.py").write_text(
        '_GRADING_INSTRUCTION_TEMPLATE = "a deliberately changed scoring instruction"\n'
    )
    (tmp_path / "agent.py").write_text(
        'from prompt_defense import _GRADING_INSTRUCTION_TEMPLATE\n'
        'GRADING_LOGIC_VERSION = "v3"\n'
    )

    assert find_bump_violations_for_tree(Path("."), "HEAD") == []


def test_cross_file_content_change_with_no_version_bump_anywhere_is_still_flagged(
    tmp_path: Path, monkeypatch
):
    """The suppression only applies when some VERSION constant actually
    changed somewhere in the tree -- a content change with zero version
    activity anywhere must still be caught."""
    _init_repo_with_grading_agent_shape(tmp_path)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "prompt_defense.py").write_text(
        '_GRADING_INSTRUCTION_TEMPLATE = "a deliberately changed scoring instruction"\n'
    )
    # agent.py (and GRADING_LOGIC_VERSION) left untouched.

    violations = find_bump_violations_for_tree(Path("."), "HEAD")

    assert len(violations) == 1
    assert "prompt_defense.py" in violations[0]

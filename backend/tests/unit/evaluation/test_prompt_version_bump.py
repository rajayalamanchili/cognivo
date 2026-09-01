"""Unit tests for scripts/check_prompt_versioning.py's version-bump
enforcement (FR-008), using two in-memory source strings rather than a
real git repo -- pure logic, no subprocess/git dependency.
"""

from scripts.check_prompt_versioning import find_version_bump_violations

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

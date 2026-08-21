#!/usr/bin/env python3
"""Fails if `grading-agent/`'s test suite and `backend/`'s test suite
share fixtures, helpers, or import each other (spec 007 T038, mirrors
spec 002's SC-005 agent-test-independence check,
`check_no_shared_recommendation_sequencing_fixtures.py` precedent).

Constitution Principle VI's justification for making the Grading Agent a
genuine remote A2A service, rather than a local ADK sub-agent, depends on
it being independently testable -- if its test suite silently depended on
`backend/tests/` fixtures (or vice versa), the two "independent" test
suites would actually be one coupled suite, undermining the argument
Principle VI requires.

This checks:
  1. No module under `grading-agent/tests/` imports anything from
     `backend/` (by module name or by a `sys.path` hack pointing at it),
     and vice versa for `backend/tests/` importing from `grading-agent/`.
  2. No test helper/fixture function name is defined in both
     `grading-agent/tests/conftest.py` (if it exists) and
     `backend/tests/conftest.py`.

Deliberately out of scope: `backend/scripts/check_grading_agent_eval.py`
(T040) legitimately imports `grading-agent/src/agent.py` to run the
ground-truth eval -- that's a `backend/scripts/` module, not a
`backend/tests/` one, so it isn't scanned here.

Usage: python scripts/check_grading_agent_test_independence.py
Exit code 0 = no violations found; 1 = violations found.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"
GRADING_AGENT_TESTS_DIR = REPO_ROOT / "grading-agent" / "tests"


def _test_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*.py") if p.name != "__init__.py")


def _imported_module_names(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _defined_function_names(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def _sys_path_hacks_into(py_file: Path, other_project_dirname: str) -> bool:
    """Catches `sys.path.insert`/`.append`/`.extend` calls pointing at the
    other project's directory, which a plain import-name scan can't see
    (the imported module name looks local once the path hack is in
    place). AST-scoped to actual `sys.path` mutation calls -- unlike a
    raw substring search, this doesn't false-positive on a docstring or
    comment that merely mentions the other project by name."""
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in {"insert", "append", "extend"}:
            continue
        target = node.func.value
        if not (isinstance(target, ast.Attribute) and target.attr == "path"):
            continue
        if not (isinstance(target.value, ast.Name) and target.value.id == "sys"):
            continue
        for arg in node.args:
            for string_node in ast.walk(arg):
                if isinstance(string_node, ast.Constant) and isinstance(string_node.value, str):
                    if other_project_dirname in string_node.value:
                        return True
    return False


def find_violations() -> list[str]:
    violations: list[str] = []
    backend_files = _test_files(BACKEND_TESTS_DIR)
    grading_agent_files = _test_files(GRADING_AGENT_TESTS_DIR)

    for py_file in grading_agent_files:
        for module_name in _imported_module_names(py_file):
            if "backend" in module_name.split("."):
                violations.append(
                    f"{py_file.relative_to(REPO_ROOT)} imports {module_name!r} -- "
                    "grading-agent/tests must not import backend/tests fixtures (T038)"
                )
        if _sys_path_hacks_into(py_file, "backend"):
            violations.append(
                f"{py_file.relative_to(REPO_ROOT)} adds 'backend' to sys.path -- "
                "grading-agent/tests must not path-hack into backend (T038)"
            )

    for py_file in backend_files:
        for module_name in _imported_module_names(py_file):
            if "grading_agent" in module_name.split(".") or "grading-agent" in module_name:
                violations.append(
                    f"{py_file.relative_to(REPO_ROOT)} imports {module_name!r} -- "
                    "backend/tests must not import grading-agent/tests fixtures (T038)"
                )
        if _sys_path_hacks_into(py_file, "grading-agent"):
            violations.append(
                f"{py_file.relative_to(REPO_ROOT)} adds 'grading-agent' to sys.path -- "
                "backend/tests must not path-hack into grading-agent (T038)"
            )

    backend_conftest = BACKEND_TESTS_DIR / "conftest.py"
    grading_agent_conftest = GRADING_AGENT_TESTS_DIR / "conftest.py"
    if backend_conftest.exists() and grading_agent_conftest.exists():
        collisions = _defined_function_names(backend_conftest) & _defined_function_names(
            grading_agent_conftest
        )
        if collisions:
            violations.append(
                f"backend/tests/conftest.py and grading-agent/tests/conftest.py both define "
                f"{sorted(collisions)} -- fixture names must not collide (T038)"
            )

    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print("VIOLATION: grading-agent and backend test suites are not independent:")
        for violation in violations:
            print(f"  {violation}")
        return 1

    print("OK: grading-agent/tests and backend/tests share no fixtures/imports")
    return 0


if __name__ == "__main__":
    sys.exit(main())

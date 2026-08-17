#!/usr/bin/env python3
"""Fails if the Recommendation Agent's and Sequencing Agent's test
suites share fixtures or scenario helpers (SC-005 gate).

Constitution Principle IV ("agent boundaries reflect real
responsibility"): FR-009 requires the two agents' test suites be
independently evaluable, with zero shared evaluation fixtures. This
checks two things:
  1. No module under tests/integration/recommendation/ is imported by
     any tests/integration/test_next_topic_*.py file (Sequencing's own
     scripted-scenario tests), or vice versa.
  2. No scripted-scenario helper function name is defined in both
     tests/integration/recommendation/scenarios.py and any
     tests/integration/test_next_topic_*.py file.

Shared test *infrastructure* (tests/conftest.py's db_session,
demo_learner, algebra_subject, biology_subject fixtures) is
deliberately out of scope -- those predate both agents and hold no
scripted-scenario data; see specs/002-recommendation-agent/plan.md's
Constitution Check for the recorded interpretation this script
operationalizes (research.md §6).

Usage: python scripts/check_no_shared_recommendation_sequencing_fixtures.py
Exit code 0 = no violations found; 1 = violations found.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = REPO_ROOT / "backend" / "tests" / "integration"
RECOMMENDATION_DIR = TESTS_DIR / "recommendation"


def _sequencing_test_files() -> list[Path]:
    return sorted(TESTS_DIR.glob("test_next_topic_*.py"))


def _recommendation_test_files() -> list[Path]:
    return sorted(p for p in RECOMMENDATION_DIR.glob("*.py") if p.name != "__init__.py")


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


def find_violations() -> list[str]:
    violations: list[str] = []
    sequencing_files = _sequencing_test_files()
    recommendation_files = _recommendation_test_files()

    for seq_file in sequencing_files:
        for module_name in _imported_module_names(seq_file):
            if "recommendation" in module_name.split("."):
                violations.append(
                    f"{seq_file.relative_to(REPO_ROOT)} imports {module_name!r} -- "
                    "Sequencing tests must not import Recommendation fixtures (FR-009/SC-005)"
                )

    for rec_file in recommendation_files:
        for module_name in _imported_module_names(rec_file):
            if any(part.startswith("test_next_topic") for part in module_name.split(".")):
                violations.append(
                    f"{rec_file.relative_to(REPO_ROOT)} imports {module_name!r} -- "
                    "Recommendation tests must not import Sequencing fixtures (FR-009/SC-005)"
                )

    scenarios_file = RECOMMENDATION_DIR / "scenarios.py"
    if scenarios_file.exists():
        recommendation_helper_names = _defined_function_names(scenarios_file)
        for seq_file in sequencing_files:
            collisions = recommendation_helper_names & _defined_function_names(seq_file)
            if collisions:
                violations.append(
                    f"{seq_file.relative_to(REPO_ROOT)} defines helper name(s) "
                    f"{sorted(collisions)} also defined in "
                    f"{scenarios_file.relative_to(REPO_ROOT)} (FR-009/SC-005)"
                )

    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print("SC-005 VIOLATION: Recommendation and Sequencing test suites share fixtures:")
        for violation in violations:
            print(f"  {violation}")
        return 1

    print("OK: no shared fixtures/imports found between Recommendation and Sequencing tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())

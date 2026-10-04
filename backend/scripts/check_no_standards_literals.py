#!/usr/bin/env python3
"""Fails if engine source hardcodes a specific standards framework/code
(SC-002/FR-002 gate, spec 038).

Constitution Principle III ("one engine, many subjects"): backend/src may
read a `StandardsTag.framework`/`.code` value from the database, but never
branch on a specific framework name or code literal baked into engine
source -- that is the exact anti-pattern this script exists to catch,
the same shape `check_no_subject_conditionals.py` already applies to
subject ids.

Collects every framework/code literal actually declared in
backend/content/*/subject.yaml's topics' `standards:` entries and fails
if any of those literals appear quoted anywhere in backend/src. Adding a
new standards tag automatically extends this check to that literal, with
no changes needed here.

Usage: python scripts/check_no_standards_literals.py
Exit code 0 = no violations found (including the no-tags-yet case); 1 =
violations found.
"""

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = REPO_ROOT / "backend" / "src"
CONTENT_DIR = REPO_ROOT / "backend" / "content"


def _known_standards_literals() -> list[str]:
    literals: set[str] = set()
    for subject_yaml in sorted(CONTENT_DIR.glob("*/subject.yaml")):
        raw = yaml.safe_load(subject_yaml.read_text()) or {}
        for topic in raw.get("topics") or []:
            for tag in topic.get("standards") or []:
                for key in ("framework", "code"):
                    value = tag.get(key)
                    if value:
                        literals.add(value)
    return sorted(literals)


def find_violations(literals: list[str]) -> list[str]:
    pattern = re.compile(r"""(['"])(""" + "|".join(re.escape(s) for s in literals) + r""")\1""")
    violations = []
    for py_file in sorted(SRC_DIR.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        for lineno, line in enumerate(py_file.read_text().splitlines(), start=1):
            if pattern.search(line):
                violations.append(f"{py_file.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    return violations


def main() -> int:
    literals = _known_standards_literals()
    if not literals:
        print("No standards tags found under backend/content/*/subject.yaml -- nothing to check.")
        return 0

    violations = find_violations(literals)
    if violations:
        print(
            "SC-002 VIOLATION: engine source (backend/src) references a "
            "standards framework/code literal:"
        )
        for violation in violations:
            print(f"  {violation}")
        return 1

    print(f"OK: no standards literals found in backend/src ({len(literals)} known literal(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())

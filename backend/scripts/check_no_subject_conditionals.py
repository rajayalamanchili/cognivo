#!/usr/bin/env python3
"""Fails if engine source hardcodes a specific subject's id (SC-004 gate).

Constitution Principle III ("one engine, many subjects"): backend/src may
branch on a `subject_id`/`topic_id` *value read from the database*, but
never on a specific subject's literal id baked into engine source -- that
is the exact anti-pattern this script exists to catch.

Rather than pattern-matching `if subject_id == ...` syntax (which would
miss dict-keyed dispatch, `.startswith(...)`, etc.), this collects every
subject_id actually declared in backend/content/*/subject.yaml and fails
if any of those literals appear quoted anywhere in backend/src. Adding a
new subject's content artifact automatically extends this check to that
subject's id, with no changes needed here.

Usage: python scripts/check_no_subject_conditionals.py
Exit code 0 = no violations found; 1 = violations found or setup error.
"""

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = REPO_ROOT / "backend" / "src"
CONTENT_DIR = REPO_ROOT / "backend" / "content"


def _known_subject_ids() -> list[str]:
    subject_ids = []
    for subject_yaml in sorted(CONTENT_DIR.glob("*/subject.yaml")):
        raw = yaml.safe_load(subject_yaml.read_text())
        subject_id = (raw or {}).get("subject_id")
        if subject_id:
            subject_ids.append(subject_id)
    return subject_ids


def find_violations(subject_ids: list[str]) -> list[str]:
    pattern = re.compile(r"""(['"])(""" + "|".join(re.escape(s) for s in subject_ids) + r""")\1""")
    violations = []
    for py_file in sorted(SRC_DIR.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        for lineno, line in enumerate(py_file.read_text().splitlines(), start=1):
            if pattern.search(line):
                violations.append(f"{py_file.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    return violations


def main() -> int:
    subject_ids = _known_subject_ids()
    if not subject_ids:
        print("No content artifacts found under backend/content/*/subject.yaml.")
        return 1

    violations = find_violations(subject_ids)
    if violations:
        print(
            "SC-004 VIOLATION: engine source (backend/src) references a "
            "subject-specific literal id:"
        )
        for violation in violations:
            print(f"  {violation}")
        return 1

    print(f"OK: no subject-id-keyed conditionals found in backend/src for {subject_ids}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

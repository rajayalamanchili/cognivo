#!/usr/bin/env python3
"""Loads and validates one subject's content artifact into Postgres.

Usage: python scripts/load_content_artifact.py content/algebra-1/subject.yaml

Fails loudly (non-zero exit, no DB writes) if the artifact fails
schema/graph validation (FR-002) -- a subject that fails this check MUST
NOT receive a `validated_at` timestamp and MUST NOT be usable.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_sessionmaker  # noqa: E402
from src.services.content_artifact.loader import load_content_artifact  # noqa: E402
from src.services.content_artifact.validator import (  # noqa: E402
    ContentArtifactValidationError,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_path", help="Path to the subject's YAML content artifact")
    args = parser.parse_args()

    session_local = get_sessionmaker()
    with session_local() as db:
        try:
            subject = load_content_artifact(db, args.artifact_path)
        except ContentArtifactValidationError as exc:
            print(f"validation failed: {exc}", file=sys.stderr)
            return 1

    print(
        f"loaded subject_id={subject.subject_id!r} "
        f"content_version={subject.content_version!r} "
        f"validated_at={subject.validated_at}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

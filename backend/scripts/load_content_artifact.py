#!/usr/bin/env python3
"""Loads and validates one subject's content artifact into Postgres,
then (re)generates its Tutor Agent retrieval passages.

Usage: python scripts/load_content_artifact.py content/algebra-1/subject.yaml

Fails loudly (non-zero exit, no DB writes) if the artifact fails
schema/graph validation (FR-002) -- a subject that fails this check MUST
NOT receive a `validated_at` timestamp and MUST NOT be usable.

The embedding step (spec 012 research.md §5) calls the real
`TUTOR_EMBEDDING_MODEL` (Voyage `voyage-3` by default) over the
network -- requires `VOYAGE_API_KEY` set, unlike the schema/graph load
above which is DB-only.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_sessionmaker  # noqa: E402
from src.services.content_artifact.loader import (  # noqa: E402
    generate_passage_embeddings,
    load_content_artifact_file,
    persist_content_artifact,
)
from src.services.content_artifact.validator import (  # noqa: E402
    ContentArtifactValidationError,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_path", help="Path to the subject's YAML content artifact")
    args = parser.parse_args()

    try:
        artifact = load_content_artifact_file(args.artifact_path)
    except ContentArtifactValidationError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1

    session_local = get_sessionmaker()
    with session_local() as db:
        subject = persist_content_artifact(db, artifact)
        generate_passage_embeddings(db, artifact)

    print(
        f"loaded subject_id={subject.subject_id!r} "
        f"content_version={subject.content_version!r} "
        f"validated_at={subject.validated_at}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

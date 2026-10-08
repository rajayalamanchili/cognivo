#!/usr/bin/env python3
"""Seeds the real, non-demo "default instructor" account (spec 043
FR-019/FR-020, research.md §5) and its per-subject rosters.

Reads `DEFAULT_INSTRUCTOR_EMAIL`/`DEFAULT_INSTRUCTOR_PASSWORD` (required)
and `DEFAULT_INSTRUCTOR_DISPLAY_NAME` (optional, default "Cognivo") from
the environment -- never committed values (Constitution Principle VIII).

Idempotent: re-running against an already-seeded environment reuses the
existing row and never re-hashes/overwrites its password, so an
operator-driven password change via `POST /api/auth/instructor/
change-password` is never silently reverted by a later re-run.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_sessionmaker  # noqa: E402
from src.models.real_instructor_account import RealInstructorAccount  # noqa: E402
from src.models.subject import Subject  # noqa: E402
from src.services.auth.passwords import hash_password  # noqa: E402
from src.services.roster.default_instructor import (  # noqa: E402
    ensure_default_instructor_roster_for_subject,
)

DEFAULT_DISPLAY_NAME = "Cognivo"


def seed_default_instructor() -> RealInstructorAccount:
    # .env.example ships both as empty strings, not unset -- `.get(...,
    # "")` plus an explicit non-empty check catches a copied-but-
    # unfilled-in example the same way an unset var would, rather than
    # silently creating a real account with an empty email/password.
    email = os.environ.get("DEFAULT_INSTRUCTOR_EMAIL", "").strip().lower()
    password = os.environ.get("DEFAULT_INSTRUCTOR_PASSWORD", "")
    if not email or not password:
        raise SystemExit(
            "DEFAULT_INSTRUCTOR_EMAIL and DEFAULT_INSTRUCTOR_PASSWORD must both be set to "
            "non-empty values -- see backend/.env.example."
        )
    if len(password) < 8:
        raise SystemExit("DEFAULT_INSTRUCTOR_PASSWORD must be at least 8 characters.")
    display_name = os.environ.get("DEFAULT_INSTRUCTOR_DISPLAY_NAME") or DEFAULT_DISPLAY_NAME

    session_local = get_sessionmaker()
    with session_local() as db:
        instructor = (
            db.query(RealInstructorAccount).filter(RealInstructorAccount.email == email).first()
        )
        if instructor is None:
            instructor = RealInstructorAccount(
                email=email,
                password_hash=hash_password(password),
                is_demo=False,
                display_name=display_name,
            )
            db.add(instructor)
            db.commit()
            db.refresh(instructor)
        elif instructor.is_demo:
            # DEFAULT_INSTRUCTOR_EMAIL resolves by email only (research.md
            # §5's deliberate choice over a new column) -- refuse rather
            # than silently promoting a flagged-demo row to be the real,
            # operationally-critical default instructor (Principle VIII).
            raise SystemExit(
                f"existing account for {email!r} is flagged is_demo=True -- refusing to adopt "
                "a demo account as the real default instructor."
            )
        else:
            # Resolving by email can't distinguish "our own previously-
            # seeded row" from "someone else's real account that happens
            # to share this email" -- surfaced here so an operator
            # reviewing this script's output notices an unexpected reuse.
            print(f"reusing existing instructor_id={instructor.instructor_id} for {email!r}")

        for subject_id in db.query(Subject.subject_id).all():
            ensure_default_instructor_roster_for_subject(db, subject_id[0])

        return instructor


def main() -> None:
    instructor = seed_default_instructor()
    print(
        f"instructor_id={instructor.instructor_id} email={instructor.email!r} "
        f"display_name={instructor.display_name!r} is_demo={instructor.is_demo}"
    )


if __name__ == "__main__":
    sys.exit(main())

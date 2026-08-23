#!/usr/bin/env python3
"""Seeds the seeded demo instructor profile (spec 010 FR-014).

`is_demo` is set explicitly to `true` here, never inferred (Constitution
Principle VIII) -- mirrors `seed_demo_learner.py`'s pattern exactly,
extended to instructors.

Idempotent: re-running with the same `--display-name` reuses the
existing row instead of creating a duplicate.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_sessionmaker  # noqa: E402
from src.models.demo_instructor_profile import DemoInstructorProfile  # noqa: E402

DEFAULT_DISPLAY_NAME = "Demo Instructor"


def seed_demo_instructor(display_name: str = DEFAULT_DISPLAY_NAME) -> DemoInstructorProfile:
    session_local = get_sessionmaker()
    with session_local() as db:
        existing = (
            db.query(DemoInstructorProfile)
            .filter(DemoInstructorProfile.display_name == display_name)
            .one_or_none()
        )
        if existing is not None:
            return existing

        instructor = DemoInstructorProfile(display_name=display_name, is_demo=True)
        db.add(instructor)
        db.commit()
        db.refresh(instructor)
        return instructor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display-name", default=DEFAULT_DISPLAY_NAME)
    args = parser.parse_args()

    instructor = seed_demo_instructor(args.display_name)
    print(
        f"instructor_id={instructor.instructor_id} display_name={instructor.display_name!r} "
        f"is_demo={instructor.is_demo}"
    )


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Seeds the Milestone-1 demo learner profile.

`is_demo` is set explicitly to `true` here, never inferred (Constitution
Principle VIII) -- this is the only account-creation path in Milestone 1,
and every `learner_id` used by the API resolves to a row this script
created.

Idempotent: re-running with the same `--display-name` reuses the
existing row instead of creating a duplicate.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_sessionmaker  # noqa: E402
from src.models.demo_learner_profile import DemoLearnerProfile  # noqa: E402

DEFAULT_DISPLAY_NAME = "Demo Learner"


def seed_demo_learner(display_name: str = DEFAULT_DISPLAY_NAME) -> DemoLearnerProfile:
    session_local = get_sessionmaker()
    with session_local() as db:
        existing = (
            db.query(DemoLearnerProfile)
            .filter(DemoLearnerProfile.display_name == display_name)
            .one_or_none()
        )
        if existing is not None:
            return existing

        learner = DemoLearnerProfile(display_name=display_name, is_demo=True)
        db.add(learner)
        db.commit()
        db.refresh(learner)
        return learner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display-name", default=DEFAULT_DISPLAY_NAME)
    args = parser.parse_args()

    learner = seed_demo_learner(args.display_name)
    print(
        f"learner_id={learner.learner_id} display_name={learner.display_name!r} "
        f"is_demo={learner.is_demo}"
    )


if __name__ == "__main__":
    sys.exit(main())

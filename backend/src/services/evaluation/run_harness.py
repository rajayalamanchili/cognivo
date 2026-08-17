"""CLI entry point for the Sequencing Evaluation Harness
(quickstart.md step 1; `backend/evaluation/README.md`).

Manual/on-demand only -- never invoked from a request or CI (research.md
§8). Phase 3 (User Story 1) supports a single `--subject`/`--profile`
pair; the full profile x subject matrix (no filters given) is User
Story 2's extension.

    python -m src.services.evaluation.run_harness --subject algebra-1 --profile cold-start --seed 1
"""

import argparse
import datetime
from pathlib import Path

from src.db import get_sessionmaker
from src.models.topic import Topic
from src.services.evaluation.profiles import PROFILES_BY_NAME
from src.services.evaluation.report import ComparisonReport, build_breakdown, run_condition_results

DEFAULT_SEED = 20260816
DEFAULT_POPULATION_SIZE = 30  # research.md §10 -- not CLI-configurable
DEFAULT_MAX_QUESTIONS_PER_TOPIC = 20

REPORT_PATH = Path(__file__).resolve().parents[3] / "evaluation" / "reports" / "latest.json"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Sequencing Evaluation Harness")
    parser.add_argument("--subject", required=True, help="subject_id to run (e.g. algebra-1)")
    parser.add_argument(
        "--profile",
        required=True,
        choices=sorted(PROFILES_BY_NAME),
        help="Synthetic learner profile to run",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--max-questions-per-topic", type=int, default=DEFAULT_MAX_QUESTIONS_PER_TOPIC
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> ComparisonReport:
    args = _parse_args(argv)
    profile = PROFILES_BY_NAME[args.profile]

    session_local = get_sessionmaker()
    db = session_local()
    try:
        topics = (
            db.query(Topic)
            .filter(Topic.subject_id == args.subject)
            .order_by(Topic.order_index)
            .all()
        )
        results = run_condition_results(
            db,
            profile=profile,
            subject_id=args.subject,
            topics=topics,
            population_size=DEFAULT_POPULATION_SIZE,
            max_questions_per_topic=args.max_questions_per_topic,
            seed=args.seed,
        )
        breakdown = build_breakdown(profile.name, args.subject, results)
    finally:
        db.close()

    report = ComparisonReport(
        run_timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
        seed=args.seed,
        profiles=[profile.name],
        subjects=[args.subject],
        population_size_per_profile=DEFAULT_POPULATION_SIZE,
        max_questions_per_topic_budget=args.max_questions_per_topic,
        breakdowns=[breakdown],
        aggregate=dict(breakdown.conditions),
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report.to_json() + "\n")

    print(f"Wrote {REPORT_PATH}")
    for condition, stats in breakdown.conditions.items():
        print(
            f"  {condition}: mean={stats.mean:.1f} median={stats.median:.1f} "
            f"non_converged={stats.non_converged_count}/{stats.n}"
        )

    return report


if __name__ == "__main__":
    main()

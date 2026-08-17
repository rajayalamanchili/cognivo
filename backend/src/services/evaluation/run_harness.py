"""CLI entry point for the Sequencing Evaluation Harness
(quickstart.md steps 1-2; `backend/evaluation/README.md`).

Manual/on-demand only -- never invoked from a request or CI (research.md
§8). With both `--subject` and `--profile` given, runs that single pair
(User Story 1). With neither given, runs the full profile x subject
matrix (User Story 2) -- `ComparisonReport.breakdowns` gets one entry per
(profile, subject) pair, and `aggregate` pools every learner across all
of them.

    python -m src.services.evaluation.run_harness --subject algebra-1 --profile cold-start --seed 1
    python -m src.services.evaluation.run_harness --seed 20260816
"""

import argparse
import datetime
from pathlib import Path

from src.db import get_sessionmaker
from src.models.subject import Subject
from src.models.topic import Topic
from src.services.evaluation.profiles import ALL_PROFILES, PROFILES_BY_NAME
from src.services.evaluation.report import (
    ComparisonReport,
    ConditionRunResult,
    ProfileSubjectBreakdown,
    aggregate_stats,
    build_breakdown,
    run_condition_results,
)

DEFAULT_SEED = 20260816
DEFAULT_POPULATION_SIZE = 30  # research.md §10 -- not CLI-configurable
DEFAULT_MAX_QUESTIONS_PER_TOPIC = 20

REPORT_PATH = Path(__file__).resolve().parents[3] / "evaluation" / "reports" / "latest.json"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Sequencing Evaluation Harness")
    parser.add_argument(
        "--subject",
        default=None,
        help="subject_id to run alone (e.g. algebra-1); omit with --profile for the full matrix",
    )
    parser.add_argument(
        "--profile",
        default=None,
        choices=sorted(PROFILES_BY_NAME),
        help="profile to run alone; omit with --subject for the full matrix",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--max-questions-per-topic", type=int, default=DEFAULT_MAX_QUESTIONS_PER_TOPIC
    )
    args = parser.parse_args(argv)
    if bool(args.subject) != bool(args.profile):
        parser.error("--subject and --profile must be given together, or both omitted")
    return args


def _validated_subject_ids(db) -> list[str]:
    return [
        subject.subject_id
        for subject in db.query(Subject)
        .filter(Subject.validated_at.isnot(None))
        .order_by(Subject.subject_id)
        .all()
    ]


def main(argv: list[str] | None = None, *, report_path: Path = REPORT_PATH) -> ComparisonReport:
    args = _parse_args(argv)

    session_local = get_sessionmaker()
    db = session_local()
    try:
        if args.subject and args.profile:
            subject_ids = [args.subject]
            profiles = [PROFILES_BY_NAME[args.profile]]
        else:
            subject_ids = _validated_subject_ids(db)
            profiles = list(ALL_PROFILES)

        all_results: list[ConditionRunResult] = []
        breakdowns: list[ProfileSubjectBreakdown] = []
        for subject_id in subject_ids:
            topics = (
                db.query(Topic)
                .filter(Topic.subject_id == subject_id)
                .order_by(Topic.order_index)
                .all()
            )
            for profile in profiles:
                results = run_condition_results(
                    db,
                    profile=profile,
                    subject_id=subject_id,
                    topics=topics,
                    population_size=DEFAULT_POPULATION_SIZE,
                    max_questions_per_topic=args.max_questions_per_topic,
                    seed=args.seed,
                )
                all_results.extend(results)
                breakdowns.append(build_breakdown(profile.name, subject_id, results))
    finally:
        db.close()

    report = ComparisonReport(
        run_timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
        seed=args.seed,
        profiles=[profile.name for profile in profiles],
        subjects=subject_ids,
        population_size_per_profile=DEFAULT_POPULATION_SIZE,
        max_questions_per_topic_budget=args.max_questions_per_topic,
        breakdowns=breakdowns,
        aggregate=aggregate_stats(all_results),
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.to_json() + "\n")

    print(f"Wrote {report_path}")
    for breakdown in breakdowns:
        print(f"  [{breakdown.profile} / {breakdown.subject_id}]")
        for condition, stats in breakdown.conditions.items():
            print(
                f"    {condition}: mean={stats.mean:.1f} median={stats.median:.1f} "
                f"non_converged={stats.non_converged_count}/{stats.n}"
            )
    print("  [aggregate]")
    for condition, stats in report.aggregate.items():
        print(
            f"    {condition}: mean={stats.mean:.1f} median={stats.median:.1f} "
            f"non_converged={stats.non_converged_count}/{stats.n}"
        )

    return report


if __name__ == "__main__":
    main()

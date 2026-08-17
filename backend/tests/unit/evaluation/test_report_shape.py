"""Unit tests: aggregation reports correct mean/median/non-convergence,
and the Sequencing Agent condition beats random at small scale (SC-001;
validates T012 -- report.py's aggregation, via scripted `ConditionRunResult`
lists rather than a live harness run)."""

from src.services.evaluation.report import (
    ComparisonReport,
    ConditionRunResult,
    aggregate_stats,
    build_breakdown,
)

PROFILES = ("cold-start", "strong-prior", "uneven", "prerequisite-bottleneck")
SUBJECTS = ("algebra-1", "biology")


def _result(
    condition: str,
    learner_index: int,
    questions_to_mastery: int | None,
    *,
    profile: str = "cold-start",
    subject_id: str = "algebra-1",
) -> ConditionRunResult:
    return ConditionRunResult(
        profile=profile,
        subject_id=subject_id,
        condition=condition,
        learner_index=learner_index,
        questions_to_mastery=questions_to_mastery,
        converged=questions_to_mastery is not None,
    )


def test_aggregation_reports_correct_mean_median_and_non_convergence():
    results = [
        _result("sequencing", 0, 10),
        _result("sequencing", 1, 20),
        _result("sequencing", 2, 30),
        _result("sequencing", 3, None),
    ]
    breakdown = build_breakdown("cold-start", "algebra-1", results)
    stats = breakdown.conditions["sequencing"]

    assert stats.n == 4
    assert stats.non_converged_count == 1
    assert stats.non_converged_rate == 0.25
    assert stats.mean == 20.0  # mean of [10, 20, 30], excluding the non-converger
    assert stats.median == 20.0


def test_sequencing_beats_random_at_small_scale():
    sequencing_results = [_result("sequencing", i, 10 + i) for i in range(5)]
    random_results = [_result("random", i, 40 + i) for i in range(5)]
    breakdown = build_breakdown("cold-start", "algebra-1", sequencing_results + random_results)

    assert breakdown.conditions["sequencing"].mean < breakdown.conditions["random"].mean


def test_breakdown_shape_matches_profile_and_subject():
    breakdown = build_breakdown("cold-start", "algebra-1", [_result("sequencing", 0, 5)])
    assert breakdown.profile == "cold-start"
    assert breakdown.subject_id == "algebra-1"
    assert set(breakdown.conditions.keys()) == {"sequencing"}


def test_comparison_report_round_trips_through_json_with_a_real_breakdown():
    sequencing_results = [_result("sequencing", i, 10 + i) for i in range(3)]
    random_results = [_result("random", i, 40 + i) for i in range(3)]
    breakdown = build_breakdown("cold-start", "algebra-1", sequencing_results + random_results)

    report = ComparisonReport(
        run_timestamp="2026-08-16T00:00:00Z",
        seed=1,
        profiles=["cold-start"],
        subjects=["algebra-1"],
        population_size_per_profile=3,
        max_questions_per_topic_budget=20,
        breakdowns=[breakdown],
        aggregate=dict(breakdown.conditions),
    )
    round_tripped = ComparisonReport.from_json(report.to_json())
    assert round_tripped == report


def test_full_matrix_report_has_eight_breakdowns_and_sequencing_wins_each():
    # SC-001: not only must the pooled aggregate favor sequencing, every
    # individual profile x subject breakdown must too -- a report where
    # only the pooled figure looks good would not actually prove the
    # result isn't cherry-picked.
    breakdowns = []
    all_results: list[ConditionRunResult] = []
    for profile in PROFILES:
        for subject_id in SUBJECTS:
            results = [
                _result("sequencing", i, 10 + i, profile=profile, subject_id=subject_id)
                for i in range(5)
            ] + [
                _result("random", i, 40 + i, profile=profile, subject_id=subject_id)
                for i in range(5)
            ]
            all_results.extend(results)
            breakdowns.append(build_breakdown(profile, subject_id, results))

    assert len(breakdowns) == 8
    assert {(b.profile, b.subject_id) for b in breakdowns} == {
        (profile, subject_id) for profile in PROFILES for subject_id in SUBJECTS
    }
    for breakdown in breakdowns:
        assert breakdown.conditions["sequencing"].mean < breakdown.conditions["random"].mean

    aggregate = aggregate_stats(all_results)
    assert aggregate["sequencing"].mean < aggregate["random"].mean
    assert aggregate["sequencing"].n == 8 * 5
    assert aggregate["random"].n == 8 * 5


def test_sequencing_pooled_aggregate_mean_no_higher_than_fixed_order():
    # SC-002: the Sequencing Agent condition's pooled aggregate mean is
    # no higher than the fixed-order baseline's -- "no higher than"
    # allows equality, not just strict improvement.
    all_results: list[ConditionRunResult] = []
    for profile in PROFILES:
        for subject_id in SUBJECTS:
            all_results += [
                _result("sequencing", i, 10 + i, profile=profile, subject_id=subject_id)
                for i in range(5)
            ]
            all_results += [
                _result("fixed_order", i, 25 + i, profile=profile, subject_id=subject_id)
                for i in range(5)
            ]

    aggregate = aggregate_stats(all_results)
    assert aggregate["sequencing"].mean <= aggregate["fixed_order"].mean

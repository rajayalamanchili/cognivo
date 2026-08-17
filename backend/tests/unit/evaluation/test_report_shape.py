"""Unit tests: aggregation reports correct mean/median/non-convergence,
and the Sequencing Agent condition beats random at small scale (SC-001;
validates T012 -- report.py's aggregation, via scripted `ConditionRunResult`
lists rather than a live harness run)."""

from src.services.evaluation.report import ComparisonReport, ConditionRunResult, build_breakdown


def _result(
    condition: str, learner_index: int, questions_to_mastery: int | None
) -> ConditionRunResult:
    return ConditionRunResult(
        profile="cold-start",
        subject_id="algebra-1",
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

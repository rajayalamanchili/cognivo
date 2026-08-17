"""Contract test: `GET /api/evaluation/report` matches contracts/api.md,
covering both the published and not-yet-published response shapes
(FR-010, FR-011).

No LLM/ADK call and no database access is involved (research.md §8) --
the route reads a committed JSON file, so nothing needs mocking except
the file path itself.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.services.evaluation.report import ComparisonReport, ConditionRunResult, build_breakdown


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


def _sample_report() -> ComparisonReport:
    results = [
        ConditionRunResult(
            profile="cold-start",
            subject_id="algebra-1",
            condition="sequencing",
            learner_index=i,
            questions_to_mastery=10 + i,
            converged=True,
        )
        for i in range(3)
    ] + [
        ConditionRunResult(
            profile="cold-start",
            subject_id="algebra-1",
            condition="random",
            learner_index=i,
            questions_to_mastery=40 + i,
            converged=True,
        )
        for i in range(3)
    ]
    breakdown = build_breakdown("cold-start", "algebra-1", results)
    return ComparisonReport(
        run_timestamp="2026-08-16T00:00:00Z",
        seed=1,
        profiles=["cold-start"],
        subjects=["algebra-1"],
        population_size_per_profile=3,
        max_questions_per_topic_budget=20,
        breakdowns=[breakdown],
        aggregate=dict(breakdown.conditions),
    )


def test_not_yet_published_returns_200_with_published_false(client, tmp_path):
    missing_path = tmp_path / "does-not-exist.json"
    with patch("src.api.routes.evaluation.REPORT_PATH", missing_path):
        response = client.get("/api/evaluation/report")

    assert response.status_code == 200
    assert response.json() == {"published": False}


def test_published_report_returns_full_shape(client, tmp_path):
    report = _sample_report()
    report_path = tmp_path / "latest.json"
    report_path.write_text(report.to_json())

    with patch("src.api.routes.evaluation.REPORT_PATH", report_path):
        response = client.get("/api/evaluation/report")

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["published"] is True
    assert body["run_timestamp"] == report.run_timestamp
    assert body["seed"] == report.seed
    assert body["profiles"] == report.profiles
    assert body["subjects"] == report.subjects
    assert body["population_size_per_profile"] == report.population_size_per_profile
    assert body["max_questions_per_topic_budget"] == report.max_questions_per_topic_budget

    assert len(body["breakdowns"]) == 1
    breakdown = body["breakdowns"][0]
    assert breakdown["profile"] == "cold-start"
    assert breakdown["subject_id"] == "algebra-1"
    for condition in ("sequencing", "random"):
        stats = breakdown["conditions"][condition]
        assert set(stats.keys()) == {
            "mean",
            "median",
            "non_converged_count",
            "non_converged_rate",
            "n",
        }

    for condition in ("sequencing", "random"):
        assert condition in body["aggregate"]

    assert body["aggregate"]["sequencing"]["mean"] < body["aggregate"]["random"]["mean"]


def test_report_path_missing_never_fabricates_figures(client, tmp_path):
    missing_path = tmp_path / "does-not-exist.json"
    with patch("src.api.routes.evaluation.REPORT_PATH", missing_path):
        response = client.get("/api/evaluation/report")

    body = response.json()
    assert body["published"] is False
    assert body.get("breakdowns") is None
    assert body.get("aggregate") is None


def test_all_non_converged_condition_omits_mean_median_not_fabricated_zero(client, tmp_path):
    # PR review finding: the wire response must never carry a fabricated
    # mean=0.0/median=0.0 for a condition where nobody converged -- that
    # would render on the report page as a spurious "reached full
    # mastery in 0.0 questions" result (FR-011).
    results = [
        ConditionRunResult(
            profile="cold-start",
            subject_id="algebra-1",
            condition="random",
            learner_index=i,
            questions_to_mastery=None,
            converged=False,
        )
        for i in range(3)
    ]
    breakdown = build_breakdown("cold-start", "algebra-1", results)
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
    report_path = tmp_path / "latest.json"
    report_path.write_text(report.to_json())

    with patch("src.api.routes.evaluation.REPORT_PATH", report_path):
        response = client.get("/api/evaluation/report")

    body = response.json()
    stats = body["breakdowns"][0]["conditions"]["random"]
    assert "mean" not in stats
    assert "median" not in stats
    assert stats["non_converged_count"] == 3
    assert stats["non_converged_rate"] == 1.0

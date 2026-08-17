"""Evaluation Run report endpoint (contracts/api.md).

Read-only: reads `backend/evaluation/reports/latest.json` -- committed
to the repo and deployed read-only with the function (research.md §8) --
at request time. Never triggers a harness run, never touches the
database. No authentication required (Assumptions: unauthenticated
report page). Not traced (`traced_request()`): no LLM/ADK call is made
here, same untraced precedent as `recommendation.py`/`mastery.py`.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.services.evaluation.report import ComparisonReport
from src.services.evaluation.run_harness import REPORT_PATH

router = APIRouter()


class ConditionStatsOut(BaseModel):
    mean: float
    median: float
    non_converged_count: int
    non_converged_rate: float
    n: int


class ProfileSubjectBreakdownOut(BaseModel):
    profile: str
    subject_id: str
    conditions: dict[str, ConditionStatsOut]


class EvaluationReportResponse(BaseModel):
    published: bool
    run_timestamp: str | None = None
    seed: int | None = None
    profiles: list[str] | None = None
    subjects: list[str] | None = None
    population_size_per_profile: int | None = None
    max_questions_per_topic_budget: int | None = None
    breakdowns: list[ProfileSubjectBreakdownOut] | None = None
    aggregate: dict[str, ConditionStatsOut] | None = None


@router.get(
    "/api/evaluation/report",
    response_model=EvaluationReportResponse,
    response_model_exclude_none=True,
)
def get_evaluation_report() -> EvaluationReportResponse:
    if not REPORT_PATH.exists():
        return EvaluationReportResponse(published=False)

    report = ComparisonReport.from_json(REPORT_PATH.read_text())
    return EvaluationReportResponse(published=True, **report.to_dict())

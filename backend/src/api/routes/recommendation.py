"""Weak-area report endpoint (contracts/api.md, User Stories 1-2).

`GET /api/learners/{learner_id}/recommendations` always returns `200`
-- "insufficient data" and "broad review needed" are reported *in* the
response body (FR-004, FR-005), never as an error status, matching
spec.md's Edge Cases ("must not overreact," "must not crash").

Not wrapped in `traced_request()`: `build_weak_area_report` makes no
LLM/ADK invocation (research.md §1), so there is nothing for
`GoogleADKInstrumentor` to instrument -- matches the existing
`GET /mastery-state` precedent (also untraced). FR-008's audit-log
requirement below is unconditional and unaffected (spec.md FR-008).
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.recommendation.agent import WeakAreaReport, build_weak_area_report
from src.api.errors import NotFoundError
from src.db import get_db
from src.models.enums import AssessmentEventType
from src.models.subject import Subject
from src.services.audit_log.writer import record_event

router = APIRouter()


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


class EvidenceCitationOut(BaseModel):
    event_id: uuid.UUID
    question_id: uuid.UUID
    question_stem: str
    answer_correct: bool
    prior_p_mastery: float | None
    posterior_p_mastery: float
    created_at: str


class NextStepSuggestionOut(BaseModel):
    recommended_topic_id: str
    recommended_display_name: str
    reason: str
    prerequisite_chain: list[str]


class MisconceptionEnrichmentOut(BaseModel):
    misconception_id: str
    description: str
    confidence: float
    evidence: list[EvidenceCitationOut]


class WeakAreaFlagOut(BaseModel):
    topic_id: str
    display_name: str
    p_mastery: float
    evidence: list[EvidenceCitationOut]
    next_step: NextStepSuggestionOut
    misconception: MisconceptionEnrichmentOut | None = None


class RecommendationsResponse(BaseModel):
    subject_id: str
    data_sufficiency: str
    broad_review_needed: bool
    weak_areas: list[WeakAreaFlagOut]
    in_progress_topic_ids: list[str]
    not_yet_assessed_topic_ids: list[str]
    insufficient_data_topic_ids: list[str]


def _evidence_citations_out(citations) -> list[EvidenceCitationOut]:
    return [
        EvidenceCitationOut(
            event_id=citation.event_id,
            question_id=citation.question_id,
            question_stem=citation.question_stem,
            answer_correct=citation.answer_correct,
            prior_p_mastery=citation.prior_p_mastery,
            posterior_p_mastery=citation.posterior_p_mastery,
            created_at=citation.created_at.isoformat(),
        )
        for citation in citations
    ]


def recommendations_response_from_report(report: WeakAreaReport) -> RecommendationsResponse:
    """The single place `WeakAreaReport` -> wire-shape conversion
    happens -- the instructor dashboard (`services/dashboard/
    aggregation.py`, FR-008/SC-001) reuses this exact function so its
    per-learner entries are guaranteed byte-for-byte identical to
    calling this endpoint directly, never a hand-copied second mapping
    that could quietly drift from this one."""
    return RecommendationsResponse(
        subject_id=report.subject_id,
        data_sufficiency=report.data_sufficiency,
        broad_review_needed=report.broad_review_needed,
        weak_areas=[
            WeakAreaFlagOut(
                topic_id=flag.topic_id,
                display_name=flag.display_name,
                p_mastery=flag.p_mastery,
                evidence=_evidence_citations_out(flag.evidence),
                next_step=NextStepSuggestionOut(
                    recommended_topic_id=flag.next_step.recommended_topic_id,
                    recommended_display_name=flag.next_step.recommended_display_name,
                    reason=flag.next_step.reason.value,
                    prerequisite_chain=flag.next_step.prerequisite_chain,
                ),
                misconception=(
                    MisconceptionEnrichmentOut(
                        misconception_id=flag.misconception.misconception_id,
                        description=flag.misconception.description,
                        confidence=flag.misconception.confidence,
                        evidence=_evidence_citations_out(flag.misconception.evidence),
                    )
                    if flag.misconception is not None
                    else None
                ),
            )
            for flag in report.weak_areas
        ],
        in_progress_topic_ids=report.in_progress_topic_ids,
        not_yet_assessed_topic_ids=report.not_yet_assessed_topic_ids,
        insufficient_data_topic_ids=report.insufficient_data_topic_ids,
    )


@router.get("/api/learners/{learner_id}/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    learner_id: uuid.UUID, subject_id: str, db: Session = Depends(get_db)
) -> RecommendationsResponse:
    _get_validated_subject(db, subject_id)

    report = build_weak_area_report(db, learner_id=learner_id, subject_id=subject_id)

    record_event(
        db,
        learner_id=learner_id,
        event_type=AssessmentEventType.RECOMMENDATION_REPORT_GENERATED,
        subject_id=subject_id,
        topic_id=None,
        payload={
            "data_sufficiency": report.data_sufficiency,
            "broad_review_needed": report.broad_review_needed,
            "weak_area_count": len(report.weak_areas),
            "in_progress_count": len(report.in_progress_topic_ids),
            "not_yet_assessed_count": len(report.not_yet_assessed_topic_ids),
            "insufficient_data_count": len(report.insufficient_data_topic_ids),
        },
    )

    for flag in report.weak_areas:
        record_event(
            db,
            learner_id=learner_id,
            event_type=AssessmentEventType.WEAK_AREA_FLAGGED,
            subject_id=subject_id,
            topic_id=flag.topic_id,
            payload={
                "p_mastery": flag.p_mastery,
                "cited_event_ids": [str(citation.event_id) for citation in flag.evidence],
            },
        )
        record_event(
            db,
            learner_id=learner_id,
            event_type=AssessmentEventType.NEXT_STEP_SUGGESTED,
            subject_id=subject_id,
            topic_id=flag.topic_id,
            payload={
                "flagged_topic_id": flag.topic_id,
                "recommended_topic_id": flag.next_step.recommended_topic_id,
                "reason": flag.next_step.reason.value,
                "prerequisite_chain": flag.next_step.prerequisite_chain,
            },
        )

    db.commit()

    return recommendations_response_from_report(report)

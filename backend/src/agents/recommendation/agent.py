"""Recommendation Agent orchestration (FR-001-FR-011).

Composes `services/recommendation/weak_area.py`'s classification (US1)
with `services/recommendation/next_step.py`'s prerequisite-aware
suggestions (US2) into the full `WeakAreaReport` -- mirroring
`agents/sequencing/agent.py`'s role relative to `services/mastery/`.
Per spec.md's Clarifications (FR-011), every decision here is
deterministic; this module makes no `LlmAgent`/`LiteLlm` call
(research.md §1).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.services.recommendation.next_step import NextStepSuggestion, suggest_next_step
from src.services.recommendation.weak_area import (
    EvidenceCitation,
    MisconceptionEnrichment,
    classify_topics,
    get_misconception_enrichment,
)


@dataclass(frozen=True)
class WeakAreaFlag:
    topic_id: str
    display_name: str
    p_mastery: float
    evidence: list[EvidenceCitation]
    next_step: NextStepSuggestion
    misconception: MisconceptionEnrichment | None = None


@dataclass(frozen=True)
class WeakAreaReport:
    subject_id: str
    data_sufficiency: str
    broad_review_needed: bool
    weak_areas: list[WeakAreaFlag]
    in_progress_topic_ids: list[str]
    not_yet_assessed_topic_ids: list[str]
    insufficient_data_topic_ids: list[str]


def build_weak_area_report(
    db: Session, *, learner_id: uuid.UUID, subject_id: str
) -> WeakAreaReport:
    """Classifies every topic (US1), then generates a next-step
    suggestion for each flagged weak area (US2, FR-006) -- exactly one
    suggestion per flag, never left unset."""
    classification = classify_topics(db, learner_id=learner_id, subject_id=subject_id)

    weak_areas = [
        WeakAreaFlag(
            topic_id=flag.topic_id,
            display_name=flag.display_name,
            p_mastery=flag.p_mastery,
            evidence=flag.evidence,
            next_step=suggest_next_step(
                db, learner_id=learner_id, subject_id=subject_id, topic_id=flag.topic_id
            ),
            misconception=get_misconception_enrichment(
                db, learner_id=learner_id, subject_id=subject_id, topic_id=flag.topic_id
            ),
        )
        for flag in classification.weak_areas
    ]

    return WeakAreaReport(
        subject_id=classification.subject_id,
        data_sufficiency=classification.data_sufficiency,
        broad_review_needed=classification.broad_review_needed,
        weak_areas=weak_areas,
        in_progress_topic_ids=classification.in_progress_topic_ids,
        not_yet_assessed_topic_ids=classification.not_yet_assessed_topic_ids,
        insufficient_data_topic_ids=classification.insufficient_data_topic_ids,
    )

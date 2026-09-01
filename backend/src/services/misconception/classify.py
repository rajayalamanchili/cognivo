"""Per-(learner, subject, topic) misconception classification (spec 013
FR-003/FR-004/FR-005/FR-008).

`select_classification` is the pure decision -- given already-computed
per-label mean probabilities and a qualifying-evidence count, applies
the evidence and confidence thresholds -- directly unit-testable with
no DB, model, or embedding call, mirroring `weak_area.py`'s
`classify_topic_status` / `next_step.py`'s `classify_prerequisite_gap`
split. `classify_learner_topic` is the DB-querying, model-loading
orchestration around it.

Never invoked inline from a learner-facing request path (research.md
§3, spec.md FR-006, Constraints) -- only from the scheduled cron route
(`api/routes/cron.py`) or the offline training/eval scripts.
"""

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import joblib
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuestionType
from src.models.generated_question import GeneratedQuestion
from src.models.topic import Topic
from src.services.audit_log.writer import record_event
from src.services.misconception.embed import embed_answer
from src.services.recommendation.weak_area import CONFIDENT_MIN_EVENTS

logger = logging.getLogger(__name__)

# research.md §8: one checked-in, versioned artifact per subject,
# bundled with the deployed function -- read-only at request/job time.
CLASSIFIER_VERSION = "v1"
_MODELS_DIR = Path(__file__).resolve().parents[3] / "misconception_models"

# research.md §5: a separate, explicit constant from the evidence-count
# threshold above -- tunable without a schema change since it's read at
# job-run time, never persisted per-classification.
CONFIDENCE_THRESHOLD = float(os.environ.get("MISCONCEPTION_CONFIDENCE_THRESHOLD", "0.6"))


class ClassifierUnavailableError(Exception):
    """No trained artifact exists yet for this subject (research.md §3:
    this is an expected, not exceptional, state until T019/retraining
    -- callers treat it as "no classification available," not a crash)."""


@dataclass(frozen=True)
class MisconceptionResult:
    misconception_id: str
    confidence: float


def select_classification(
    *,
    qualifying_event_count: int,
    mean_probability_by_id: dict[str, float],
    min_events: int = CONFIDENT_MIN_EVENTS,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> MisconceptionResult | None:
    """Pure decision: `None` below the evidence-count threshold (FR-005)
    or when every candidate label's mean probability is below the
    confidence threshold (FR-006's "or below its confidence threshold"),
    otherwise the highest-mean-probability label."""
    if qualifying_event_count < min_events:
        return None
    if not mean_probability_by_id:
        return None
    best_id, best_confidence = max(mean_probability_by_id.items(), key=lambda kv: kv[1])
    if best_confidence < confidence_threshold:
        return None
    return MisconceptionResult(misconception_id=best_id, confidence=best_confidence)


def _load_classifier(subject_id: str):
    path = _MODELS_DIR / subject_id / CLASSIFIER_VERSION / "classifier.joblib"
    if not path.is_file():
        raise ClassifierUnavailableError(f"no trained classifier for subject '{subject_id}'")
    return joblib.load(path)


def _qualifying_events(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, topic_id: str
) -> list[tuple[AssessmentEvent, GeneratedQuestion]]:
    """Every incorrect free-text `ANSWER_SUBMITTED` event for this
    learner/topic -- the only evidence this classifier ever considers
    (FR-001), ordered oldest-first for deterministic embedding order."""
    rows = (
        db.query(AssessmentEvent, GeneratedQuestion)
        .join(GeneratedQuestion, AssessmentEvent.question_id == GeneratedQuestion.question_id)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.subject_id == subject_id,
            AssessmentEvent.topic_id == topic_id,
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
            GeneratedQuestion.question_type == QuestionType.FREE_TEXT,
        )
        .order_by(AssessmentEvent.created_at)
        .all()
    )
    return [(event, question) for event, question in rows if event.payload.get("correct") is False]


def classify_learner_topic(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, topic_id: str
) -> AssessmentEvent | None:
    """Classifies one learner/topic pair. Returns the written
    `misconception_classified` event, or `None` if no classification
    was made -- no taxonomy authored for this topic, insufficient
    evidence, or every candidate label scored below confidence
    (FR-006's graceful degradation is the only outcome shape here; this
    function never raises for those cases). Does not commit -- mirrors
    `record_event`'s own transaction-boundary convention; the caller
    (the cron route, T020) controls commit per pair.

    Raises `ClassifierUnavailableError` if no trained artifact exists
    for `subject_id` yet -- a real, distinct failure mode from "nothing
    to classify," left for the caller to catch per pair (T027).
    """
    topic = (
        db.query(Topic)
        .filter(Topic.subject_id == subject_id, Topic.topic_id == topic_id)
        .one()
    )
    valid_ids = {
        m["misconception_id"] for m in topic.skill_definition.get("misconceptions", [])
    }
    if not valid_ids:
        return None

    qualifying = _qualifying_events(db, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id)
    if len(qualifying) < CONFIDENT_MIN_EVENTS:
        return None

    model = _load_classifier(subject_id)
    embeddings = [
        embed_answer(question.stem, event.payload["response"]) for event, question in qualifying
    ]
    probabilities = model.predict_proba(embeddings)
    mean_probabilities = probabilities.mean(axis=0)
    mean_probability_by_id = {
        label: float(prob)
        for label, prob in zip(model.classes_, mean_probabilities, strict=True)
        if label in valid_ids
    }

    result = select_classification(
        qualifying_event_count=len(qualifying), mean_probability_by_id=mean_probability_by_id
    )
    if result is None:
        return None

    return record_event(
        db,
        learner_id=learner_id,
        event_type=AssessmentEventType.MISCONCEPTION_CLASSIFIED,
        subject_id=subject_id,
        topic_id=topic_id,
        payload={
            "misconception_id": result.misconception_id,
            "confidence": result.confidence,
            "cited_event_ids": [str(event.event_id) for event, _ in qualifying],
            "classifier_version": CLASSIFIER_VERSION,
        },
    )


def _last_answer_at_by_pair(db: Session) -> dict[tuple[uuid.UUID, str, str], object]:
    """Latest *qualifying* free-text `ANSWER_SUBMITTED` event's
    `created_at` per pair -- filtered to incorrect answers in Python
    (mirrors `_qualifying_events`'s own `payload.get("correct") is
    False` filter, since that's the only evidence a classification can
    ever be based on) so a subsequent *correct* answer, which changes
    nothing `classify_learner_topic` would see, cannot advance the
    watermark and trigger a duplicate re-classification."""
    events = (
        db.query(AssessmentEvent)
        .join(GeneratedQuestion, AssessmentEvent.question_id == GeneratedQuestion.question_id)
        .filter(
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
            GeneratedQuestion.question_type == QuestionType.FREE_TEXT,
        )
        .all()
    )
    last_at: dict[tuple[uuid.UUID, str, str], object] = {}
    for event in events:
        if event.payload.get("correct") is not False:
            continue
        key = (event.learner_id, event.subject_id, event.topic_id)
        if key not in last_at or event.created_at > last_at[key]:
            last_at[key] = event.created_at
    return last_at


def _last_classified_at_by_pair(db: Session) -> dict[tuple[uuid.UUID, str, str], object]:
    rows = (
        db.query(
            AssessmentEvent.learner_id,
            AssessmentEvent.subject_id,
            AssessmentEvent.topic_id,
            func.max(AssessmentEvent.created_at),
        )
        .filter(AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED)
        .group_by(AssessmentEvent.learner_id, AssessmentEvent.subject_id, AssessmentEvent.topic_id)
        .all()
    )
    return {
        (learner_id, subject_id, topic_id): last_at
        for learner_id, subject_id, topic_id, last_at in rows
    }


def run_classification_batch(db: Session) -> int:
    """Scans `(learner_id, subject_id, topic_id)` pairs with newly-
    qualifying free-text evidence since the last run and (re)classifies
    each -- called by the scheduled cron route (`api/routes/cron.py`),
    never inline in a request (research.md §3). The watermark is the
    existing `misconception_classified` event's own `created_at` per
    pair (no new column/table) -- a pair with no free-text answer newer
    than its last classification is skipped: nothing new to say, so
    re-embedding its whole history and writing a duplicate event would
    be pure waste. A pair never classified before always runs (subject
    to `classify_learner_topic`'s own evidence/confidence thresholds).
    Returns the number of pairs that actually produced a new
    `misconception_classified` event this run, not the number scanned.
    """
    last_answer_at = _last_answer_at_by_pair(db)
    last_classified_at = _last_classified_at_by_pair(db)

    classified_count = 0
    for (learner_id, subject_id, topic_id), answered_at in last_answer_at.items():
        classified_at = last_classified_at.get((learner_id, subject_id, topic_id))
        if classified_at is not None and answered_at <= classified_at:
            continue  # no new evidence since the last run
        try:
            event = classify_learner_topic(
                db, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id
            )
            db.commit()
        except Exception:
            # One bad pair (e.g. a missing classifier.joblib for this
            # subject, ClassifierUnavailableError) must never fail the
            # whole scheduled run (spec 013 US2/FR-006) -- roll back
            # just this pair's partial work and keep going.
            db.rollback()
            logger.exception(
                "misconception classification failed for learner=%s subject=%s topic=%s",
                learner_id,
                subject_id,
                topic_id,
            )
            continue
        if event is not None:
            classified_count += 1
    return classified_count

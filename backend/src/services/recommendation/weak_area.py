"""Weak-area classification and evidence citation (FR-002, FR-003,
FR-003a, FR-004, FR-005).

Every decision here is deterministic code reading the mastery model's
existing output -- never an LLM's judgment call (FR-011, spec.md
Clarifications). `classify_topic_status` is the pure per-topic rule,
directly unit-testable with no DB; `classify_topics` is the
DB-querying orchestration that applies it across a subject's topics and
assembles evidence citations, mirroring `agents/sequencing/agent.py`'s
own pure-`_sort_key`-plus-DB-querying-`select_next_topic` split.
"""

import datetime
import enum
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, MasteryBand, mastery_band_for
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState
from src.models.topic import Topic

# FR-004's per-topic minimum: fewer than this many recorded assessment
# events and a topic cannot be confidently classified weak/in-progress/
# mastered, regardless of its raw p_mastery.
CONFIDENT_MIN_EVENTS = 3

# FR-005's broad-review proportion: at or above this share of
# confidently-assessed topics in the struggling band switches the
# report to "broad review needed" framing.
BROAD_REVIEW_THRESHOLD = 0.6


class TopicStatus(enum.StrEnum):
    NOT_YET_ASSESSED = "not_yet_assessed"
    INSUFFICIENT_DATA = "insufficient_data"
    WEAK = "weak"
    IN_PROGRESS = "in_progress"
    MASTERED = "mastered"


def classify_topic_status(
    *,
    p_mastery: float | None,
    update_count: int,
    consecutive_mastered_observations: int = 0,
) -> TopicStatus:
    """Pure per-topic classification -- no `MasteryState` row
    (`p_mastery is None`) is "not yet assessed" (FR-003); fewer than
    `CONFIDENT_MIN_EVENTS` is "insufficient data" (FR-004); otherwise
    the topic's three-band mastery classification (Milestone 1's
    `mastery_band_for`, reused rather than reimplemented per
    research.md §4) decides weak (FR-002), in-progress (FR-003a), or
    mastered (intentionally omitted from the report, spec.md Key
    Entities)."""
    if p_mastery is None:
        return TopicStatus.NOT_YET_ASSESSED
    if update_count < CONFIDENT_MIN_EVENTS:
        return TopicStatus.INSUFFICIENT_DATA
    band = mastery_band_for(p_mastery, consecutive_mastered_observations)
    if band is MasteryBand.STRUGGLING:
        return TopicStatus.WEAK
    if band is MasteryBand.DEVELOPING:
        return TopicStatus.IN_PROGRESS
    return TopicStatus.MASTERED


@dataclass(frozen=True)
class EvidenceCitation:
    event_id: uuid.UUID
    question_id: uuid.UUID
    question_stem: str
    answer_correct: bool
    prior_p_mastery: float | None
    posterior_p_mastery: float
    created_at: datetime.datetime


@dataclass(frozen=True)
class FlaggedWeakArea:
    topic_id: str
    display_name: str
    p_mastery: float
    evidence: list[EvidenceCitation] = field(default_factory=list)


@dataclass(frozen=True)
class MisconceptionEnrichment:
    """spec 013's read-time view of the most recent matching
    Misconception Classification for one `WeakAreaFlag` -- distinct
    from the persisted `misconception_classified` event itself
    (data-model.md's naming clarification)."""

    misconception_id: str
    description: str
    confidence: float
    evidence: list[EvidenceCitation]


@dataclass(frozen=True)
class WeakAreaClassification:
    subject_id: str
    data_sufficiency: str  # "confident" | "insufficient_data"
    broad_review_needed: bool
    weak_areas: list[FlaggedWeakArea]
    in_progress_topic_ids: list[str]
    not_yet_assessed_topic_ids: list[str]
    insufficient_data_topic_ids: list[str]


def _evidence_citations_from_rows(
    rows: list[tuple[AssessmentEvent, GeneratedQuestion]],
) -> list[EvidenceCitation]:
    """Builds `EvidenceCitation` objects from `(mastery_updated event,
    question)` pairs -- shared by `_build_evidence` (every qualifying
    event for a topic) and `get_misconception_enrichment` (spec 013,
    only the events a classification specifically cited)."""
    return [
        EvidenceCitation(
            event_id=event.event_id,
            question_id=question.question_id,
            question_stem=question.stem,
            answer_correct=event.payload["answer_correct"],
            prior_p_mastery=event.payload.get("prior_p_mastery"),
            posterior_p_mastery=event.payload["posterior_p_mastery"],
            created_at=event.created_at,
        )
        for event, question in rows
    ]


def _build_evidence(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, topic_id: str
) -> list[EvidenceCitation]:
    """Cites every qualifying `mastery_updated` event for this topic --
    by construction there are exactly `MasteryState.update_count` of
    them (FR-002/SC-002: never a bare topic name and number)."""
    rows = (
        db.query(AssessmentEvent, GeneratedQuestion)
        .join(GeneratedQuestion, AssessmentEvent.question_id == GeneratedQuestion.question_id)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.subject_id == subject_id,
            AssessmentEvent.topic_id == topic_id,
            AssessmentEvent.event_type == AssessmentEventType.MASTERY_UPDATED,
        )
        .order_by(AssessmentEvent.created_at)
        .all()
    )
    return _evidence_citations_from_rows(rows)


def get_misconception_enrichment(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, topic_id: str
) -> "MisconceptionEnrichment | None":
    """Reads the most recent `misconception_classified` event for this
    learner/topic, if any, and builds the display-ready
    `MisconceptionEnrichment` (spec 013 FR-006's graceful degradation:
    `None` whenever no such event exists -- no taxonomy authored, no
    trained classifier yet, or evidence/confidence below threshold at
    classification time). A plain DB read -- never a live classifier or
    LLM call (research.md §3), mirroring `suggest_next_step`'s own
    independent-DB-orchestration style."""
    event = (
        db.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.subject_id == subject_id,
            AssessmentEvent.topic_id == topic_id,
            AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED,
        )
        .order_by(AssessmentEvent.created_at.desc())
        .first()
    )
    if event is None:
        return None

    cited_event_ids = [uuid.UUID(raw_id) for raw_id in event.payload["cited_event_ids"]]
    cited_question_ids = [
        row.question_id
        for row in db.query(AssessmentEvent.question_id).filter(
            AssessmentEvent.event_id.in_(cited_event_ids)
        )
    ]
    rows = (
        db.query(AssessmentEvent, GeneratedQuestion)
        .join(GeneratedQuestion, AssessmentEvent.question_id == GeneratedQuestion.question_id)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.subject_id == subject_id,
            AssessmentEvent.topic_id == topic_id,
            AssessmentEvent.event_type == AssessmentEventType.MASTERY_UPDATED,
            AssessmentEvent.question_id.in_(cited_question_ids),
        )
        .order_by(AssessmentEvent.created_at)
        .all()
    )
    evidence = _evidence_citations_from_rows(rows)

    topic = db.query(Topic).filter(Topic.subject_id == subject_id, Topic.topic_id == topic_id).one()
    description = next(
        (
            m["description"]
            for m in topic.skill_definition.get("misconceptions", [])
            if m["misconception_id"] == event.payload["misconception_id"]
        ),
        event.payload["misconception_id"],
    )

    return MisconceptionEnrichment(
        misconception_id=event.payload["misconception_id"],
        description=description,
        confidence=event.payload["confidence"],
        evidence=evidence,
    )


def classify_topics(
    db: Session, *, learner_id: uuid.UUID, subject_id: str
) -> WeakAreaClassification:
    """Classifies every topic in `subject_id` for `learner_id`, in
    `Topic.order_index` order (the same deterministic ordering
    `select_next_topic` uses), and assembles the report-level
    `data_sufficiency`/`broad_review_needed` verdicts."""
    topics = (
        db.query(Topic).filter(Topic.subject_id == subject_id).order_by(Topic.order_index).all()
    )
    mastery_by_topic = {
        state.topic_id: state
        for state in db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .all()
    }

    weak_areas: list[FlaggedWeakArea] = []
    in_progress_topic_ids: list[str] = []
    not_yet_assessed_topic_ids: list[str] = []
    insufficient_data_topic_ids: list[str] = []
    confidently_assessed_count = 0
    struggling_confident_count = 0

    for topic in topics:
        state = mastery_by_topic.get(topic.topic_id)
        status = classify_topic_status(
            p_mastery=state.p_mastery if state else None,
            update_count=state.update_count if state else 0,
            consecutive_mastered_observations=(
                state.consecutive_mastered_observations if state else 0
            ),
        )

        if status is TopicStatus.NOT_YET_ASSESSED:
            not_yet_assessed_topic_ids.append(topic.topic_id)
            continue
        if status is TopicStatus.INSUFFICIENT_DATA:
            insufficient_data_topic_ids.append(topic.topic_id)
            continue

        # FR-005's denominator: every confidently-assessed topic,
        # regardless of which band it confidently lands in.
        confidently_assessed_count += 1

        if status is TopicStatus.WEAK:
            struggling_confident_count += 1
            evidence = _build_evidence(
                db, learner_id=learner_id, subject_id=subject_id, topic_id=topic.topic_id
            )
            weak_areas.append(
                FlaggedWeakArea(
                    topic_id=topic.topic_id,
                    display_name=topic.display_name,
                    p_mastery=state.p_mastery,
                    evidence=evidence,
                )
            )
        elif status is TopicStatus.IN_PROGRESS:
            in_progress_topic_ids.append(topic.topic_id)
        # TopicStatus.MASTERED: intentionally not represented in the
        # report (spec.md Key Entities) -- counted above for FR-005's
        # denominator only.

    # FR-004: zero confidently-assessed topics (whether because none
    # were touched at all, or every touched topic is still below the
    # per-topic minimum) means the report can't reach a confident
    # verdict -- vacuously true for a brand-new learner, per spec.md
    # FR-004/Clarifications.
    data_sufficiency = "insufficient_data" if confidently_assessed_count == 0 else "confident"

    broad_review_needed = confidently_assessed_count > 0 and (
        struggling_confident_count / confidently_assessed_count >= BROAD_REVIEW_THRESHOLD
    )

    return WeakAreaClassification(
        subject_id=subject_id,
        data_sufficiency=data_sufficiency,
        broad_review_needed=broad_review_needed,
        weak_areas=weak_areas,
        in_progress_topic_ids=in_progress_topic_ids,
        not_yet_assessed_topic_ids=not_yet_assessed_topic_ids,
        insufficient_data_topic_ids=insufficient_data_topic_ids,
    )

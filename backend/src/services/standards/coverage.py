"""Standards-coverage computation (spec 038 FR-004/FR-006/FR-007,
data-model.md). Derives met/in-progress/not-yet-reached per standard
from already-persisted `MasteryState` rows -- no new mastery
computation (Constitution Principle I). Shared by both `mastery.py`
(guardian/demo path) and `services/dashboard/aggregation.py` (instructor
path) so both surfaces compute identically (FR-004).
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.enums import MasteryBand
from src.models.mastery_state import MasteryState
from src.models.standards_tag import StandardsTag
from src.models.topic import Topic

CoverageStatus = Literal["met", "in_progress", "not_yet_reached"]


@dataclass(frozen=True)
class StandardCoverageEntry:
    framework: str
    code: str
    title: str
    topic_ids: tuple[str, ...]
    status: CoverageStatus


def compute_standards_coverage(
    db: Session, *, learner_id: UUID, subject_id: str
) -> list[StandardCoverageEntry]:
    """One entry per distinct `(framework, code)` tagged anywhere in
    `subject_id`, ordered by each standard's first-tagged topic's
    authored order (`Topic.order_index`) for a stable, deterministic
    listing. Empty list for a subject with zero `StandardsTag` rows
    (FR-006/FR-009).
    """
    tagged = (
        db.query(StandardsTag, Topic.order_index)
        .join(
            Topic,
            (Topic.subject_id == StandardsTag.subject_id)
            & (Topic.topic_id == StandardsTag.topic_id),
        )
        .filter(StandardsTag.subject_id == subject_id)
        .order_by(Topic.order_index)
        .all()
    )
    if not tagged:
        return []

    topic_ids_by_code: dict[tuple[str, str], list[str]] = {}
    title_by_code: dict[tuple[str, str], str] = {}
    for tag, _order_index in tagged:
        key = (tag.framework, tag.code)
        topic_ids_by_code.setdefault(key, []).append(tag.topic_id)
        title_by_code[key] = tag.title

    all_topic_ids = {tag.topic_id for tag, _ in tagged}
    mastery_by_topic: dict[str, MasteryState] = {
        state.topic_id: state
        for state in db.query(MasteryState).filter(
            MasteryState.learner_id == learner_id,
            MasteryState.subject_id == subject_id,
            MasteryState.topic_id.in_(all_topic_ids),
        )
    }

    entries: list[StandardCoverageEntry] = []
    for key, topic_ids in topic_ids_by_code.items():
        framework, code = key
        states = [mastery_by_topic.get(topic_id) for topic_id in topic_ids]
        if all(state is None for state in states):
            status: CoverageStatus = "not_yet_reached"
        elif all(state is not None and state.band == MasteryBand.MASTERED for state in states):
            status = "met"
        else:
            status = "in_progress"
        entries.append(
            StandardCoverageEntry(
                framework=framework,
                code=code,
                title=title_by_code[key],
                topic_ids=tuple(topic_ids),
                status=status,
            )
        )
    return entries

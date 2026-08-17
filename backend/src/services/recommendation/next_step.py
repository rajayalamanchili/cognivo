"""Prerequisite-aware next-step suggestion (FR-006, FR-007).

Deterministic recursion over the content artifact's prerequisite graph
-- never an LLM's judgment (FR-011). `classify_prerequisite_gap` is the
pure graph walk, directly unit-testable against plain lookup maps;
`suggest_next_step` is the DB-querying wrapper that builds those maps,
mirroring `weak_area.py`'s own pure/DB-orchestration split.
"""

import enum
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.models.enums import MasteryBand, mastery_band_for
from src.models.mastery_state import MasteryState
from src.models.prerequisite_edge import PrerequisiteEdge
from src.models.topic import Topic


class NextStepReason(enum.StrEnum):
    DIRECT_PRACTICE = "direct_practice"
    PREREQUISITE_GAP = "prerequisite_gap"
    PREREQUISITE_NOT_YET_ASSESSED = "prerequisite_not_yet_assessed"


@dataclass(frozen=True)
class NextStepSuggestion:
    recommended_topic_id: str
    recommended_display_name: str
    reason: NextStepReason
    prerequisite_chain: list[str] = field(default_factory=list)


def _sort_key(p_mastery: float | None, order_index: int) -> tuple[float, int]:
    """Lowest `p_mastery` first, `unknown` (None) ranked ahead of any
    numeric value -- the identical tie-break `agents/sequencing/
    agent.py`'s `_sort_key` already uses for topic selection, reused
    here (research.md §5) rather than reimplemented."""
    return (-1.0 if p_mastery is None else p_mastery, order_index)


def _is_unmastered(p_mastery: float | None) -> bool:
    """FR-007's "unmastered" check: the same struggling-band cutoff
    FR-002 uses for flagging weak areas -- not yet assessed
    (`p_mastery is None`) is also treated as unmastered for recursion
    purposes (a topic with no data can't have satisfied a prerequisite).
    `consecutive_mastered_observations` is irrelevant to the struggling
    boundary, so 0 is a safe default here."""
    if p_mastery is None:
        return True
    return mastery_band_for(p_mastery, 0) is MasteryBand.STRUGGLING


def classify_prerequisite_gap(
    topic_id: str,
    *,
    prereqs_by_topic: dict[str, list[str]],
    p_mastery_by_topic: dict[str, float | None],
    order_index_by_topic: dict[str, int],
    display_name_by_topic: dict[str, str],
) -> NextStepSuggestion:
    """Pure FR-007 recursion: walks from `topic_id` through unmastered
    direct prerequisites until reaching a topic whose own prerequisites
    are all mastered/nonexistent (`prerequisite_gap`, naming the
    deepest such topic), or a topic with no recorded assessment data
    at all (`prerequisite_not_yet_assessed`, stopping there rather than
    assuming mastered or unmastered). A topic with more than one
    unmastered direct prerequisite recurses into only the lowest-
    `p_mastery` one, ties broken by `order_index` -- never a branching
    set (spec.md FR-007). No cycle guard is needed: content-artifact
    load-time validation already guarantees the prerequisite graph is
    acyclic (research.md §5)."""
    chain: list[str] = []
    current = topic_id

    while True:
        prereq_ids = prereqs_by_topic.get(current, [])
        unmastered_prereqs = [p for p in prereq_ids if _is_unmastered(p_mastery_by_topic.get(p))]

        if not unmastered_prereqs:
            break

        chosen = min(
            unmastered_prereqs,
            key=lambda p: _sort_key(p_mastery_by_topic.get(p), order_index_by_topic[p]),
        )
        chain.append(chosen)

        if p_mastery_by_topic.get(chosen) is None:
            return NextStepSuggestion(
                recommended_topic_id=chosen,
                recommended_display_name=display_name_by_topic[chosen],
                reason=NextStepReason.PREREQUISITE_NOT_YET_ASSESSED,
                prerequisite_chain=chain,
            )

        current = chosen

    if not chain:
        return NextStepSuggestion(
            recommended_topic_id=topic_id,
            recommended_display_name=display_name_by_topic[topic_id],
            reason=NextStepReason.DIRECT_PRACTICE,
        )

    return NextStepSuggestion(
        recommended_topic_id=chain[-1],
        recommended_display_name=display_name_by_topic[chain[-1]],
        reason=NextStepReason.PREREQUISITE_GAP,
        prerequisite_chain=chain,
    )


def suggest_next_step(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, topic_id: str
) -> NextStepSuggestion:
    """Loads `subject_id`'s topic graph and `learner_id`'s mastery
    state, then delegates to `classify_prerequisite_gap`."""
    topics = {
        topic.topic_id: topic
        for topic in db.query(Topic).filter(Topic.subject_id == subject_id).all()
    }
    edges = db.query(PrerequisiteEdge).filter(PrerequisiteEdge.subject_id == subject_id).all()
    prereqs_by_topic: dict[str, list[str]] = {t: [] for t in topics}
    for edge in edges:
        prereqs_by_topic.setdefault(edge.from_topic_id, []).append(edge.to_topic_id)

    mastery_by_topic = {
        state.topic_id: state
        for state in db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .all()
    }
    p_mastery_by_topic = {
        t: (mastery_by_topic[t].p_mastery if t in mastery_by_topic else None) for t in topics
    }
    order_index_by_topic = {t: topic.order_index for t, topic in topics.items()}
    display_name_by_topic = {t: topic.display_name for t, topic in topics.items()}

    return classify_prerequisite_gap(
        topic_id,
        prereqs_by_topic=prereqs_by_topic,
        p_mastery_by_topic=p_mastery_by_topic,
        order_index_by_topic=order_index_by_topic,
        display_name_by_topic=display_name_by_topic,
    )

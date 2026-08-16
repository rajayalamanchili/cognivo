"""Sequencing Agent: next-topic selection + wired question generation
(FR-006, T046/T047).

Topic *selection* here is the same deterministic-model discipline as the
mastery-update tool (Constitution Principle I) -- never an LLM guessing
which topic comes next. Only the actual question *content* is delegated
to the Assessment-Generation Agent, with the near-duplicate check
(FR-008) run against its output before it's handed back to the caller.
"""

import uuid
from dataclasses import dataclass, field

from google.adk.sessions import BaseSessionService
from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import GeneratedQuestionDraft, generate_question
from src.agents.diagnostic.agent import (
    difficulty_guidance,
    preferred_question_type,
    skill_summary,
)
from src.models.enums import DifficultyBand, QuestionType
from src.models.mastery_state import MasteryState
from src.models.prerequisite_edge import PrerequisiteEdge
from src.models.topic import Topic
from src.services.dedup.checker import (
    DEFAULT_LOOKBACK,
    is_near_duplicate,
    recent_stems_for_topic,
)

# Selection uses the plain band label including "unknown" -- MasteryBand
# (models/enums.py) intentionally has no "unknown" member since "unknown"
# is the *absence* of a MasteryState row (FR-005), not a stored band.
_ELIGIBLE_BANDS = frozenset({"unknown", "struggling", "developing"})

_DIFFICULTY_BY_BAND: dict[str, DifficultyBand] = {
    "unknown": DifficultyBand.EASY,
    "struggling": DifficultyBand.EASY,
    "developing": DifficultyBand.MEDIUM,
    "mastered": DifficultyBand.HARD,
}


@dataclass(frozen=True)
class TopicCandidate:
    topic_id: str
    band: str  # "unknown" | "struggling" | "developing" | "mastered"
    p_mastery: float | None


@dataclass(frozen=True)
class NextTopicSelection:
    topic_id: str
    band: str
    p_mastery: float | None
    difficulty: DifficultyBand
    is_fallback: bool
    candidates_considered: list[TopicCandidate] = field(default_factory=list)


def _sort_key(p_mastery: float | None, order_index: int) -> tuple[float, int]:
    """Lowest `p_mastery` first, `unknown` (None) ranked ahead of any
    numeric value (data-model.md's Next-topic eligibility rule)."""
    return (-1.0 if p_mastery is None else p_mastery, order_index)


def select_next_topic(db: Session, *, learner_id: uuid.UUID, subject_id: str) -> NextTopicSelection:
    """Selects the next topic per data-model.md's Next-topic eligibility
    and Difficulty-selection rules. Always returns a selection -- if zero
    topics are eligible, falls back to the lowest-`p_mastery` `mastered`
    topic rather than raising (contracts/api.md: next-question is always
    a `200`)."""
    topics = (
        db.query(Topic).filter(Topic.subject_id == subject_id).order_by(Topic.order_index).all()
    )
    edges = db.query(PrerequisiteEdge).filter(PrerequisiteEdge.subject_id == subject_id).all()
    mastery_by_topic = {
        state.topic_id: state
        for state in db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .all()
    }

    def band_of(topic_id: str) -> str:
        state = mastery_by_topic.get(topic_id)
        return "unknown" if state is None else state.band.value

    def p_mastery_of(topic_id: str) -> float | None:
        state = mastery_by_topic.get(topic_id)
        return None if state is None else state.p_mastery

    prereqs_by_topic: dict[str, list[str]] = {topic.topic_id: [] for topic in topics}
    for edge in edges:
        prereqs_by_topic.setdefault(edge.from_topic_id, []).append(edge.to_topic_id)

    def prereqs_satisfied(topic_id: str) -> bool:
        return all(band_of(prereq_id) == "mastered" for prereq_id in prereqs_by_topic[topic_id])

    candidates = [
        TopicCandidate(
            topic_id=t.topic_id, band=band_of(t.topic_id), p_mastery=p_mastery_of(t.topic_id)
        )
        for t in topics
    ]

    eligible = [
        t
        for t in topics
        if band_of(t.topic_id) in _ELIGIBLE_BANDS and prereqs_satisfied(t.topic_id)
    ]

    if eligible:
        chosen = min(eligible, key=lambda t: _sort_key(p_mastery_of(t.topic_id), t.order_index))
        is_fallback = False
    else:
        mastered = [t for t in topics if band_of(t.topic_id) == "mastered"]
        pool = mastered or topics
        chosen = min(pool, key=lambda t: _sort_key(p_mastery_of(t.topic_id), t.order_index))
        is_fallback = True

    chosen_band = band_of(chosen.topic_id)
    return NextTopicSelection(
        topic_id=chosen.topic_id,
        band=chosen_band,
        p_mastery=p_mastery_of(chosen.topic_id),
        difficulty=_DIFFICULTY_BY_BAND[chosen_band],
        is_fallback=is_fallback,
        candidates_considered=candidates,
    )


@dataclass(frozen=True)
class NextQuestionResult:
    selection: NextTopicSelection
    question_type: QuestionType
    draft: GeneratedQuestionDraft


async def generate_next_question(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    session_service: BaseSessionService,
    dedup_lookback: int = DEFAULT_LOOKBACK,
    max_dedup_attempts: int = 3,
) -> NextQuestionResult:
    """Selects the next topic (T046), then generates a question for it,
    retrying generation up to `max_dedup_attempts` times if the draft is
    a near-duplicate of the learner's recent questions on that topic
    (FR-008, T047) before giving up and returning the last draft."""
    selection = select_next_topic(db, learner_id=learner_id, subject_id=subject_id)
    topic = db.get(Topic, (subject_id, selection.topic_id))
    question_type = preferred_question_type(topic)
    recent_stems = recent_stems_for_topic(
        db,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=selection.topic_id,
        limit=dedup_lookback,
    )

    draft: GeneratedQuestionDraft | None = None
    for _ in range(max_dedup_attempts):
        draft = await generate_question(
            topic_display_name=topic.display_name,
            skill_summary=skill_summary(topic),
            difficulty=selection.difficulty,
            difficulty_guidance=difficulty_guidance(topic, selection.difficulty),
            question_type=question_type,
            session_service=session_service,
            avoid_stems=recent_stems,
        )
        if not is_near_duplicate(draft.stem, recent_stems):
            break

    return NextQuestionResult(selection=selection, question_type=question_type, draft=draft)

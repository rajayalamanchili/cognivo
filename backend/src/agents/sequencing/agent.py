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


def rank_eligible_topics(
    topic_ids_in_order: list[str],
    *,
    band_by_topic: dict[str, str],
    p_mastery_by_topic: dict[str, float | None],
    prereqs_by_topic: dict[str, list[str]],
) -> tuple[list[str], bool]:
    """Pure eligibility/ranking rule (data-model.md's Next-topic
    eligibility rule), directly unit-testable with no DB -- mirrors
    `weak_area.py`'s/`next_step.py`'s own pure-rule-plus-DB-querying-
    wrapper split. Shared by `select_next_topic` (which uses only the
    top-ranked topic) and `preview_topic_priority` (which also exposes
    the next few), so FR-003's "not a separately invented ordering"
    guarantee for the dashboard's upcoming-topics list holds by
    construction rather than by convention.

    Returns topic ids ranked lowest-`p_mastery`-first (`unknown` ranked
    ahead of any numeric value), ties broken by `topic_ids_in_order`'s
    original order (`Topic.order_index`), plus whether the ranking fell
    back to the mastered-topics-or-all-topics pool because zero topics
    were strictly eligible (every topic mastered, or none has its
    prerequisites satisfied)."""
    order_index_by_topic = {topic_id: index for index, topic_id in enumerate(topic_ids_in_order)}

    def prereqs_satisfied(topic_id: str) -> bool:
        return all(
            band_by_topic[prereq_id] == "mastered" for prereq_id in prereqs_by_topic[topic_id]
        )

    eligible = [
        t
        for t in topic_ids_in_order
        if band_by_topic[t] in _ELIGIBLE_BANDS and prereqs_satisfied(t)
    ]

    if eligible:
        pool, is_fallback = eligible, False
    else:
        mastered = [t for t in topic_ids_in_order if band_by_topic[t] == "mastered"]
        pool, is_fallback = (mastered or topic_ids_in_order), True

    ranked = sorted(pool, key=lambda t: _sort_key(p_mastery_by_topic[t], order_index_by_topic[t]))
    return ranked, is_fallback


@dataclass(frozen=True)
class _TopicRankingContext:
    topic_ids_in_order: list[str]
    band_by_topic: dict[str, str]
    p_mastery_by_topic: dict[str, float | None]
    prereqs_by_topic: dict[str, list[str]]
    display_name_by_topic: dict[str, str]


def _load_topic_ranking_context(
    db: Session, *, learner_id: uuid.UUID, subject_id: str
) -> _TopicRankingContext:
    """DB-querying orchestration shared by `select_next_topic` and
    `preview_topic_priority` -- builds the plain lookup maps
    `rank_eligible_topics` needs."""
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

    return _TopicRankingContext(
        topic_ids_in_order=[t.topic_id for t in topics],
        band_by_topic={t.topic_id: band_of(t.topic_id) for t in topics},
        p_mastery_by_topic={t.topic_id: p_mastery_of(t.topic_id) for t in topics},
        prereqs_by_topic=prereqs_by_topic,
        display_name_by_topic={t.topic_id: t.display_name for t in topics},
    )


def select_next_topic(db: Session, *, learner_id: uuid.UUID, subject_id: str) -> NextTopicSelection:
    """Selects the next topic per data-model.md's Next-topic eligibility
    and Difficulty-selection rules. Always returns a selection -- if zero
    topics are eligible, falls back to the lowest-`p_mastery` `mastered`
    topic rather than raising (contracts/api.md: next-question is always
    a `200`)."""
    ctx = _load_topic_ranking_context(db, learner_id=learner_id, subject_id=subject_id)

    candidates = [
        TopicCandidate(topic_id=t, band=ctx.band_by_topic[t], p_mastery=ctx.p_mastery_by_topic[t])
        for t in ctx.topic_ids_in_order
    ]

    ranked, is_fallback = rank_eligible_topics(
        ctx.topic_ids_in_order,
        band_by_topic=ctx.band_by_topic,
        p_mastery_by_topic=ctx.p_mastery_by_topic,
        prereqs_by_topic=ctx.prereqs_by_topic,
    )
    chosen_id = ranked[0]
    chosen_band = ctx.band_by_topic[chosen_id]
    return NextTopicSelection(
        topic_id=chosen_id,
        band=chosen_band,
        p_mastery=ctx.p_mastery_by_topic[chosen_id],
        difficulty=_DIFFICULTY_BY_BAND[chosen_band],
        is_fallback=is_fallback,
        candidates_considered=candidates,
    )


@dataclass(frozen=True)
class TopicPreviewEntry:
    topic_id: str
    display_name: str
    band: str
    p_mastery: float | None


@dataclass(frozen=True)
class TopicPriorityPreview:
    subject_id: str
    next_topic: TopicPreviewEntry
    upcoming_topics: list[TopicPreviewEntry]
    is_fallback: bool


def preview_topic_priority(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, upcoming_count: int = 3
) -> TopicPriorityPreview:
    """Read-only preview of the same ranking `select_next_topic` uses to
    pick the real next topic (research.md §1) -- exposes the next
    `upcoming_count` ranked entries too, without generating a question
    or committing a selection. Callers must not write an `AssessmentEvent`
    row or wrap this in `traced_request()` (research.md §3): this is an
    illustrative dashboard preview, not a real pedagogical decision."""
    ctx = _load_topic_ranking_context(db, learner_id=learner_id, subject_id=subject_id)
    ranked, is_fallback = rank_eligible_topics(
        ctx.topic_ids_in_order,
        band_by_topic=ctx.band_by_topic,
        p_mastery_by_topic=ctx.p_mastery_by_topic,
        prereqs_by_topic=ctx.prereqs_by_topic,
    )

    def to_entry(topic_id: str) -> TopicPreviewEntry:
        return TopicPreviewEntry(
            topic_id=topic_id,
            display_name=ctx.display_name_by_topic[topic_id],
            band=ctx.band_by_topic[topic_id],
            p_mastery=ctx.p_mastery_by_topic[topic_id],
        )

    return TopicPriorityPreview(
        subject_id=subject_id,
        next_topic=to_entry(ranked[0]),
        upcoming_topics=[to_entry(t) for t in ranked[1 : 1 + upcoming_count]],
        is_fallback=is_fallback,
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

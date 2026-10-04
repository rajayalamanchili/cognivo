"""Sequencing Agent: next-topic selection + wired question generation
(FR-006, T046/T047).

Topic *selection* here is the same deterministic-model discipline as the
mastery-update tool (Constitution Principle I) -- never an LLM guessing
which topic comes next. Only the actual question *content* is delegated
to the Assessment-Generation Agent, with the near-duplicate check
(FR-008) run against its output before it's handed back to the caller.
"""

import datetime
import uuid
from dataclasses import dataclass, field

from google.adk.sessions import BaseSessionService
from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import (
    GENERATION_PROMPT_VERSION,
    GeneratedQuestionDraft,
    generate_question,
)
from src.agents.diagnostic.agent import (
    difficulty_guidance,
    preferred_question_type,
    skill_summary,
)
from src.models.enums import DifficultyBand, QuestionType
from src.models.grade_band import GradeBand
from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState
from src.models.prerequisite_edge import PrerequisiteEdge
from src.models.subject import Subject
from src.models.topic import Topic
from src.services.cache_common.outcome import CacheOutcome
from src.services.content_artifact.image_asset import content_image_url
from src.services.dedup.checker import (
    DEFAULT_LOOKBACK,
    is_near_duplicate,
    recent_stems_for_topic,
)
from src.services.mastery.decay import effective_mastery_for_review
from src.services.question_cache.cache import get_or_generate_question

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
    # Decayed value actually used to rank this candidate when it's a
    # "mastered" topic in the fallback pool (spec 024 FR-003/FR-004/
    # FR-005); equal to `p_mastery` otherwise. Carried into the audit
    # payload so a decay-broken tie between two equal raw `p_mastery`
    # topics is traceable after the fact (Constitution Principle V).
    effective_p_mastery: float | None


@dataclass(frozen=True)
class NextTopicSelection:
    topic_id: str
    band: str
    p_mastery: float | None
    effective_p_mastery: float | None
    difficulty: DifficultyBand
    is_fallback: bool
    # Spec 025 FR-002: when this topic has a prior MasteryState row, the
    # last time it was practiced -- lets the "why this question" chip name
    # actual elapsed time for a fallback/decayed pick, not just a value.
    updated_at: datetime.datetime | None = None
    # Spec 027: the chosen topic's own grade band (Topic.grade), already
    # loaded into `_TopicRankingContext.grade_by_topic` for the unlocked-
    # grade gate above -- a read-only lookup against data already in
    # memory for this request, not a new query. None for an ungraded
    # subject's topics, same as Topic.grade itself.
    grade: int | None = None
    candidates_considered: list[TopicCandidate] = field(default_factory=list)


def _sort_key(p_mastery: float | None, order_index: int) -> tuple[float, int]:
    """Lowest `p_mastery` first, `unknown` (None) ranked ahead of any
    numeric value (data-model.md's Next-topic eligibility rule)."""
    return (-1.0 if p_mastery is None else p_mastery, order_index)


def _effective_p_mastery_for_ranking(
    topic_id: str,
    *,
    band_by_topic: dict[str, str],
    p_mastery_by_topic: dict[str, float | None],
    updated_at_by_topic: dict[str, datetime.datetime] | None,
    now: datetime.datetime | None,
) -> float | None:
    """Returns the raw `p_mastery` unchanged unless `topic_id` is
    `"mastered"` and both decay inputs are available for it, in which
    case it returns the decayed value for ranking purposes only (spec
    024 FR-003/FR-004/FR-005). A no-op for every topic in the eligible
    pool by construction, since `_ELIGIBLE_BANDS` never includes
    `"mastered"` -- no branch needed to keep that pool's ranking
    untouched (research.md §2)."""
    p_mastery = p_mastery_by_topic[topic_id]
    if (
        band_by_topic[topic_id] != "mastered"
        or p_mastery is None
        or updated_at_by_topic is None
        or now is None
        or topic_id not in updated_at_by_topic
    ):
        return p_mastery
    return effective_mastery_for_review(
        p_mastery, updated_at=updated_at_by_topic[topic_id], now=now
    )


def rank_eligible_topics(
    topic_ids_in_order: list[str],
    *,
    band_by_topic: dict[str, str],
    p_mastery_by_topic: dict[str, float | None],
    prereqs_by_topic: dict[str, list[str]],
    grade_by_topic: dict[str, int | None] | None = None,
    unlocked_grade: int | None = None,
    updated_at_by_topic: dict[str, datetime.datetime] | None = None,
    now: datetime.datetime | None = None,
) -> tuple[list[str], bool]:
    """Pure eligibility/ranking rule (data-model.md's Next-topic
    eligibility rule), directly unit-testable with no DB -- mirrors
    `weak_area.py`'s/`next_step.py`'s own pure-rule-plus-DB-querying-
    wrapper split. Shared by `select_next_topic` (which uses only the
    top-ranked topic) and `preview_topic_priority` (which also exposes
    the next few), so FR-003's "not a separately invented ordering"
    guarantee for the dashboard's upcoming-topics list holds by
    construction rather than by convention.

    `grade_by_topic`/`unlocked_grade` add spec 017 User Story 2's grade
    gate: a topic whose `grade` is above `unlocked_grade` is excluded
    from every pool (eligible, mastered-fallback, and full-fallback)
    before ranking even begins -- it must never surface regardless of
    band/prerequisites (spec.md Edge Case: prerequisites spanning
    grades -- grade-gating and prerequisite-gating both apply,
    independently). An ungraded topic (`grade IS NULL`) or an ungraded
    subject (`unlocked_grade is None`) is unaffected, byte-identical to
    before this feature.

    `updated_at_by_topic`/`now` add spec 024's mastery decay: when both
    are supplied, a `"mastered"` topic's effective mastery for ranking
    purposes decays with elapsed time since its `updated_at` (see
    `_effective_p_mastery_for_ranking`) -- affecting only the ranking
    *within* the mastered-fallback pool this function may already fall
    back to. Omitting either (both default to `None`) reproduces
    pre-decay behavior exactly.

    Returns topic ids ranked lowest-`p_mastery`-first (`unknown` ranked
    ahead of any numeric value), ties broken by `topic_ids_in_order`'s
    original order (`Topic.order_index`), plus whether the ranking fell
    back to the mastered-topics-or-all-topics pool because zero topics
    were strictly eligible (every topic mastered, or none has its
    prerequisites satisfied)."""
    grade_by_topic = grade_by_topic or {}

    def within_unlocked_grade(topic_id: str) -> bool:
        topic_grade = grade_by_topic.get(topic_id)
        return topic_grade is None or unlocked_grade is None or topic_grade <= unlocked_grade

    topic_ids_in_order = [t for t in topic_ids_in_order if within_unlocked_grade(t)]
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

    def sort_key_for(topic_id: str) -> tuple[float, int]:
        effective_p_mastery = _effective_p_mastery_for_ranking(
            topic_id,
            band_by_topic=band_by_topic,
            p_mastery_by_topic=p_mastery_by_topic,
            updated_at_by_topic=updated_at_by_topic,
            now=now,
        )
        return _sort_key(effective_p_mastery, order_index_by_topic[topic_id])

    ranked = sorted(pool, key=sort_key_for)
    return ranked, is_fallback


@dataclass(frozen=True)
class _TopicRankingContext:
    topic_ids_in_order: list[str]
    band_by_topic: dict[str, str]
    p_mastery_by_topic: dict[str, float | None]
    prereqs_by_topic: dict[str, list[str]]
    display_name_by_topic: dict[str, str]
    grade_by_topic: dict[str, int | None]
    unlocked_grade: int | None
    updated_at_by_topic: dict[str, datetime.datetime]


def _load_topic_ranking_context(
    db: Session, *, learner_id: uuid.UUID, subject_id: str
) -> _TopicRankingContext:
    """DB-querying orchestration shared by `select_next_topic` and
    `preview_topic_priority` -- builds the plain lookup maps
    `rank_eligible_topics` needs."""
    topics = (
        db.query(Topic).filter(Topic.subject_id == subject_id).order_by(Topic.order_index).all()
    )
    declared_grades = [
        row.grade for row in db.query(GradeBand).filter(GradeBand.subject_id == subject_id).all()
    ]
    unlocked_grade: int | None = None
    if declared_grades:
        progress = db.get(GradeProgress, (learner_id, subject_id))
        # No GradeProgress row yet (data-model.md's defensive default):
        # only reachable if a learner answers a graded subject's
        # question before ever completing its placement flow -- gate at
        # the lowest declared grade rather than leaving everything open.
        unlocked_grade = progress.unlocked_grade if progress is not None else min(declared_grades)
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

    updated_at_by_topic = {
        topic_id: state.updated_at for topic_id, state in mastery_by_topic.items()
    }

    prereqs_by_topic: dict[str, list[str]] = {topic.topic_id: [] for topic in topics}
    for edge in edges:
        prereqs_by_topic.setdefault(edge.from_topic_id, []).append(edge.to_topic_id)

    return _TopicRankingContext(
        topic_ids_in_order=[t.topic_id for t in topics],
        band_by_topic={t.topic_id: band_of(t.topic_id) for t in topics},
        p_mastery_by_topic={t.topic_id: p_mastery_of(t.topic_id) for t in topics},
        prereqs_by_topic=prereqs_by_topic,
        display_name_by_topic={t.topic_id: t.display_name for t in topics},
        grade_by_topic={t.topic_id: t.grade for t in topics},
        unlocked_grade=unlocked_grade,
        updated_at_by_topic=updated_at_by_topic,
    )


def select_next_topic(db: Session, *, learner_id: uuid.UUID, subject_id: str) -> NextTopicSelection:
    """Selects the next topic per data-model.md's Next-topic eligibility
    and Difficulty-selection rules. Always returns a selection -- if zero
    topics are eligible, falls back to the lowest-`p_mastery` `mastered`
    topic rather than raising (contracts/api.md: next-question is always
    a `200`)."""
    ctx = _load_topic_ranking_context(db, learner_id=learner_id, subject_id=subject_id)
    now = datetime.datetime.now(datetime.UTC)

    def effective_p_mastery_of(topic_id: str) -> float | None:
        return _effective_p_mastery_for_ranking(
            topic_id,
            band_by_topic=ctx.band_by_topic,
            p_mastery_by_topic=ctx.p_mastery_by_topic,
            updated_at_by_topic=ctx.updated_at_by_topic,
            now=now,
        )

    candidates = [
        TopicCandidate(
            topic_id=t,
            band=ctx.band_by_topic[t],
            p_mastery=ctx.p_mastery_by_topic[t],
            effective_p_mastery=effective_p_mastery_of(t),
        )
        for t in ctx.topic_ids_in_order
    ]

    ranked, is_fallback = rank_eligible_topics(
        ctx.topic_ids_in_order,
        band_by_topic=ctx.band_by_topic,
        p_mastery_by_topic=ctx.p_mastery_by_topic,
        prereqs_by_topic=ctx.prereqs_by_topic,
        grade_by_topic=ctx.grade_by_topic,
        unlocked_grade=ctx.unlocked_grade,
        updated_at_by_topic=ctx.updated_at_by_topic,
        now=now,
    )
    chosen_id = ranked[0]
    chosen_band = ctx.band_by_topic[chosen_id]
    return NextTopicSelection(
        topic_id=chosen_id,
        band=chosen_band,
        p_mastery=ctx.p_mastery_by_topic[chosen_id],
        effective_p_mastery=effective_p_mastery_of(chosen_id),
        difficulty=_DIFFICULTY_BY_BAND[chosen_band],
        is_fallback=is_fallback,
        updated_at=ctx.updated_at_by_topic.get(chosen_id),
        grade=ctx.grade_by_topic.get(chosen_id),
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
    # 027-learner-ui-redesign, gap-closing pass: the Dashboard's "why
    # this question?" disclosure names the prerequisite that makes
    # `next_topic` the pick (mockup: "You've mastered X, its
    # prerequisite"). Direct `prereqs_by_topic` lookup already built by
    # `_load_topic_ranking_context` -- not the recursive unmastered-gap
    # walk `next_step.py` does, since by construction `next_topic`'s
    # own direct prerequisites are already satisfied. When there are
    # several, the most recently mastered one is named (PR #99 review:
    # picking by path order was arbitrary and could name a prerequisite
    # unrelated to why this topic just became eligible) -- the one that
    # most recently crossed into mastered is the one that plausibly just
    # unlocked `next_topic`. `None` when `next_topic` has no prerequisite
    # (e.g. the first topic in the path) or when this is a fallback pick
    # (no "next step" framing applies there).
    next_topic_prerequisite_display_name: str | None = None


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
    now = datetime.datetime.now(datetime.UTC)
    ranked, is_fallback = rank_eligible_topics(
        ctx.topic_ids_in_order,
        band_by_topic=ctx.band_by_topic,
        p_mastery_by_topic=ctx.p_mastery_by_topic,
        prereqs_by_topic=ctx.prereqs_by_topic,
        grade_by_topic=ctx.grade_by_topic,
        unlocked_grade=ctx.unlocked_grade,
        updated_at_by_topic=ctx.updated_at_by_topic,
        now=now,
    )

    def to_entry(topic_id: str) -> TopicPreviewEntry:
        return TopicPreviewEntry(
            topic_id=topic_id,
            display_name=ctx.display_name_by_topic[topic_id],
            band=ctx.band_by_topic[topic_id],
            p_mastery=ctx.p_mastery_by_topic[topic_id],
        )

    next_topic_id = ranked[0]
    prerequisite_display_name: str | None = None
    if not is_fallback:
        prereq_ids = ctx.prereqs_by_topic.get(next_topic_id, [])
        if prereq_ids:
            never_updated = datetime.datetime.min.replace(tzinfo=datetime.UTC)
            immediate_prereq = max(
                prereq_ids,
                key=lambda p: ctx.updated_at_by_topic.get(p, never_updated),
            )
            prerequisite_display_name = ctx.display_name_by_topic.get(immediate_prereq)

    return TopicPriorityPreview(
        subject_id=subject_id,
        next_topic=to_entry(next_topic_id),
        upcoming_topics=[to_entry(t) for t in ranked[1 : 1 + upcoming_count]],
        is_fallback=is_fallback,
        next_topic_prerequisite_display_name=prerequisite_display_name,
    )


@dataclass(frozen=True)
class NextQuestionResult:
    selection: NextTopicSelection
    question_type: QuestionType
    draft: GeneratedQuestionDraft
    image_url: str | None = None
    image_alt_text: str | None = None
    cache_outcome: CacheOutcome = field(default_factory=lambda: CacheOutcome(hit=False))


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
    subject = db.get(Subject, subject_id)
    question_type = preferred_question_type(topic)
    recent_stems = recent_stems_for_topic(
        db,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=selection.topic_id,
        limit=dedup_lookback,
    )

    image_url: str | None = None
    image_alt_text: str | None = None
    if topic.image_asset is not None:
        image_url = content_image_url(subject_id, topic.image_asset["filename"])
        image_alt_text = topic.image_asset["alt_text"]

    draft: GeneratedQuestionDraft | None = None
    cache_outcome = CacheOutcome(hit=False)
    for _ in range(max_dedup_attempts):
        draft, cache_outcome = await get_or_generate_question(
            db,
            subject_id=subject_id,
            topic_id=selection.topic_id,
            difficulty=selection.difficulty,
            content_version=subject.content_version,
            generation_prompt_version=GENERATION_PROMPT_VERSION,
            avoid_stems=recent_stems,
            generate_fn=lambda: generate_question(
                topic_display_name=topic.display_name,
                skill_summary=skill_summary(topic),
                difficulty=selection.difficulty,
                difficulty_guidance=difficulty_guidance(topic, selection.difficulty),
                question_type=question_type,
                session_service=session_service,
                avoid_stems=recent_stems,
                image_alt_text=image_alt_text,
            ),
        )
        if not is_near_duplicate(draft.stem, recent_stems):
            break

    return NextQuestionResult(
        selection=selection,
        question_type=question_type,
        draft=draft,
        image_url=image_url,
        image_alt_text=image_alt_text,
        cache_outcome=cache_outcome,
    )

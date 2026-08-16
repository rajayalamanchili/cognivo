"""Diagnostic Agent (FR-003, FR-006's difficulty mapping).

Selects exactly one placement question per entry-level topic --
deterministic topic selection (Constitution Principle I: topic
selection is never an LLM guessing which topics need placement),
delegating only the actual question content generation to the
Assessment-Generation Agent. Every entry-level topic has no
`MasteryState` row yet ("unknown", FR-005) at placement time, and
FR-006's difficulty mapping sends "unknown" topics to "easy" -- so every
placement question is requested at "easy" difficulty, unconditionally.
"""

from dataclasses import dataclass

from google.adk.sessions import BaseSessionService

from src.agents.assessment_gen.agent import GeneratedQuestionDraft, generate_question
from src.models.enums import DifficultyBand, QuestionType
from src.models.topic import Topic


@dataclass(frozen=True)
class PlacementQuestion:
    topic_id: str
    question_type: QuestionType
    draft: GeneratedQuestionDraft


def preferred_question_type(topic: Topic) -> QuestionType:
    """First entry in the content artifact's `preferred_question_types`
    (backend/content/<subject>/subject.yaml) -- a content-artifact-owned
    choice, never an engine-side subject conditional (Principle III)."""
    skill = (topic.skill_definition or {}).get("skill") or {}
    preferred = skill.get("preferred_question_types") or []
    if preferred:
        return QuestionType(preferred[0])
    return QuestionType.MULTIPLE_CHOICE


def difficulty_guidance(topic: Topic, difficulty: DifficultyBand) -> str:
    calibration = (topic.skill_definition or {}).get("difficulty_calibration") or {}
    return calibration.get(difficulty.value, "")


def _skill_summary(topic: Topic) -> str:
    skill = (topic.skill_definition or {}).get("skill") or {}
    return skill.get("summary", "")


async def generate_placement_questions(
    entry_level_topics: list[Topic],
    *,
    session_service: BaseSessionService,
) -> list[PlacementQuestion]:
    """One question per entry-level topic, always at "easy" difficulty."""
    questions: list[PlacementQuestion] = []
    for topic in entry_level_topics:
        question_type = preferred_question_type(topic)
        draft = await generate_question(
            topic_display_name=topic.display_name,
            skill_summary=_skill_summary(topic),
            difficulty=DifficultyBand.EASY,
            difficulty_guidance=difficulty_guidance(topic, DifficultyBand.EASY),
            question_type=question_type,
            session_service=session_service,
        )
        questions.append(
            PlacementQuestion(topic_id=topic.topic_id, question_type=question_type, draft=draft)
        )
    return questions

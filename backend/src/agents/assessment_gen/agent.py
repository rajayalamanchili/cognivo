"""Assessment-Generation Agent (FR-007, Constitution Principle II).

An ADK sub-agent, LiteLlm-wrapped (Claude Sonnet default per
research.md §2, provider kept a runtime config value), that generates
one structured question AND its own answer key together, in a single
call -- never a question shown before its rubric exists. Internal-
consistency validation happens here, before the caller ever persists a
`GeneratedQuestion` row with `shown_at` set: a question whose
marked-correct option isn't among its listed options MUST NOT reach a
learner.
"""

import json
import math
import os
from collections.abc import Sequence
from typing import Literal

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types
from pydantic import BaseModel, Field

from src.models.enums import DifficultyBand, QuestionType

APP_NAME = "cognivo-assessment-gen"

# Bumped whenever _INSTRUCTION_TEMPLATE's instructional content changes
# (spec 014 FR-002/FR-008's CI-enforced version-bump requirement) -- a
# code constant, not a database row, same as GRADING_LOGIC_VERSION.
GENERATION_PROMPT_VERSION = "v1"


class GenerationValidationError(Exception):
    """Raised when the model's draft fails internal-consistency validation
    (FR-007) after exhausting all retry attempts."""


class RubricCriterion(BaseModel):
    """One weighted grading criterion within a free-text question's rubric
    (data-model.md's `answer_key.criteria` shape, spec 007 FR-002)."""

    description: str = Field(min_length=1)
    weight: float = Field(gt=0)


class GeneratedQuestionDraft(BaseModel):
    """The Assessment-Generation Agent's structured output shape.

    Flat by design (rather than a discriminated union) so the LLM has a
    single, unambiguous schema to fill regardless of `question_type` --
    the fields irrelevant to the requested type are simply left null,
    then checked by `_validate_draft` below.
    """

    question_type: Literal["multiple_choice", "numeric", "free_text"]
    stem: str = Field(min_length=1)
    options: list[str] | None = Field(
        default=None, description="Required for multiple_choice; null for numeric/free_text."
    )
    correct_index: int | None = Field(
        default=None,
        description="0-based index into options. Required for multiple_choice.",
    )
    correct_value: float | None = Field(default=None, description="Required for numeric.")
    tolerance: float | None = Field(
        default=None,
        description=(
            "Relative tolerance for numeric, e.g. 0.005 for +/-0.5%. Required for numeric."
        ),
    )
    rubric_criteria: list[RubricCriterion] | None = Field(
        default=None,
        description=(
            "Required for free_text: 1-4 grading criteria whose weights sum to 1.0. "
            "Null for multiple_choice/numeric."
        ),
    )


_INSTRUCTION_TEMPLATE = """\
You write exactly one assessment question for a learning platform, on the \
topic "{topic_display_name}".

Topic skill: {skill_summary}

Requested question type: {question_type}
Requested difficulty: {difficulty}
Difficulty guidance for this topic/difficulty: {difficulty_guidance}
{image_section}
Rules:
- Generate a brand-new question. Do not reuse a well-known textbook example verbatim.
- If question_type is "multiple_choice": provide exactly 4 plausible options in \
"options", and "correct_index" as the 0-based index of the single correct option. \
Leave "correct_value" and "tolerance" null.
- If question_type is "numeric": provide "correct_value" as the exact correct \
numeric answer, and "tolerance" as a small positive relative tolerance (e.g. 0.005 \
for +/-0.5%) appropriate for this question's precision. Leave "options" and \
"correct_index" null.
- If question_type is "free_text": ask a short-answer question requiring a \
sentence or two of explanation, not a single word or number. Provide \
"rubric_criteria" as a list of 1-4 grading criteria, each with a "description" \
(a specific, checkable thing a correct answer must demonstrate -- never vague) \
and a "weight" (a positive number; all weights in the list MUST sum to 1.0). \
Leave "options", "correct_index", "correct_value", and "tolerance" null.
- The question must be answerable using only the stated topic skill -- no outside \
context needed.
{avoid_section}
Respond with ONLY the structured output matching the required schema.
"""


def _build_instruction(
    *,
    topic_display_name: str,
    skill_summary: str,
    question_type: QuestionType,
    difficulty: DifficultyBand,
    difficulty_guidance: str,
    avoid_stems: Sequence[str],
    image_alt_text: str | None = None,
) -> str:
    avoid_section = ""
    if avoid_stems:
        joined = "\n".join(f'- "{stem}"' for stem in avoid_stems)
        avoid_section = (
            "\nDo not generate a question that duplicates or closely resembles any "
            f"of these previously used questions on this topic:\n{joined}\n"
        )
    image_section = ""
    if image_alt_text:
        image_section = (
            "\nThis question will be displayed to the learner together with an "
            f"image (you will not see the image itself). Description of the image: "
            f"{image_alt_text}\nWrite the question stem so it reads naturally "
            'alongside that image (e.g. referring to "the diagram below" or "the '
            'graph shown"), not a generic stem that merely happens to have an '
            "unrelated image attached.\n"
        )
    return _INSTRUCTION_TEMPLATE.format(
        topic_display_name=topic_display_name,
        skill_summary=skill_summary,
        question_type=question_type.value,
        difficulty=difficulty.value,
        difficulty_guidance=difficulty_guidance,
        avoid_section=avoid_section,
        image_section=image_section,
    )


def _build_agent(model_name: str, instruction: str) -> LlmAgent:
    return LlmAgent(
        name="assessment_generation_agent",
        model=LiteLlm(model=model_name),
        instruction=instruction,
        output_schema=GeneratedQuestionDraft,
    )


def _validate_draft(draft: GeneratedQuestionDraft, question_type: QuestionType) -> None:
    if draft.question_type != question_type.value:
        raise GenerationValidationError(
            f"requested question_type={question_type.value!r} but model returned "
            f"{draft.question_type!r}"
        )
    if question_type == QuestionType.MULTIPLE_CHOICE:
        if not draft.options or len(draft.options) < 2:
            raise GenerationValidationError("multiple_choice question needs >=2 options")
        if draft.correct_index is None or not (0 <= draft.correct_index < len(draft.options)):
            raise GenerationValidationError(
                "multiple_choice answer_key's correct_index is not among options (FR-007)"
            )
    elif question_type == QuestionType.NUMERIC:
        if draft.correct_value is None:
            raise GenerationValidationError("numeric question missing correct_value")
        if draft.tolerance is None or draft.tolerance <= 0:
            raise GenerationValidationError("numeric question missing a positive tolerance")
    elif question_type == QuestionType.FREE_TEXT:
        if not draft.rubric_criteria:
            raise GenerationValidationError(
                "free_text question needs >=1 rubric criterion (spec 007 FR-002)"
            )
        total_weight = sum(c.weight for c in draft.rubric_criteria)
        if not math.isclose(total_weight, 1.0, rel_tol=0.01):
            raise GenerationValidationError(
                f"free_text rubric_criteria weights must sum to ~1.0, got {total_weight}"
            )


async def _run_agent_once(agent: LlmAgent, session_service: BaseSessionService) -> str:
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    user_id = "assessment-gen-service"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=[types.Part(text="Generate the question.")])

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if final_text is None:
        raise GenerationValidationError("model produced no final response")
    return final_text


async def generate_question(
    *,
    topic_display_name: str,
    skill_summary: str,
    difficulty: DifficultyBand,
    difficulty_guidance: str,
    question_type: QuestionType,
    session_service: BaseSessionService,
    avoid_stems: Sequence[str] = (),
    model_name: str | None = None,
    max_attempts: int = 3,
    image_alt_text: str | None = None,
) -> GeneratedQuestionDraft:
    """Generates and validates one structured question (FR-007).

    Retries up to `max_attempts` times on a validation failure -- an
    invalid draft (e.g. `correct_index` outside `options`) MUST NOT be
    returned to the caller, since the caller sets `shown_at` on the
    assumption this function only ever returns a valid question.

    `image_alt_text`, when set, tells the model an image will be shown
    alongside this question (spec 003 FR-004, research.md §3) -- the
    model never sees the image itself, only its alt-text description,
    and is asked to phrase the stem so it reads naturally next to it.
    The image reference itself (URL + alt text) is attached by the
    caller from the topic's own content-artifact data, never by the
    model.
    """
    resolved_model_name = model_name or os.environ["ASSESSMENT_GEN_MODEL"]
    instruction = _build_instruction(
        topic_display_name=topic_display_name,
        skill_summary=skill_summary,
        question_type=question_type,
        difficulty=difficulty,
        difficulty_guidance=difficulty_guidance,
        avoid_stems=avoid_stems,
        image_alt_text=image_alt_text,
    )
    agent = _build_agent(resolved_model_name, instruction)

    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            raw_text = await _run_agent_once(agent, session_service)
            draft = GeneratedQuestionDraft.model_validate_json(raw_text)
            _validate_draft(draft, question_type)
            return draft
        except (GenerationValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise GenerationValidationError(
        f"failed to generate a valid {question_type.value} question after "
        f"{max_attempts} attempts: {last_error}"
    )


def draft_to_answer_key(draft: GeneratedQuestionDraft) -> dict:
    """Converts a validated draft into the `answer_key` shape
    `services/mastery/grading.py` expects (data-model.md's
    GeneratedQuestion.answer_key)."""
    if draft.question_type == "multiple_choice":
        return {"correct_index": draft.correct_index}
    if draft.question_type == "free_text":
        return {
            "criteria": [
                {"description": c.description, "weight": c.weight} for c in draft.rubric_criteria
            ]
        }
    return {"value": draft.correct_value, "tolerance": draft.tolerance}

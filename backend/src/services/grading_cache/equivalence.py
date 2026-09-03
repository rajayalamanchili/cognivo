"""Cheap rubric-criteria re-classification gating a grading-cache
candidate before it's served as a hit (spec 015 FR-003/FR-009,
Clarifications 2026-09-02).

`get_or_grade_answer` (cache.py) found, against Milestone 6's real
ground-truth grading eval set, that embedding-distance thresholding
alone cannot separate negation/opposite-meaning answers from genuine
paraphrases -- the closest false-positive pair measured a smaller
distance than genuine true-positive pairs, so no threshold value could
work. This module is the fix: it never compares the new answer against
the original learner's raw answer text (`grading_response_cache`
deliberately stores none, FR-009) -- instead it classifies the new
answer against the SAME rubric criteria a real grading call would use
(a lightweight model call, not a substitute for the full Grading Agent
call) and checks whether that classification's `criteria_met` pattern
matches the candidate row's already-stored pattern exactly. Only on a
match does the caller serve the candidate's cached grade.

Uses the same ADK `LlmAgent` + `LiteLlm` + cheap-model pattern
`grading_client/moderation.py` already establishes for this project's
other lightweight pre/post-grading classification step.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types
from pydantic import BaseModel

APP_NAME = "cognivo-grading-cache-equivalence"

# Bumped whenever _INSTRUCTION's instructional content changes (spec 014
# FR-002/FR-008's CI-enforced version-bump requirement) -- a code
# constant, not a database row, same as GRADING_LOGIC_VERSION.
EQUIVALENCE_INSTRUCTION_VERSION = "v1"

_INSTRUCTION = """\
You are re-checking a learner's free-text answer against a rubric, for \
a learning platform's grading cache. For each rubric criterion listed, \
decide whether the learner's answer satisfies it.

If the learner's answer is blank, whitespace-only, off-topic, or does \
not substantively attempt to address the question, no criteria are \
met -- do not mark a criterion met just because the question or rubric \
text near it happens to share words with the criterion's description.

Respond with ONLY the structured output matching the required schema: \
one boolean per criterion, in the same order the criteria are listed.
"""


class _CriteriaClassification(BaseModel):
    met: list[bool]


def _build_agent(model_name: str) -> LlmAgent:
    return LlmAgent(
        name="grading_cache_equivalence_agent",
        model=LiteLlm(model=model_name),
        instruction=_INSTRUCTION,
        output_schema=_CriteriaClassification,
    )


def _build_prompt(*, question_stem: str, rubric_criteria: list[dict], learner_answer: str) -> str:
    criteria_lines = "\n".join(
        f"{i + 1}. {criterion['description']}" for i, criterion in enumerate(rubric_criteria)
    )
    return (
        f"Question: {question_stem}\n\nRubric criteria (in order):\n{criteria_lines}"
        f"\n\nLearner answer: {learner_answer}"
    )


class ClassificationFailedError(Exception):
    """The classifier returned no response, or a response that didn't
    match `rubric_criteria`'s shape."""


async def classify_criteria_met(
    *,
    question_stem: str,
    rubric_criteria: list[dict],
    learner_answer: str,
    session_service: BaseSessionService,
    model_name: str | None = None,
) -> set[str]:
    """Cheaply classifies `learner_answer` against `rubric_criteria`,
    returning the set of criterion descriptions it satisfies. Raises
    `ClassificationFailedError` on no/malformed response -- the caller
    decides the fail-open behavior (`matches_cached_criteria_pattern`
    below treats it as no match; `scripts/validate_grading_cache_
    threshold.py` treats it as a hard validation failure)."""
    resolved_model_name = model_name or os.environ.get(
        "GRADING_CACHE_EQUIVALENCE_MODEL", "anthropic/claude-haiku-4-5"
    )
    agent = _build_agent(resolved_model_name)
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    user_id = "grading-cache-equivalence-service"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    prompt = _build_prompt(
        question_stem=question_stem, rubric_criteria=rubric_criteria, learner_answer=learner_answer
    )
    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if final_text is None:
        raise ClassificationFailedError("no response from the equivalence classifier")

    classification = _CriteriaClassification.model_validate_json(final_text)
    if len(classification.met) != len(rubric_criteria):
        raise ClassificationFailedError(
            f"classifier returned {len(classification.met)} results for "
            f"{len(rubric_criteria)} criteria"
        )

    return {
        rubric_criteria[i]["description"]
        for i, met in enumerate(classification.met)
        if met
    }


async def matches_cached_criteria_pattern(
    *,
    question_stem: str,
    rubric_criteria: list[dict],
    learner_answer: str,
    cached_criteria_met: list[str],
    session_service: BaseSessionService,
    model_name: str | None = None,
) -> bool:
    """True if a cheap re-classification of `learner_answer` against
    `rubric_criteria` lands on the exact same `criteria_met` set the
    cached candidate row already has.

    Fails closed: a classification failure returns `False` (treated as
    no match, i.e. a cache miss) -- never risks serving a wrong cached
    grade because verification broke.
    """
    try:
        classified_met = await classify_criteria_met(
            question_stem=question_stem,
            rubric_criteria=rubric_criteria,
            learner_answer=learner_answer,
            session_service=session_service,
            model_name=model_name,
        )
    except ClassificationFailedError:
        return False
    return classified_met == set(cached_criteria_met)

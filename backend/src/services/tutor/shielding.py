"""Tutor Agent answer-shielding (spec 016 FR-001..FR-010).

When a learner asks the Tutor Agent something that would reveal the
final answer to a question they currently have open and unanswered
(practice, quiz -- learner-initiated or instructor-assigned -- or
placement), `determine_shielding` is what `tutor/session.py`'s
`prepare_message` calls to decide whether the Tutor Agent must respond
with a hint instead of a direct answer.

The open-question lookup (`find_open_questions`) is a plain, always-
reliable read against data this system already records -- no LLM
involved, so it never needs a fail-safe of its own. The
direct-or-paraphrase *match* decision (`_classify_match`) is the part
that can fail (a model call), and uses the same local, in-process
cheap-model classification shape `grading_cache/equivalence.py`
(spec 015) already establishes -- not a new agent boundary or A2A
service (Constitution Principle IV/VI): a genuinely different
classification problem, but the identical "cheap `LlmAgent` +
structured Pydantic output, version-constant tied to the instruction
text" pattern.
"""

import dataclasses
import os
import uuid
from collections.abc import Awaitable, Callable

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.generated_question import GeneratedQuestion
from src.models.quiz_assignment import QuizAssignment
from src.models.quiz_assignment_target import QuizAssignmentTarget

APP_NAME = "cognivo-tutor-shielding"

# Bumped whenever _MATCH_INSTRUCTION's instructional content changes
# (spec 014 FR-002/FR-008's CI-enforced version-bump requirement) -- a
# code constant, not a database row, same as
# EQUIVALENCE_INSTRUCTION_VERSION/GRADING_LOGIC_VERSION.
SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION = "v1"

_MATCH_INSTRUCTION = """\
You are checking whether a learner's message in a tutoring chat is asking \
for the final answer to a specific question they have open and have not \
yet answered, for a learning platform's answer-shielding safeguard.

Answer "true" only when the learner's message restates the open question's \
own content -- exactly or as a recognizable paraphrase -- or directly asks \
to have that open question solved or its answer stated (for example "what's \
the answer to this", "just solve it for me", or a close paraphrase of the \
open question itself).

Answer "false" when the learner's message is a general conceptual question \
that does not itself ask for or restate the open question's specific \
content -- even if it happens to be about the same general topic. A \
same-topic question that could be answered without giving away the open \
question's specific answer must not be treated as a match.
"""


class _MatchClassification(BaseModel):
    matches: bool


def _build_agent(model_name: str) -> LlmAgent:
    return LlmAgent(
        name="tutor_shielding_match_agent",
        model=LiteLlm(model=model_name),
        instruction=_MATCH_INSTRUCTION,
        output_schema=_MatchClassification,
    )


def _build_prompt(*, open_question_stem: str, tutor_question: str) -> str:
    return (
        f"Open, unanswered question: {open_question_stem}\n\n"
        f"Learner's tutoring-chat message: {tutor_question}"
    )


class ClassificationFailedError(Exception):
    """The classifier returned no response, or a malformed one."""


async def classify_match(
    *,
    open_question_stem: str,
    tutor_question: str,
    session_service: BaseSessionService,
    model_name: str | None = None,
) -> bool:
    """Raises `ClassificationFailedError` on no/malformed response --
    `determine_shielding` below treats any exception from its injected
    `match_fn` (this function, bound via `functools.partial` at the
    real call site, mirroring `grading_cache/cache.py`'s `verify_fn`
    injection so unit tests never need real ADK/LLM machinery to
    exercise the lookup/tie-break/fail-safe logic) as FR-010's
    inconclusive-determination case."""
    resolved_model_name = model_name or os.environ.get(
        "TUTOR_SHIELDING_CLASSIFICATION_MODEL", "anthropic/claude-haiku-4-5"
    )
    agent = _build_agent(resolved_model_name)
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    user_id = "tutor-shielding-service"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    prompt = _build_prompt(open_question_stem=open_question_stem, tutor_question=tutor_question)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if final_text is None:
        raise ClassificationFailedError("no response from the shielding-match classifier")

    return _MatchClassification.model_validate_json(final_text).matches


def _is_answered(db: Session, *, question_id: uuid.UUID) -> bool:
    """Mirrors `api/routes/questions.py`'s `_already_answered()` exactly
    (FR-001) -- kept as its own copy here rather than imported, since
    that function lives in a route module, not a reusable service."""
    return (
        db.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question_id,
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .first()
        is not None
    )


def _is_assignment_cancelled(db: Session, *, quiz_session_id: uuid.UUID) -> bool:
    """FR-006's "session/attempt ended" branch, corrected during
    `/speckit-analyze` (finding C1): `quiz_assignment/assignment.py`'s
    `cancel_assignment()` never transitions the underlying
    `QuizSession.status` -- it stays whatever it already was
    (`IN_PROGRESS`, mid-attempt) forever, so cancellation must be
    checked here explicitly rather than inferred from session status."""
    return (
        db.query(QuizAssignment)
        .join(
            QuizAssignmentTarget,
            QuizAssignmentTarget.assignment_id == QuizAssignment.assignment_id,
        )
        .filter(
            QuizAssignmentTarget.quiz_session_id == quiz_session_id,
            QuizAssignment.cancelled_at.isnot(None),
        )
        .first()
        is not None
    )


def find_open_questions(
    db: Session, *, learner_id: uuid.UUID, subject_id: str
) -> list[GeneratedQuestion]:
    """FR-001/FR-002: every question currently displayed to this learner
    in this subject with no submitted answer yet. Practice, quiz
    (learner-initiated or instructor-assigned), and placement all set
    `shown_at` on this same `GeneratedQuestion` table, so no
    per-context branching is needed here (Constitution Principle III).
    """
    candidates = (
        db.query(GeneratedQuestion)
        .filter(
            GeneratedQuestion.learner_id == learner_id,
            GeneratedQuestion.subject_id == subject_id,
            GeneratedQuestion.shown_at.isnot(None),
        )
        .all()
    )
    return [
        question
        for question in candidates
        if not _is_answered(db, question_id=question.question_id)
        and not (
            question.quiz_session_id is not None
            and _is_assignment_cancelled(db, quiz_session_id=question.quiz_session_id)
        )
    ]


@dataclasses.dataclass(frozen=True)
class ShieldingDecision:
    shielded: bool
    # Only set on a confirmed content match (data-model.md's invariant)
    # -- stays None for the FR-010 inconclusive path even though a
    # candidate stem was still used for open_question_stem below, since
    # attributing the shield to a specific question we're not actually
    # confident matches would misrepresent the audit trail.
    shielded_question_id: uuid.UUID | None
    # Populated whenever shielded is True (confirmed match or FR-010
    # fail-safe) -- the only information about the open question ever
    # sent to tutor-agent/ (research.md decision 3): never its
    # answer_key.
    open_question_stem: str | None
    open_question_topic_id: str | None


async def determine_shielding(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    tutor_question: str,
    match_fn: Callable[..., Awaitable[bool]],
) -> ShieldingDecision:
    """The single entry point `tutor/session.py`'s `prepare_message`
    calls. `match_fn(open_question_stem=..., tutor_question=...)` is
    injected by the caller (real call sites bind `classify_match` via
    `functools.partial(classify_match, session_service=...)`) rather
    than called directly here, so this function's lookup/tie-break/
    fail-safe logic is unit-testable with a plain fake coroutine --
    no ADK/LLM machinery needed (mirrors `grading_cache/cache.py`'s
    `verify_fn` injection).

    Any exception `match_fn` raises defaults to shielding (FR-010) --
    never risks revealing a final answer because the determination
    itself broke, rather than because it genuinely found no match.
    """
    open_questions = find_open_questions(db, learner_id=learner_id, subject_id=subject_id)
    if not open_questions:
        return ShieldingDecision(False, None, None, None)

    most_recent = max(open_questions, key=lambda question: question.shown_at)

    matched: GeneratedQuestion | None = None
    inconclusive = False
    for question in open_questions:
        try:
            is_match = await match_fn(
                open_question_stem=question.stem, tutor_question=tutor_question
            )
        except Exception:
            inconclusive = True
            continue
        if is_match and (matched is None or question.shown_at > matched.shown_at):
            matched = question

    if matched is not None:
        return ShieldingDecision(True, matched.question_id, matched.stem, matched.topic_id)
    if inconclusive:
        return ShieldingDecision(True, None, most_recent.stem, most_recent.topic_id)
    return ShieldingDecision(False, None, None, None)

#!/usr/bin/env python3
"""Offline batch-eval: re-validates a sample of previously generated
questions for internal-consistency (SC-003 regression testing).

Distinct from `tests/unit/test_question_validation.py` (T042): that test
exercises `_validate_draft` against hand-written drafts at display time.
This script re-runs the exact same validation function against
`GeneratedQuestion` rows already persisted to Postgres, so a change that
weakens `_validate_draft` (or a bug in `draft_to_answer_key`'s
reconstruction) shows up as a regression against real generated content,
not just fixtures.

Reuses `_validate_draft` rather than reimplementing the check -- one
validation function, exercised at both generation time (FR-007) and
regression time.
"""

import argparse
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.sessions import InMemorySessionService  # noqa: E402

from src.agents.assessment_gen.agent import (  # noqa: E402
    GeneratedQuestionDraft,
    GenerationValidationError,
    generate_question,
    _validate_draft,
)
from src.db import get_sessionmaker  # noqa: E402
from src.models.enums import DifficultyBand, QuestionType  # noqa: E402
from src.models.generated_question import GeneratedQuestion  # noqa: E402
from src.services.content_artifact.loader import load_content_artifact_file  # noqa: E402

DEFAULT_SAMPLE_SIZE = 100
DEFAULT_FRESH_SAMPLE_SIZE_PER_SUBJECT = 3
CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def _draft_from_row(question: GeneratedQuestion) -> GeneratedQuestionDraft:
    """Reconstructs the draft shape `_validate_draft` expects from a
    persisted row's `answer_key` (the inverse of `draft_to_answer_key`)."""
    answer_key = question.answer_key
    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        correct_index = answer_key.get("correct_index")
        correct_value = None
        tolerance = None
    else:
        correct_index = None
        correct_value = answer_key.get("value")
        tolerance = answer_key.get("tolerance")

    return GeneratedQuestionDraft(
        question_type=question.question_type.value,
        stem=question.stem or " ",  # stem is min_length=1; blank is itself a failure below
        options=question.options,
        correct_index=correct_index,
        correct_value=correct_value,
        tolerance=tolerance,
    )


class EvalFailure:
    def __init__(self, question_id, reason: str) -> None:
        self.question_id = question_id
        self.reason = reason


def evaluate_sample(
    questions: list[GeneratedQuestion],
) -> tuple[int, list[EvalFailure]]:
    failures: list[EvalFailure] = []
    for question in questions:
        try:
            if not question.stem or not question.stem.strip():
                raise GenerationValidationError("stem is blank")
            draft = _draft_from_row(question)
            _validate_draft(draft, question.question_type)
        except GenerationValidationError as exc:
            failures.append(EvalFailure(question.question_id, str(exc)))
    return len(questions), failures


async def _generate_and_validate_one(topic, session_service: InMemorySessionService) -> None:
    """Raises `GenerationValidationError` (a bad draft) or lets any other
    exception (a failed generation call -- missing credentials, model/
    network error) propagate -- both are failures to the caller, per
    FR-007's fail-closed requirement; neither is silently swallowed."""
    skill = topic.skill_definition or {}
    preferred_types = skill.get("preferred_question_types") or ["multiple_choice"]
    question_type = QuestionType(preferred_types[0])
    difficulty = DifficultyBand.MEDIUM
    guidance = (topic.difficulty_calibration or {}).get(difficulty.value, "")

    draft = await generate_question(
        topic_display_name=topic.display_name,
        skill_summary=skill.get("summary", ""),
        difficulty=difficulty,
        difficulty_guidance=guidance,
        question_type=question_type,
        session_service=session_service,
    )
    _validate_draft(draft, question_type)


async def run_fresh_sample(
    sample_size_per_subject: int = DEFAULT_FRESH_SAMPLE_SIZE_PER_SUBJECT,
) -> tuple[int, list[EvalFailure]]:
    """FR-005's stateless-CI-compatible mode (research.md §5): generates a
    small fresh sample via the real Assessment-Generation path across
    this project's content artifacts on disk -- no database, no
    dependency on any previously-persisted `GeneratedQuestion` history."""
    session_service = InMemorySessionService()
    total = 0
    failures: list[EvalFailure] = []
    for subject_path in sorted(CONTENT_DIR.glob("*/subject.yaml")):
        artifact = load_content_artifact_file(subject_path)
        for topic in artifact.topics[:sample_size_per_subject]:
            total += 1
            question_id = f"{artifact.subject_id}:{topic.topic_id}"
            try:
                await _generate_and_validate_one(topic, session_service)
            except GenerationValidationError as exc:
                failures.append(EvalFailure(question_id, str(exc)))
            except Exception as exc:  # noqa: BLE001 -- fail-closed (FR-007), see docstring above
                failures.append(EvalFailure(question_id, f"generation call failed: {exc}"))
    return total, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-id", default=None, help="Restrict the sample to one subject.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help=(
            f"Max questions to re-validate (default {DEFAULT_SAMPLE_SIZE} for the default "
            f"DB-sampling mode, {DEFAULT_FRESH_SAMPLE_SIZE_PER_SUBJECT} per subject for --fresh)."
        ),
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for sampling.")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "Generate a fresh sample via the real Assessment-Generation path instead of "
            "sampling persisted GeneratedQuestion rows -- for a stateless CI database with "
            "no accumulated history (research.md §5)."
        ),
    )
    args = parser.parse_args()

    if args.fresh:
        sample_size = args.sample_size or DEFAULT_FRESH_SAMPLE_SIZE_PER_SUBJECT
        try:
            total, failures = asyncio.run(run_fresh_sample(sample_size))
        except Exception as exc:  # noqa: BLE001 -- fail-closed (FR-007)
            print(f"FAIL: could not run the fresh Assessment-Generation eval: {exc}")
            return 1
    else:
        sample_size = args.sample_size or DEFAULT_SAMPLE_SIZE
        session_local = get_sessionmaker()
        with session_local() as db:
            query = db.query(GeneratedQuestion)
            if args.subject_id:
                query = query.filter(GeneratedQuestion.subject_id == args.subject_id)
            all_questions = query.all()

        rng = random.Random(args.seed)
        sample = (
            rng.sample(all_questions, sample_size)
            if len(all_questions) > sample_size
            else all_questions
        )
        total, failures = evaluate_sample(sample)

    passed = total - len(failures)
    print(f"batch_eval_questions: {passed}/{total} passed internal-consistency re-validation")
    for failure in failures:
        print(f"  FAIL question_id={failure.question_id}: {failure.reason}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

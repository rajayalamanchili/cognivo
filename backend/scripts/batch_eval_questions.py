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
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.assessment_gen.agent import (  # noqa: E402
    GeneratedQuestionDraft,
    GenerationValidationError,
    _validate_draft,
)
from src.db import get_sessionmaker  # noqa: E402
from src.models.enums import QuestionType  # noqa: E402
from src.models.generated_question import GeneratedQuestion  # noqa: E402

DEFAULT_SAMPLE_SIZE = 100


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-id", default=None, help="Restrict the sample to one subject.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help=f"Max questions to re-validate (default {DEFAULT_SAMPLE_SIZE}).",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for sampling.")
    args = parser.parse_args()

    session_local = get_sessionmaker()
    with session_local() as db:
        query = db.query(GeneratedQuestion)
        if args.subject_id:
            query = query.filter(GeneratedQuestion.subject_id == args.subject_id)
        all_questions = query.all()

    rng = random.Random(args.seed)
    sample = (
        rng.sample(all_questions, args.sample_size)
        if len(all_questions) > args.sample_size
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

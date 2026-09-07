"""Starting-grade determination (spec 017 FR-003, research.md Decision 3).

A pure function, deliberately DB-free -- Constitution Principle I
requires the mastery model's decisions be deterministic and
inspectable, never an LLM's impression of a conversation. Reused
unmodified for User Story 3's interim "currently-assessed level" check
(research.md Decision 4): callers there simply pass a partial
`correct_by_grade` covering only the questions answered so far in the
placement session.
"""


def determine_starting_grade(correct_by_grade: dict[int, bool], declared_grades: list[int]) -> int:
    """The highest grade G such that every declared grade from the
    lowest up through G was answered correctly, contiguously from the
    lowest declared grade. A grade missing from `correct_by_grade`
    (unanswered or skipped) counts as not-yet-correct, same as an
    explicit `False`. Floors to the lowest declared grade if even that
    one isn't a correct answer -- a learner is never placed below a
    subject's own floor.
    """
    if not declared_grades:
        raise ValueError("declared_grades must be non-empty")

    ordered_grades = sorted(declared_grades)
    starting_grade = ordered_grades[0]
    for grade in ordered_grades:
        if not correct_by_grade.get(grade):
            break
        starting_grade = grade
    return starting_grade

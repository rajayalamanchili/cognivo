"""Unit tests: `determine_starting_grade` (spec 017 FR-003/SC-001,
research.md Decision 3). Pure function, no DB -- directly satisfies
SC-001's determinism requirement as a unit test, same pattern
`test_mastery_bkt.py` already uses for the BKT update.
"""

from src.services.placement.starting_grade import determine_starting_grade


def test_all_correct_reaches_the_highest_declared_grade():
    assert (
        determine_starting_grade({6: True, 7: True, 8: True}, declared_grades=[6, 7, 8]) == 8
    )


def test_gap_caps_the_result_at_the_grade_below_the_first_miss():
    assert (
        determine_starting_grade({6: True, 7: False, 8: True}, declared_grades=[6, 7, 8]) == 6
    )


def test_zero_correct_floors_to_the_lowest_declared_grade():
    assert determine_starting_grade({}, declared_grades=[6, 7, 8]) == 6
    assert (
        determine_starting_grade({6: False, 7: False, 8: False}, declared_grades=[6, 7, 8]) == 6
    )


def test_partial_interim_input_treats_unanswered_grades_as_not_yet_correct():
    """Decision 4: User Story 3's skip-eligibility check reuses this
    same function against only the grades answered so far in a
    placement session -- an unanswered higher grade must not be
    mistaken for a passed one."""
    assert determine_starting_grade({6: True}, declared_grades=[6, 7, 8]) == 6
    assert determine_starting_grade({6: True, 7: True}, declared_grades=[6, 7, 8]) == 7


def test_declared_grades_order_does_not_matter():
    assert (
        determine_starting_grade({6: True, 7: True, 8: False}, declared_grades=[8, 6, 7]) == 7
    )


def test_ten_repeated_calls_with_identical_input_are_byte_identical():
    correct_by_grade = {6: True, 7: True, 8: False}
    declared_grades = [6, 7, 8]

    results = {
        determine_starting_grade(correct_by_grade, declared_grades) for _ in range(10)
    }

    assert len(results) == 1

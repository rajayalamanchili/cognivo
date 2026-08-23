"""Unit test: assignment target-list resolution (research.md §4), T008.

Pure-function test, no DB -- `resolve_target_learner_ids` is fully
determined by the requested `learner_ids` (a subset or the literal
`"all"`) and the roster's currently-enrolled learner ids passed in by
the caller (`create_assignment` is the one that actually queries
`Enrollment`).
"""

import uuid

import pytest

from src.api.errors import UnprocessableError
from src.services.quiz_assignment.assignment import resolve_target_learner_ids

_LEARNER_A = uuid.uuid4()
_LEARNER_B = uuid.uuid4()
_LEARNER_C = uuid.uuid4()
_NOT_ENROLLED = uuid.uuid4()


def test_all_resolves_to_every_currently_enrolled_learner():
    resolved = resolve_target_learner_ids(
        "all", enrolled_learner_ids=[_LEARNER_A, _LEARNER_B, _LEARNER_C]
    )
    assert set(resolved) == {_LEARNER_A, _LEARNER_B, _LEARNER_C}


def test_subset_resolves_to_only_the_requested_and_enrolled_learners():
    resolved = resolve_target_learner_ids(
        [_LEARNER_A], enrolled_learner_ids=[_LEARNER_A, _LEARNER_B, _LEARNER_C]
    )
    assert resolved == [_LEARNER_A]


def test_subset_silently_drops_a_requested_learner_not_currently_enrolled():
    resolved = resolve_target_learner_ids(
        [_LEARNER_A, _NOT_ENROLLED], enrolled_learner_ids=[_LEARNER_A, _LEARNER_B]
    )
    assert resolved == [_LEARNER_A]


def test_subset_deduplicates_a_repeated_learner_id():
    resolved = resolve_target_learner_ids(
        [_LEARNER_A, _LEARNER_A], enrolled_learner_ids=[_LEARNER_A, _LEARNER_B]
    )
    assert resolved == [_LEARNER_A]


def test_empty_subset_raises_unprocessable():
    with pytest.raises(UnprocessableError):
        resolve_target_learner_ids([], enrolled_learner_ids=[_LEARNER_A])


def test_all_against_an_empty_roster_raises_unprocessable():
    with pytest.raises(UnprocessableError):
        resolve_target_learner_ids("all", enrolled_learner_ids=[])


def test_subset_entirely_not_enrolled_raises_unprocessable():
    with pytest.raises(UnprocessableError):
        resolve_target_learner_ids([_NOT_ENROLLED], enrolled_learner_ids=[_LEARNER_A])

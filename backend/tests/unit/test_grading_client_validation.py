"""Unit test: the Grading Agent's A2A response is validated against the
question's own rubric shape before acceptance (spec 007 FR-014,
contracts/api.md's validation gate) -- no DB/network dependency,
exercises `_validate_and_parse` directly.
"""

import json

import pytest

from src.services.grading_client.client import (
    SCORE_THRESHOLD,
    _InvalidGradingResponse,
    _validate_and_parse,
)

_RUBRIC = [
    {"description": "Correctly identifies the independent variable", "weight": 0.4},
    {"description": "Correctly identifies the dependent variable", "weight": 0.6},
]


def _valid_response(**overrides) -> str:
    payload = {
        "graduated_score": 1.0,
        "criteria_results": [
            {"description": "Correctly identifies the independent variable", "met": True},
            {"description": "Correctly identifies the dependent variable", "met": True},
        ],
        "grading_logic_version": "v1",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_valid_response_parses_and_thresholds_correctly():
    result = _validate_and_parse(_valid_response(graduated_score=0.9), _RUBRIC)
    assert result.correct is True
    assert result.graduated_score == 0.9
    assert result.criteria_met == [
        "Correctly identifies the independent variable",
        "Correctly identifies the dependent variable",
    ]
    assert result.criteria_missed == []
    assert result.grading_logic_version == "v1"


def test_score_exactly_at_threshold_is_correct():
    result = _validate_and_parse(_valid_response(graduated_score=SCORE_THRESHOLD), _RUBRIC)
    assert result.correct is True


def test_score_just_below_threshold_is_incorrect():
    result = _validate_and_parse(_valid_response(graduated_score=SCORE_THRESHOLD - 0.01), _RUBRIC)
    assert result.correct is False


def test_partial_criteria_split_into_met_and_missed():
    response = _valid_response(
        graduated_score=0.4,
        criteria_results=[
            {"description": "Correctly identifies the independent variable", "met": True},
            {"description": "Correctly identifies the dependent variable", "met": False},
        ],
    )
    result = _validate_and_parse(response, _RUBRIC)
    assert result.criteria_met == ["Correctly identifies the independent variable"]
    assert result.criteria_missed == ["Correctly identifies the dependent variable"]


def test_non_json_response_rejected():
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse("not json", _RUBRIC)


def test_out_of_range_score_rejected():
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse(_valid_response(graduated_score=1.5), _RUBRIC)


def test_missing_score_rejected():
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse(_valid_response(graduated_score=None), _RUBRIC)


def test_wrong_criteria_count_rejected():
    response = _valid_response(
        criteria_results=[
            {"description": "Correctly identifies the independent variable", "met": True}
        ]
    )
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse(response, _RUBRIC)


def test_mismatched_criteria_description_rejected():
    response = _valid_response(
        criteria_results=[
            {"description": "a totally different criterion", "met": True},
            {"description": "Correctly identifies the dependent variable", "met": True},
        ]
    )
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse(response, _RUBRIC)


def test_missing_grading_logic_version_rejected():
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse(_valid_response(grading_logic_version=""), _RUBRIC)

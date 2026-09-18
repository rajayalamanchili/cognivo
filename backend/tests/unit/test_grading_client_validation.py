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
    _validate_and_parse_stepwise,
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


# Spec 018 multi-step validation gate (contracts/api.md) -- exercises
# `_validate_and_parse_stepwise` directly.

_STEPS = [
    {
        "step_prompt": "Isolate the variable term on one side.",
        "criteria": [
            {"description": "Chooses to subtract 2 from both sides", "weight": 0.5},
            {"description": "Correctly computes 3x = 12", "weight": 0.5},
        ],
    },
    {
        "step_prompt": "Solve for x.",
        "criteria": [
            {"description": "Chooses to divide both sides by 3", "weight": 0.5},
            {"description": "Correctly computes x = 4", "weight": 0.5},
        ],
    },
]


def _step_result(index: int, *, all_met: bool) -> dict:
    return {
        "step_index": index,
        "criteria_results": [
            {"description": c["description"], "met": all_met} for c in _STEPS[index]["criteria"]
        ],
    }


def _all_correct_stepwise_response(**overrides) -> str:
    payload = {
        "graduated_score": 1.0,
        "first_diverging_step_index": None,
        "step_results": [_step_result(0, all_met=True), _step_result(1, all_met=True)],
        "grading_logic_version": "v1",
    }
    payload.update(overrides)
    return json.dumps(payload)


def _diverges_at_step_1_response(**overrides) -> str:
    # Step 1: correct method (first criterion met), computational slip
    # (second criterion missed) -- FR-005's distinguishing case.
    payload = {
        "graduated_score": 0.5,
        "first_diverging_step_index": 1,
        "step_results": [
            _step_result(0, all_met=True),
            {
                "step_index": 1,
                "criteria_results": [
                    {"description": "Chooses to divide both sides by 3", "met": True},
                    {"description": "Correctly computes x = 4", "met": False},
                ],
            },
        ],
        "grading_logic_version": "v1",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_well_formed_all_correct_stepwise_response_accepted():
    result = _validate_and_parse_stepwise(_all_correct_stepwise_response(), _STEPS)
    assert result.correct is True
    assert result.graduated_score == 1.0
    assert result.first_diverging_step_index is None
    assert [s.correct for s in result.step_results] == [True, True]


def test_well_formed_one_wrong_step_response_accepted():
    result = _validate_and_parse_stepwise(_diverges_at_step_1_response(), _STEPS)
    assert result.correct is False
    assert result.graduated_score == 0.5
    assert result.first_diverging_step_index == 1
    assert len(result.step_results) == 2
    assert result.step_results[0].correct is True
    assert result.step_results[1].correct is False
    assert result.step_results[1].criteria_met == ["Chooses to divide both sides by 3"]
    assert result.step_results[1].criteria_missed == ["Correctly computes x = 4"]


def test_stepwise_score_out_of_range_rejected():
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse_stepwise(_all_correct_stepwise_response(graduated_score=1.5), _STEPS)


def test_step_results_longer_than_diverging_index_rejected():
    # FR-006: the agent reported step 1 as diverging but still included a
    # (fabricated) step 2 -- must never happen.
    response = json.dumps(
        {
            "graduated_score": 0.5,
            "first_diverging_step_index": 1,
            "step_results": [
                _step_result(0, all_met=True),
                _step_result(1, all_met=False),
                _step_result(1, all_met=True),  # step index reused/out of order too
            ],
            "grading_logic_version": "v1",
        }
    )
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse_stepwise(response, _STEPS)


def test_step_results_criteria_not_matching_rubric_rejected():
    payload = json.loads(_all_correct_stepwise_response())
    payload["step_results"][1]["criteria_results"] = [
        {"description": "a totally different criterion", "met": True},
        {"description": "Correctly computes x = 4", "met": True},
    ]
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse_stepwise(json.dumps(payload), _STEPS)


def test_step_results_shorter_than_total_with_no_divergence_rejected():
    # Claims no divergence (first_diverging_step_index null) but only
    # reported one of two steps.
    response = json.dumps(
        {
            "graduated_score": 1.0,
            "first_diverging_step_index": None,
            "step_results": [_step_result(0, all_met=True)],
            "grading_logic_version": "v1",
        }
    )
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse_stepwise(response, _STEPS)


def test_mismatched_first_diverging_step_index_rejected():
    # step_results shows step 1 diverging, but the agent self-reports null.
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse_stepwise(
            _diverges_at_step_1_response(first_diverging_step_index=None), _STEPS
        )


def test_mismatched_graduated_score_rejected():
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse_stepwise(_diverges_at_step_1_response(graduated_score=1.0), _STEPS)


def test_missing_step_results_rejected():
    with pytest.raises(_InvalidGradingResponse):
        _validate_and_parse_stepwise(_all_correct_stepwise_response(step_results=None), _STEPS)

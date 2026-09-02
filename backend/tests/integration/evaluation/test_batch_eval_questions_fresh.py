"""Integration tests for batch_eval_questions.py's --fresh mode (spec 014
FR-005/FR-007): generates a small sample via the real Assessment-
Generation path (no persisted GeneratedQuestion history required, unlike
the default DB-sampling mode) and re-validates it with _validate_draft.
"""

import asyncio
import json

import pytest
from scripts.batch_eval_questions import run_fresh_sample


def _draft_json(question_type: str = "multiple_choice") -> str:
    return json.dumps(
        {
            "question_type": question_type,
            "stem": "a freshly generated question",
            "options": ["a", "b", "c", "d"],
            "correct_index": 1,
            "correct_value": None,
            "tolerance": None,
        }
    )


def test_fresh_sample_passes_when_generation_is_valid(monkeypatch):
    async def _fake_run_agent_once(agent, session_service):
        return _draft_json()

    monkeypatch.setattr(
        "src.agents.assessment_gen.agent._run_agent_once", _fake_run_agent_once
    )

    total, failures = asyncio.run(run_fresh_sample(sample_size_per_subject=1))

    assert total > 0
    assert failures == []


def test_fresh_sample_reports_a_failing_question_by_reason(monkeypatch):
    """A validation failure (e.g. correct_index out of range) is reported
    as a clean failure, not a crash."""

    async def _fake_run_agent_once(agent, session_service):
        return json.dumps(
            {
                "question_type": "multiple_choice",
                "stem": "an invalid question",
                "options": ["a", "b"],
                "correct_index": 99,
                "correct_value": None,
                "tolerance": None,
            }
        )

    monkeypatch.setattr(
        "src.agents.assessment_gen.agent._run_agent_once", _fake_run_agent_once
    )

    total, failures = asyncio.run(run_fresh_sample(sample_size_per_subject=1))

    assert total > 0
    assert len(failures) == total


def test_fresh_sample_fails_closed_when_generation_call_itself_errors(monkeypatch):
    """FR-007: an eval that cannot run at all (e.g. a model/network error)
    is a reported failure, not a silent skip or an unhandled crash."""

    async def _raising_run_agent_once(agent, session_service):
        raise RuntimeError("simulated model/network failure")

    monkeypatch.setattr(
        "src.agents.assessment_gen.agent._run_agent_once", _raising_run_agent_once
    )

    total, failures = asyncio.run(run_fresh_sample(sample_size_per_subject=1))

    assert total > 0
    assert len(failures) == total
    assert all("simulated model/network failure" in f.reason for f in failures)


def test_main_fails_closed_when_fresh_finds_zero_content_artifacts(monkeypatch, tmp_path, capsys):
    """PR #55 review: `total == 0` (e.g. CONTENT_DIR resolving to nothing,
    a future content-layout change) must exit non-zero, not report a
    vacuous "0/0 passed" success."""
    import scripts.batch_eval_questions as batch_eval_questions

    monkeypatch.setattr(batch_eval_questions, "CONTENT_DIR", tmp_path)  # empty, no subject.yaml
    monkeypatch.setattr("sys.argv", ["batch_eval_questions.py", "--fresh"])

    exit_code = batch_eval_questions.main()

    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().out

"""Shared helpers for quiz integration tests (`test_quiz_*.py`).

Mirrors `test_second_subject.py`'s pattern of mocking the
Assessment-Generation Agent's LLM call boundary (`_run_agent_once`) so
these tests exercise the real quiz-session/difficulty/dedup paths
without depending on a live LLM call.
"""

import json
from collections.abc import Sequence
from unittest.mock import AsyncMock, patch


def draft_json(stem: str, *, correct_index: int = 0) -> str:
    return json.dumps(
        {
            "question_type": "multiple_choice",
            "stem": stem,
            "options": ["a", "b", "c", "d"],
            "correct_index": correct_index,
            "correct_value": None,
            "tolerance": None,
        }
    )


def patch_generation(stems: Sequence[str] | None = None):
    """Patches `_run_agent_once` to return sequential, distinct stems (a
    caller-provided cycle if given, else `f"quiz question #{n}"`)."""
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        if stems is not None:
            stem = stems[(call_count["n"] - 1) % len(stems)]
        else:
            stem = f"quiz question #{call_count['n']}"
        return draft_json(stem)

    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    )

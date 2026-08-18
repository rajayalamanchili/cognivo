"""Shared helpers for quiz integration tests (`test_quiz_*.py`).

Mirrors `test_second_subject.py`'s pattern of mocking the
Assessment-Generation Agent's LLM call boundary (`_run_agent_once`) so
these tests exercise the real quiz-session/difficulty/dedup paths
without depending on a live LLM call.
"""

import json
import uuid
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
    caller-provided cycle if given, else a fresh UUID-suffixed stem).

    Tests open a separate `with patch_generation():` block per API call
    (once per question generated), each installing a *new* mock with its
    own fresh counter -- so a counter-based default stem (e.g. `"quiz
    question #1"`) would collide across blocks and falsely trigger
    dedup-exhaustion (`is_near_duplicate`). A UUID suffix guarantees
    uniqueness regardless of how many times this is re-invoked within a
    test. The explicit `stems` cycle is unaffected, since some tests
    (e.g. dedup-exhaustion tests) rely on intentionally repeating a
    stem."""
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        if stems is not None:
            stem = stems[(call_count["n"] - 1) % len(stems)]
        else:
            stem = f"quiz question {uuid.uuid4()}"
        return draft_json(stem)

    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    )

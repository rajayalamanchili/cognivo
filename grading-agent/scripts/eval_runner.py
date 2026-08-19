#!/usr/bin/env python3
"""Runs the Grading Agent's current `GRADING_LOGIC_VERSION` against a
ground-truth JSONL file, twice per triple (accuracy + consistency, spec
007 FR-008/SC-003, research.md §11), and prints one NDJSON result line
per run to stdout.

Deliberately invoked as a subprocess from `backend/scripts/
check_grading_agent_eval.py` (T040) rather than imported directly --
`grading-agent/` is a genuinely separate deployable unit with its own
dependency set (research.md §2), and both projects happen to use the
top-level package name `src`, so importing this module's `agent.py`
directly into a `backend/` process would collide with `backend/src`'s
own `src` package in `sys.modules`. Running it in-process, under this
project's own `uv` environment, and passing results back as plain text
avoids that entirely -- and mirrors how the real backend->Grading-Agent
boundary is a request/response call, not a shared Python process.

Usage: uv run python scripts/eval_runner.py <ground_truth.jsonl>
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from src.agent import GRADING_LOGIC_VERSION, _agent  # noqa: E402

# Locked per research.md §7 -- the same score-to-binary rule
# `backend/src/services/grading_client/client.py::SCORE_THRESHOLD` uses.
# Duplicated here (not imported) because that module lives in `backend/`,
# a different deployable unit/dependency set (research.md §2) -- see this
# file's module docstring.
SCORE_THRESHOLD = 0.7

APP_NAME = "cognivo-grading-agent-eval"


async def _run_once(*, question_stem: str, rubric: dict, learner_answer: str) -> dict:
    session_service = InMemorySessionService()
    runner = Runner(app_name=APP_NAME, agent=_agent, session_service=session_service)
    user_id = "eval-harness"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)

    request_payload = {
        "question_stem": question_stem,
        "rubric": rubric,
        "learner_answer": learner_answer,
    }
    message = types.Content(role="user", parts=[types.Part(text=json.dumps(request_payload))])

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if final_text is None:
        return {"error": "no response from Grading Agent"}

    data = json.loads(final_text)
    graduated_score = data["graduated_score"]
    return {
        "graduated_score": graduated_score,
        "correct": graduated_score >= SCORE_THRESHOLD,
        "grading_logic_version": data.get("grading_logic_version"),
    }


async def _main_async(ground_truth_path: Path) -> None:
    with ground_truth_path.open() as f:
        triples = [json.loads(line) for line in f if line.strip()]

    for triple in triples:
        for run_index in (1, 2):
            try:
                run_result = await _run_once(
                    question_stem=triple["question_stem"],
                    rubric=triple["rubric"],
                    learner_answer=triple["learner_answer"],
                )
            except Exception as exc:  # noqa: BLE001 -- surfaced as a failed run, not a crash
                run_result = {"error": str(exc)}
            print(
                json.dumps(
                    {
                        "id": triple["id"],
                        "category": triple["category"],
                        "expected_correct": triple["expected_correct"],
                        "run_index": run_index,
                        "grading_logic_version_expected": GRADING_LOGIC_VERSION,
                        **run_result,
                    }
                ),
                flush=True,
            )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: eval_runner.py <ground_truth.jsonl>", file=sys.stderr)
        return 2
    asyncio.run(_main_async(Path(sys.argv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Unit test: `tutor_agent_client/client.py`'s `_process_raw_events()`
aggregation loop -- the FR-016 rewrite's riskier half, since
`test_extract_cite_passages_ids.py` only covers the extraction helper
in isolation (`/speckit-analyze` finding C1, 2026-08-28). Covers the
status_update/artifact_update dedup rule this module has carried since
before FR-016 (its own docstring: treating every response type as new
content would double-count the final chunk) now that it applies to
parts, not just flattened text.
"""

import logging
import uuid
from collections.abc import AsyncIterator

from a2a.helpers import new_data_part, new_message, new_text_artifact_update_event, new_text_part
from a2a.types import Role, StreamResponse, TaskState, TaskStatus, TaskStatusUpdateEvent
from google.protobuf import struct_pb2
from google.protobuf.json_format import ParseDict

from src.services.tutor_agent_client.client import (
    TutorAnswerDelta,
    TutorAnswerResult,
    _process_raw_events,
)

_TASK_ID = "task-1"
_CONTEXT_ID = "ctx-1"


def _status_update(*, state: int, parts: list) -> StreamResponse:
    message = new_message(parts, context_id=_CONTEXT_ID, task_id=_TASK_ID, role=Role.ROLE_AGENT)
    return StreamResponse(
        status_update=TaskStatusUpdateEvent(
            task_id=_TASK_ID,
            context_id=_CONTEXT_ID,
            status=TaskStatus(state=state, message=message),
        )
    )


def _cite_part(passage_ids: list[str]):
    part = new_data_part(
        {"name": "cite_passages", "args": {"passage_ids": passage_ids}, "id": "call-1"}
    )
    part.metadata.MergeFrom(ParseDict({"adk_type": "function_call"}, struct_pb2.Struct()))
    return part


async def _events(*responses: StreamResponse) -> AsyncIterator[StreamResponse]:
    for response in responses:
        yield response


async def _collect(raw_events, offered_passage_ids, exchange_id=None, session_id=None):
    events = []
    async for event in _process_raw_events(
        raw_events,
        offered_passage_ids=offered_passage_ids,
        exchange_id=exchange_id or uuid.uuid4(),
        session_id=session_id or uuid.uuid4(),
    ):
        events.append(event)
    return events


async def test_multiple_text_parts_across_separate_chunks_yield_in_order():
    events = await _collect(
        _events(
            _status_update(state=TaskState.TASK_STATE_WORKING, parts=[new_text_part("Light ")]),
            _status_update(
                state=TaskState.TASK_STATE_WORKING, parts=[new_text_part("provides energy.")]
            ),
            _status_update(state=TaskState.TASK_STATE_COMPLETED, parts=[]),
        ),
        offered_passage_ids=set(),
    )
    deltas = [e for e in events if isinstance(e, TutorAnswerDelta)]
    result = events[-1]
    assert [d.text for d in deltas] == ["Light ", "provides energy."]
    assert isinstance(result, TutorAnswerResult)
    assert result.answer_text == "Light provides energy."
    assert result.grounded_passage_ids == []


async def test_text_and_citation_in_the_same_message():
    passage_id = uuid.uuid4()
    events = await _collect(
        _events(
            _status_update(
                state=TaskState.TASK_STATE_COMPLETED,
                parts=[new_text_part("Light provides energy."), _cite_part([str(passage_id)])],
            ),
        ),
        offered_passage_ids={passage_id},
    )
    result = events[-1]
    assert isinstance(result, TutorAnswerResult)
    assert result.answer_text == "Light provides energy."
    assert result.grounded_passage_ids == [passage_id]


async def test_trailing_artifact_update_does_not_duplicate_text_or_reprocess_citation():
    passage_id = uuid.uuid4()
    artifact_update = StreamResponse(
        artifact_update=new_text_artifact_update_event(
            task_id=_TASK_ID, context_id=_CONTEXT_ID, name="answer", text="Light provides energy."
        )
    )
    events = await _collect(
        _events(
            _status_update(
                state=TaskState.TASK_STATE_COMPLETED,
                parts=[new_text_part("Light provides energy."), _cite_part([str(passage_id)])],
            ),
            artifact_update,
        ),
        offered_passage_ids={passage_id},
    )
    deltas = [e for e in events if isinstance(e, TutorAnswerDelta)]
    result = events[-1]
    assert len(deltas) == 1
    assert result.answer_text == "Light provides energy."
    assert result.grounded_passage_ids == [passage_id]


async def test_no_citation_call_yields_empty_grounded_ids_and_logs_a_warning(caplog):
    # PR #45 review: the warning must identify *which* exchange hit
    # the compliance failure, the same correlation this file's own
    # X-Tutor-Exchange-Id/X-Tutor-Session-Id headers exist to provide.
    exchange_id, session_id = uuid.uuid4(), uuid.uuid4()
    with caplog.at_level(logging.WARNING):
        events = await _collect(
            _events(
                _status_update(
                    state=TaskState.TASK_STATE_COMPLETED,
                    parts=[new_text_part("An ungrounded answer.")],
                ),
            ),
            offered_passage_ids=set(),
            exchange_id=exchange_id,
            session_id=session_id,
        )
    result = events[-1]
    assert any(str(exchange_id) in record.message for record in caplog.records)
    assert any(str(session_id) in record.message for record in caplog.records)
    assert isinstance(result, TutorAnswerResult)
    assert result.grounded_passage_ids == []
    assert any("cite_passages" in record.message for record in caplog.records)

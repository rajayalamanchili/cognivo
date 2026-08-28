"""Unit test: `tutor_agent_client/client.py`'s `_extract_cite_passages_ids()`
reads the `cite_passages` tool call's `passage_ids` argument from an
A2A `DataPart`, replacing the marker+JSON-in-text parsing this file
used to cover (`test_parse_grounded_ids.py`, deleted) -- three straight
PR-review rounds (PRs #42, #44) found a new way that heuristic text
parsing picked the wrong array or dropped real citations; FR-016
(spec.md, research.md §9) moves the signal to a structurally separate,
schema-validated channel instead of parsing it back out of prose.
"""

import uuid

from a2a.types import Part
from google.protobuf import struct_pb2
from google.protobuf.json_format import ParseDict

from src.services.tutor_agent_client.client import _extract_cite_passages_ids


def _text_part(text: str) -> Part:
    return Part(text=text)


def _cite_passages_part(passage_ids: list[str]) -> Part:
    return Part(
        data=ParseDict(
            {"name": "cite_passages", "args": {"passage_ids": passage_ids}, "id": "call-1"},
            struct_pb2.Value(),
        ),
        metadata=ParseDict({"adk_type": "function_call"}, struct_pb2.Struct()),
    )


def test_extracts_ids_from_cite_passages_data_part():
    passage_id = uuid.uuid4()
    parts = [_text_part("Light provides the energy."), _cite_passages_part([str(passage_id)])]
    assert _extract_cite_passages_ids(parts) == [passage_id]


def test_returns_empty_list_for_empty_cite_passages_call():
    parts = [_cite_passages_part([])]
    assert _extract_cite_passages_ids(parts) == []


def test_returns_none_when_no_cite_passages_part_present():
    parts = [_text_part("just a text delta, no citation call yet")]
    assert _extract_cite_passages_ids(parts) is None


def test_drops_non_uuid_shaped_entry_without_discarding_the_call():
    passage_id = uuid.uuid4()
    parts = [_cite_passages_part([str(passage_id), "n/a"])]
    assert _extract_cite_passages_ids(parts) == [passage_id]


def test_ignores_a_data_part_with_a_different_function_name():
    parts = [
        Part(
            data=ParseDict(
                {
                    "name": "some_other_tool",
                    "args": {"passage_ids": [str(uuid.uuid4())]},
                    "id": "x",
                },
                struct_pb2.Value(),
            ),
            metadata=ParseDict({"adk_type": "function_call"}, struct_pb2.Struct()),
        )
    ]
    assert _extract_cite_passages_ids(parts) is None


def test_ignores_a_data_part_missing_the_function_call_metadata_tag():
    # A `data` Part whose payload happens to look like a citation call
    # but isn't tagged `adk_type: function_call` (e.g. some other
    # structured data) must not be mistaken for the real tool call.
    parts = [
        Part(
            data=ParseDict(
                {"name": "cite_passages", "args": {"passage_ids": [str(uuid.uuid4())]}},
                struct_pb2.Value(),
            )
        )
    ]
    assert _extract_cite_passages_ids(parts) is None

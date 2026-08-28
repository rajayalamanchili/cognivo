"""Unit test: `tutor_agent_client/client.py`'s `_parse_grounded_ids()`
(backed by `_extract_grounded_id_candidates()`) tolerates common LLM
footer-formatting deviations.

Found during the T038 grounding investigation (roadmap.md, 2026-08-27):
a live 30-question run against production came back 0/30 grounded even
though the answers themselves showed real passages had clearly been
offered and used -- a strict `json.loads(footer_text.strip())` silently
returned `[]` for any footer that wasn't a *bare* JSON array (a code
fence, trailing prose, a leading label), with no exception surfaced
anywhere to explain why. This test file didn't exist before this fix --
`_parse_grounded_ids` had no unit coverage of its own at all. Two later
PR #42 review rounds each found a narrower bracket-extraction bug
reproducing the same failure via bracket-containing prose before/after
the real array (see the tests below named for those cases).
"""

import uuid

from src.services.tutor_agent_client.client import _parse_grounded_ids


def test_parses_bare_json_array():
    passage_id = uuid.uuid4()
    result = _parse_grounded_ids(f'["{passage_id}"]', {passage_id})
    assert result == [passage_id]


def test_tolerates_markdown_code_fence():
    passage_id = uuid.uuid4()
    footer = f'```json\n["{passage_id}"]\n```'
    assert _parse_grounded_ids(footer, {passage_id}) == [passage_id]


def test_tolerates_trailing_prose():
    passage_id = uuid.uuid4()
    footer = f'["{passage_id}"]\nThat passage covers this topic.'
    assert _parse_grounded_ids(footer, {passage_id}) == [passage_id]


def test_tolerates_leading_label():
    passage_id = uuid.uuid4()
    footer = f'Grounded passages: ["{passage_id}"]'
    assert _parse_grounded_ids(footer, {passage_id}) == [passage_id]


def test_empty_array_means_not_grounded():
    assert _parse_grounded_ids("[]", {uuid.uuid4()}) == []


def test_drops_fabricated_or_stale_ids():
    offered = uuid.uuid4()
    fabricated = uuid.uuid4()
    footer = f'["{offered}", "{fabricated}"]'
    assert _parse_grounded_ids(footer, {offered}) == [offered]


def test_no_array_at_all_returns_empty():
    assert _parse_grounded_ids("I used the course material to answer.", {uuid.uuid4()}) == []


def test_malformed_json_inside_brackets_returns_empty():
    assert _parse_grounded_ids("[not valid json]", {uuid.uuid4()}) == []


def test_tolerates_trailing_prose_containing_brackets():
    """PR #42 review finding: a first fix (a greedy `\\[.*\\]` regex)
    spanned from the first `[` to the *last* `]` in the whole footer --
    trailing prose with its own brackets (e.g. interval notation, very
    plausible from an algebra tutor) would swallow both into one invalid
    JSON blob, reproducing this same bug via a different trigger."""
    passage_id = uuid.uuid4()
    footer = f'["{passage_id}"]\nSee the interval [0, 1] for the domain.'
    assert _parse_grounded_ids(footer, {passage_id}) == [passage_id]


def test_tolerates_multiple_ids_with_trailing_bracketed_prose():
    first = uuid.uuid4()
    second = uuid.uuid4()
    footer = f'["{first}", "{second}"]\nThe inequality flips for x in [-3, 3].'
    assert _parse_grounded_ids(footer, {first, second}) == [first, second]


def test_tolerates_leading_prose_containing_brackets():
    """PR #42 review, third round: a bracket-balanced extraction that
    just returns the first *balanced* pair still picked a leading
    bracketed aside (e.g. "[0, 5]") over the real array further along,
    since `[0, 5]` is itself valid JSON -- `_extract_grounded_id_
    candidates` must keep scanning until it finds a candidate whose
    elements are actually UUID-shaped strings."""
    passage_id = uuid.uuid4()
    footer = f'Sources for the interval [0, 5]: ["{passage_id}"]'
    assert _parse_grounded_ids(footer, {passage_id}) == [passage_id]

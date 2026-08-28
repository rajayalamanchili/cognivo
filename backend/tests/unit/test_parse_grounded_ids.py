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

import json
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


def test_tolerates_one_non_uuid_placeholder_among_real_ids():
    """PR #43 review, round 6: rejecting the whole array if *any*
    element isn't UUID-shaped (rather than dropping just that element)
    would silently discard a real citation array over one stray
    hallucinated placeholder like "n/a" -- the pre-fix code always
    tolerated invalid individual elements, and this restores that."""
    offered = uuid.uuid4()
    footer = f'["{offered}", "n/a"]'
    assert _parse_grounded_ids(footer, {offered}) == [offered]


def test_prefers_purer_array_over_earlier_mixed_one():
    """PR #44 review, round 7: picking the *first* candidate with at
    least one UUID-shaped element (rather than the best-scoring one
    across the whole footer) meant a leading bracketed aside containing
    one coincidentally UUID-shaped token, mixed with ordinary numbers,
    would be accepted before the real, purer citation array later in
    the text was ever reached -- silently dropping the real citations.
    The fully UUID-shaped array must win regardless of position."""
    real_a, real_b = uuid.uuid4(), uuid.uuid4()
    coincidental = uuid.uuid4()
    footer = f'See [0, 5, "{coincidental}"]: ["{real_a}", "{real_b}"]'
    assert _parse_grounded_ids(footer, {real_a, real_b, coincidental}) == [real_a, real_b]


def test_prefers_larger_mostly_clean_array_over_small_clean_one():
    """PR #44 review, round 8: scoring candidates fraction-first meant a
    real 5-id array with one stray non-UUID placeholder (fraction 5/6)
    lost to an unrelated single coincidentally UUID-shaped token
    elsewhere in the footer (fraction 1/1) -- reintroducing exactly the
    failure round 6 exists to tolerate. Count-shaped elements must be
    compared first so the larger real array always wins."""
    real_ids = [uuid.uuid4() for _ in range(5)]
    coincidental = uuid.uuid4()
    real_array = json.dumps([str(i) for i in real_ids] + ["n/a"])
    footer = f'Unrelated aside: ["{coincidental}"]. Sources: {real_array}'
    assert _parse_grounded_ids(footer, {*real_ids, coincidental}) == real_ids


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


def test_prefers_nonempty_array_over_leading_empty_bracket_aside():
    """PR #42 review, fifth round: `_all_uuid_shaped([])` is vacuously
    true, so an incidental empty-bracket aside before the real array
    (e.g. "No citations here: []. Sources: [...]") would otherwise be
    accepted immediately as "the" grounding array, never even reaching
    the real, non-empty one later in the same footer."""
    passage_id = uuid.uuid4()
    footer = f'No citations here: []. Sources: ["{passage_id}"]'
    assert _parse_grounded_ids(footer, {passage_id}) == [passage_id]


def test_tolerates_leading_unbalanced_half_open_interval():
    """PR #42 review, fourth round: half-open interval notation like
    `[0, 5)` pairs `[` with `)`, not `]` -- the bracket-depth scanner
    starting from that `[` never finds a balancing `]` (every later
    `[`/`]`, including the real array's, gets folded into the same
    unresolved count), so it must give up on *that* `[` specifically
    and keep scanning for the next one rather than returning `None`
    for the whole footer."""
    passage_id = uuid.uuid4()
    footer = f'The domain is [0, 5) for this function: ["{passage_id}"]'
    assert _parse_grounded_ids(footer, {passage_id}) == [passage_id]

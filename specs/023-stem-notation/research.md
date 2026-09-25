# Research: Math and Science Notation for Free-Text Answers

## §1. Notation encoding: real Unicode characters, not markup

**Decision**: Represent notation as plain Unicode text, composed from
existing standard character ranges:
- Common fractions use the precomposed "vulgar fraction" code points
  where one exists (¼ ½ ¾ ⅓ ⅔ ⅕ ⅖ ⅗ ⅘ ⅙ ⅚ ⅐ ⅛ ⅜ ⅝ ⅞ ⅑ ⅒).
- Any other fraction is composed from superscript digits (⁰-⁹) +
  U+2044 FRACTION SLASH + subscript digits (₀-₉), e.g. "5/12" as
  "⁵⁄₁₂" -- a well-established, widely-rendered technique, not a
  custom encoding.
- Exponents use Unicode superscript digits (⁰-⁹) plus superscript
  minus (⁻) for negative exponents.
- Subscripts (chemical formulas) use Unicode subscript digits (₀-₉).

**Rationale**: This is still exactly a `str` -- the same type
`FreeTextAnswerInput`'s `text` state and `MultiStepAnswerInput`'s
`answers` array already hold, the same type `grade_answer`'s
`validate_response_shape` already requires for `FREE_TEXT`/`MULTI_STEP`
(`backend/src/services/mastery/grading.py`), and the same type
`answer_key`'s JSON column and the Grading Agent's A2A request already
carry. Choosing plain-text composition over a markup/structured format
means:
- **No new dependency** (Constitution Principle IX bias against adding
  server/build weight for a two-subject need).
- **No new rendering step anywhere** -- a `<textarea>`/`<input>` (or
  any future view) already renders arbitrary Unicode text correctly by
  definition; there is no "raw markup vs. rendered" distinction to get
  wrong.
- **No backend or schema change** -- `answer_key` stays the existing
  JSON column, `response`/`response_text` stay `str`/`list[str]`,
  Postgres `Text`/`JSON` columns are UTF-8 already.
- **No grading change** -- see §2.

**Alternatives considered**:
- *LaTeX input + KaTeX/MathJax rendering*: full mathematical fidelity
  and the industry-standard approach, but requires a new frontend
  rendering dependency, a render step wherever the answer might ever be
  displayed, and would hand the Grading Agent raw LaTeX source instead
  of natural text it already handles fine. Rejected: disproportionate
  for a scope limited to fractions/exponents/subscripts across exactly
  two subjects with no calculus content.
- *A structured expression object* (e.g. `{"type": "fraction", "num":
  1, "den": 2}` JSON with a custom React renderer): would introduce a
  genuinely new "Notated Answer" data shape needing its own renderer
  and a serialization step before the text reaches the Grading Agent or
  the audit log (both of which expect a plain string today). Rejected:
  Unicode composition already produces a plain, human-readable,
  directly-gradeable string with none of that translation machinery.
- *MathQuill/mathlive WYSIWYG editor*: a real, widely-used option, but
  a new third-party dependency needing its own LaTeX/MathML
  serialization decision for storage -- same rejection reasoning as the
  LaTeX row above.

## §2. Grading is unaffected -- corrects the original spec draft

**Finding**: The original spec draft (this feature's first pass)
assumed free-text grading was exact-match and that this feature needed
to introduce a new "rubric-authored accepted variant" comparison
mechanism to keep notated answers gradeable. Reading the actual grading
path shows this is factually wrong:
- `backend/src/agents/assessment_gen/agent.py` generates `rubric_criteria`
  as free-form, weighted natural-language descriptions (1-4 per
  free-text question, 2+ per multi-step step) -- not a literal
  accepted-answer string.
- `backend/src/services/grading_client/client.py` sends the learner's
  raw `response_text` and those criteria to the Grading Agent (A2A,
  Milestone 6), which returns a `graduated_score` judged against
  `SCORE_THRESHOLD = 0.7` -- an LLM semantic judgment, not a string
  comparison.
- `backend/src/services/mastery/grading.py`'s deterministic exact/
  tolerance comparison exists only for `multiple_choice`/`numeric`; its
  module docstring explicitly scopes it to those two types.

**Decision**: This feature makes zero changes to grading. A learner's
notated answer reaches the Grading Agent as the same opaque
`response_text`/`response_steps` string(s) a plain-text answer already
does, and is judged by the same rubric-criteria evaluation that already
tolerates equivalent phrasings (it already accepts "1/2", "0.5", or "a
half" as the same idea if a rubric criterion asks for one half). No
prompt change, no new comparison mechanism, no new rubric-authoring
requirement.

**Spec correction made**: `spec.md`'s FR-004, User Story 2, and the Key
Entities/Assumptions sections were rewritten to state this explicitly
(grading unchanged) rather than the original draft's incorrect
"exact-match against rubric-authored variants" framing. See
`checklists/requirements.md`'s Notes for the full record.

## §3. No existing view re-displays a learner's raw answer text

**Finding**: The original spec draft's User Story 3 assumed a learner
answer-history view and an instructor per-answer review view already
existed and just needed notation-aware rendering. Checking the actual
frontend:
- `frontend/src/app/instructor/review/review-flow.tsx` (the only
  instructor "review" surface) displays a flagged *question*'s stem/
  options/flagged reason (`content_review.py`'s `ListFlaggedOut`) --
  never a specific learner's submitted answer text.
- The quiz/practice post-grading UI shows `AnswerResult.criteria_met`/
  `criteria_missed` (rubric-criterion descriptions the Grading Agent
  returns), never the learner's own submitted string echoed back.
- No route or component reads a learner's answer text back out of
  storage for display anywhere in the product today.

**Decision**: Cut User Story 3. The only place a learner's answer text
is ever shown is the input field itself, while they're typing it
(before submission) -- already covered by User Story 1/FR-002.
Building a new answer-history or per-answer review view is a distinct,
materially larger feature (new endpoints, new UI, its own spec) and out
of scope here. Because notation is plain text (§1), any such view built
later renders it correctly automatically with zero dependency on this
feature -- there is no markup-interpretation debt being deferred.

## §4. Malformed/incomplete expression handling (FR-007)

**Decision**: The notation toolbar is a client-side state machine, not
a parser. "Build a fraction" and "exponent"/"subscript" mode are each a
small, explicit UI state (e.g. numerator typed -> slash inserted ->
awaiting denominator digits); the existing submit button's disabled
condition (`FreeTextAnswerInput`'s `text.trim() === """`,
`MultiStepAnswerInput`'s `allStepsFilled`) gains one more clause: also
disabled while any notation construct is left open (a fraction with a
slash but no denominator yet, an exponent/subscript mode toggled on
with nothing typed). No new validation service, no regex-based
well-formedness parser over arbitrary pasted text -- pasted text is
always accepted as opaque plain text (spec.md's Edge Cases), exactly as
today.

## §5. Backend/API impact

**Decision**: None. Confirmed by reading:
- `validate_response_shape` (`grading.py`): `FREE_TEXT` already
  requires `str`, `MULTI_STEP` already requires `list[str]` -- a
  Unicode-richer string still satisfies both unchanged.
- Answer length guardrail (`questions.py`, `len(response_text)`):
  Python's `len()` counts code points. A composed fraction like "⁵⁄₁₂"
  is 4 code points, comparable to typing "5/12" (4 ASCII characters) --
  no meaningful length distortion against the existing
  `MAX_LENGTH`/guardrail budget.
- `answer_key` (JSON column) and `response_text`/`response_steps`
  (Postgres `Text`, UTF-8) need no migration -- Unicode text already
  round-trips through both today.

No `tech-stack.md` amendment needed: no new dependency, no new agent,
no deployment-shape change.

## §6. Input mechanism

**Decision**: A small, reusable notation-toolbar UI (buttons for the
common precomposed fractions, plus "build a fraction," "exponent," and
"subscript" controls) rendered above the existing `<textarea>`
(`FreeTextAnswerInput`) and each per-step `<input>`
(`MultiStepAnswerInput`), inserting composed Unicode text at the
current cursor position. Shared between both components (they already
share the same submit-state-machine shape) rather than duplicated.

**Rationale**: Smallest addition that satisfies FR-001/FR-002/FR-007
without a new dependency or a new answer data shape -- consistent with
§1's decision that the output is always a plain string.

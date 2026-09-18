# Research: Process-Level STEM Grading

## 1. Latency budget vs. the existing Grading Agent call constants

**Decision**: Reuse `grading_client/client.py`'s existing
`REQUEST_TIMEOUT_SECONDS = 8.0` and `MAX_ATTEMPTS = 2` unchanged for the
new `grade_stepwise_answer()` call. No new timeout/retry constants.

**Rationale**: FR-003a already commits to one batched A2A call per
submission (never one call per step), so the call this feature adds is
structurally identical in shape to Milestone 6's existing
`grade_free_text_answer()` call -- a larger prompt (an ordered list of
steps and their criteria instead of one flat list), not a different
call pattern. Worst case (2 attempts, both timing out) is `2 * 8.0 +
1 * 0.2 = 16.2s`, comfortably under `grading-agent/`'s existing
`maxDuration: 30` Vercel ceiling, same margin Milestone 6's own
research.md §7 already established for the identical retry shape. The
typical (single-attempt) case is expected to run a few seconds slower
than Milestone 6's ~3.3s in-process baseline (a longer prompt, more
output tokens for a per-step breakdown), which still leaves real margin
under SC-006's 15s full-request-path target -- the same reasoning the
15s figure itself was chosen from (spec.md Clarifications).

**Alternatives considered**:
- *Per-step sequential calls, one LLM call per step*: rejected --
  violates FR-003a's flat-cost requirement outright, and multiplies
  latency by step count, which would blow both the 15s SC-006 budget
  and the 30s ceiling for any problem with more than a handful of
  steps.
- *A separate, longer timeout tuned for the multi-step call*: rejected
  as premature -- no real latency data exists yet for the new prompt
  shape (the same position Milestone 6 was in before its own SC-006
  clarification), and the existing constants already have measured
  margin. Revisit once real staging latency data exists, the same way
  Milestone 6's original 5.0s timeout was revised once its ground-truth
  eval gate produced real numbers.

## 2. Request-size headroom under the existing length-cap guardrail

**Decision**: No change to `grading-agent/src/guardrails.py`'s existing
total-request-length cap (the leaked-secret compensating control,
Constitution Principle VI). A multi-step submission's total text (all
steps' rubric criteria plus all of the learner's per-step answers,
serialized into one request) is bounded by the same cap that already
covers Milestone 6's single free-text submission.

**Rationale**: The cap exists to bound worst-case LLM token cost if the
shared secret leaks (tech-stack.md's "A2A leaked-secret compensating
control" row) -- it was never sized specifically to one flat criteria
list, so a request that's structurally an ordered list of several
smaller criteria lists plus several shorter per-step answers does not
inherently exceed it. `/speckit-tasks` should include a task to confirm
the cap's current value against a realistic multi-step payload (e.g.,
a 6-step algebra problem) rather than assume; if a real authored
question's payload turns out to exceed it, the fix is raising the
existing constant, not adding a second, multi-step-specific cap.

**Alternatives considered**:
- *A separate, larger cap for multi-step requests*: rejected --
  would need its own justification for why multi-step submissions
  deserve a different worst-case token-cost bound than free-text ones,
  which isn't true; a single cap sized correctly for the largest
  realistic payload (of either shape) is simpler and enforces the same
  guarantee.

## 3. Where the per-topic opt-in flag lives

**Decision**: A new nullable-default-`false` `Topic.step_grading_enabled:
bool` column, loaded from an optional per-topic `process_level_grading`
boolean field in the content artifact's YAML. No cross-topic
"all-or-nothing" rule (unlike Milestone 15's `grade_bands`).

**Rationale**: FR-001 asks for a **per-topic** opt-in ("a subject's
content artifact MUST be able to opt **a topic**"), not a per-subject
one -- structurally different from Milestone 15's grade-banding, which
spec 017's research.md Decision 1 deliberately made all-or-nothing
*per subject* because a subject either has a coherent grade sequence or
it doesn't. Process-level grading has no equivalent subject-wide
coherence requirement: one topic in `algebra-1` being naturally
multi-step (solving a linear equation) says nothing about whether a
different topic in the same subject (e.g., a single-step vocabulary
recall question) should be. A simple boolean column, independently set
per topic, is the correct-shaped shortcut here, not a scope-widened
copy of Milestone 15's existence-table pattern.

**Alternatives considered**:
- *A `GradeBand`-style existence table (`step_graded_topics`)*: rejected
  -- that pattern exists specifically because `GradeBand` needed to
  represent an ordered *set* of grades a subject spans, which a boolean
  flag has no equivalent need for.
- *All-or-nothing per subject, mirroring Milestone 15 exactly*: rejected
  -- would force every topic in `algebra-1` to author step rubrics even
  where multi-step decomposition doesn't naturally apply, which
  contradicts spec.md's own Assumptions (opt-in is deliberately
  topic-granular).

## 4. Step rubric shape and generation-time validation

**Decision**: Extend `GeneratedQuestionDraft` with an optional
`steps: list[StepDraft] | None` field (`StepDraft = {step_prompt: str,
rubric_criteria: list[RubricCriterion]}`, reusing the existing
`RubricCriterion` type unchanged). `_validate_draft()` gains a
`MULTI_STEP` branch requiring `len(steps) >= 2` (a "multi-step"
question with fewer than two steps is a contradiction) and, per step,
`len(rubric_criteria) >= 2` (FR-005 -- a single criterion per step can
never distinguish a sound method with a computational slip from a
genuinely incorrect method) plus the same non-empty-criteria /
weights-sum-to-~1.0 check `FREE_TEXT` already applies (FR-002, FR-010).
`_build_instruction()`'s multi-step guidance must explicitly ask the
model for one method-correctness criterion and one execution-
correctness criterion per step (not just "criteria" generically), so
the `>= 2` count produces a real method/execution split instead of two
arbitrary near-duplicate criteria. Stored in `GeneratedQuestion.answer_key`
as `{"steps": [{"step_prompt": ..., "criteria": [...]}]}` -- no new
column (data-model.md).

**Rationale**: Mirrors the exact generate-then-validate discipline
already in place for `FREE_TEXT` and `MULTIPLE_CHOICE` -- a malformed
draft triggers the existing `max_attempts` retry loop in
`generate_question()` rather than ever reaching a learner or requiring
new fallback logic. Reusing `RubricCriterion` (rather than inventing a
step-specific criterion type) keeps criteria-weight validation
identical at every level.

**Alternatives considered**:
- *A completely separate schema/model class for multi-step questions*:
  rejected -- `GeneratedQuestionDraft`'s existing flat-with-nulled-
  irrelevant-fields design (chosen in spec 007 specifically so the LLM
  has one unambiguous schema regardless of `question_type`) already
  accommodates one more optional field cleanly; a parallel class would
  duplicate `RubricCriterion` and the retry/validation plumbing for no
  benefit.

## 5. Initial content-artifact scope

**Decision**: Author `process_level_grading: true` on a small number of
naturally multi-step topics in `algebra-1` only, at implementation
time. `biology` (and every other unopted-in topic) is left untouched,
matching Milestone 15's precedent of using `biology` as the explicit
"nothing changed" regression fixture.

**Rationale**: Constitution Principle III requires the engine stay
subject-agnostic, not that every subject exercise every feature on day
one -- `biology`'s multi-step science reasoning (e.g., a multi-step
dimensional-analysis or stoichiometry problem) is a real future
candidate but authoring it isn't required to prove the mechanism is
domain-agnostic; the mechanism works identically for any subject that
authors step-structured questions, which is what SC-003's regression
requirement actually tests.

**Alternatives considered**:
- *Author step-enabled topics in both subjects immediately*: deferred,
  not rejected -- doable later with zero engine changes once this
  feature ships, exactly the kind of "add a second data point" step
  Milestone 1's own domain-agnostic proof already established as cheap
  once the mechanism itself is subject-agnostic.

## 6. Semantic grading cache (Milestone 13) is bypassed for multi-step, v1

**Decision**: `POST /answer`'s `multi_step` branch calls
`grade_stepwise_answer()` directly -- it does not route through
`grading_cache/cache.py`'s `get_or_grade_answer()` semantic cache that
`free_text` submissions already use.

**Rationale**: `get_or_grade_answer()` embeds one learner-answer string
(`embed_answer(question_stem, learner_answer)`) and verifies a cache
hit against one flat rubric-criteria list
(`matches_cached_criteria_pattern`). A stepwise submission has neither
shape -- it's an ordered list of per-step answers graded against an
ordered list of per-step criteria lists, with FR-006's stop-at-first-
error behavior baked into what "equivalent" would even mean (two
submissions that both fail at step 2 for different reasons are not
obviously cache-equivalent the way two paraphrases of one free-text
answer are). Building that equivalence check correctly is a
meaningfully different, larger problem than this feature's spec scoped
-- spec.md's Assumptions already draws the same kind of boundary around
Milestone 11's misconception classifier and the Recommendation Agent,
for the same reason (a real, larger integration, deliberately left for
a future feature once this one's core mechanism is proven). Skipping
the cache costs real LLM spend on repeat-identical multi-step
submissions (rare in practice -- unlike a free-text paraphrase, an
identical stepwise submission means byte-identical text at every step)
and is bounded by SC-002's determinism requirement regardless (a cache
hit or a live call must produce the same result either way, so
correctness doesn't depend on caching).

**Alternatives considered**:
- *Extend `get_or_grade_answer()` to accept a list-shaped answer/rubric*:
  rejected for v1 -- would require a new embedding strategy (concatenate
  all steps? embed each step separately and require every step to be
  independently close?) and a new step-aware equivalence classifier,
  neither of which spec.md's clarifications addressed; a real follow-up
  once real multi-step traffic volume exists to justify it (the same
  bar Milestone 13 itself was held to before it was built -- tech-
  stack.md's Semantic-caching row was deliberately deferred until real
  call volume was known).
- *A separate, simpler cache keyed on exact byte-identical step text*:
  rejected as premature -- no data yet on how often that actually
  recurs for multi-step submissions specifically; add only if real
  usage shows it matters.

# Phase 1 Data Model: Learner-Facing Explainability UI

No new tables, no new columns, no migration (see research.md). Every entity below is either an additive field on an existing Pydantic response model, or one new read-only query over an existing table. Field names deliberately match existing sibling fields (e.g. `AnswerOut`'s naming) rather than inventing parallel vocabulary.

## 1. Selection reason (extends `NextQuestionOut` only)

**Correction (found during Phase 2 implementation)**: `QuizQuestionOut` does NOT gain these fields. Quiz question selection (`next_quiz_topic`, a round-robin) never computes `is_fallback`/decay standing at all -- there is nothing to surface for quiz or instructor-assigned quiz attempts (research.md §1, spec.md Edge Cases).

| Field | Type | Source | Notes |
|---|---|---|---|
| `is_fallback` | `bool` | `NextTopicSelection.is_fallback` (already computed, M22) | True when this pick came from the mastered-topic review-fallback pool, not the normal eligible pool. |
| `p_mastery` | `float \| null` | `NextTopicSelection.p_mastery` | Raw, persisted mastery for the selected topic at selection time. `null` only if the topic had no prior `MasteryState` row. |
| `effective_p_mastery` | `float \| null` | `NextTopicSelection.effective_p_mastery` | Decay-adjusted mastery used to rank the fallback pool (M22). Equal to `p_mastery` when `is_fallback` is false or the topic is within its decay grace period. |
| `last_practiced_at` | `string \| null` (ISO 8601) | `NextTopicSelection.updated_at` (new field, added during Phase 2 implementation -- not in the original design) | The selected topic's last-practiced timestamp, sourced from `_load_topic_ranking_context`'s already-computed `updated_at_by_topic` map. Needed for FR-002's "naming elapsed time since last practice" wording, which the original three-field design omitted. `null` when the topic has no prior `MasteryState` row. |

**State transitions**: None -- computed fresh per selection, never persisted beyond the existing `NEXT_TOPIC_SELECTED` audit event.

**Validation**: FR-004 -- these three fields MUST NOT be present with fabricated values; when `NextTopicSelection` itself has no meaningful selection reason (should not occur given M1/M22's existing selection logic always populates it), omit the fields rather than defaulting to a misleading value.

## 2. Dashboard effective mastery (extends `MasteryTopicOut`)

| Field | Type | Source | Notes |
|---|---|---|---|
| `effective_p_mastery` | `float` | `effective_mastery_for_review(p_mastery, updated_at=, now=)` (`decay.py`), called per topic in `mastery.py`'s route | Existing `p_mastery` field is retained unchanged and now doubles as "peak" mastery in the UI's framing. `effective_p_mastery == p_mastery` when the topic is not yet mastered, or is within the decay grace period -- decay only ever applies to a mastered topic past grace (spec 024's own scope). |

**Validation**: FR-006 -- `effective_p_mastery` MUST equal `decay.py`'s own output for the same `(p_mastery, updated_at, now)` triple; no separate computation.

## 3. Grading result, extended flow coverage (extends `PlacementSubmitResponse`; no change to `AnswerOut`'s shape, only where it's read)

New nested type, field-for-field aligned with `AnswerOut`:

**`PlacementQuestionResult`**

| Field | Type | Source |
|---|---|---|
| `question_id` | `uuid.UUID` | The placement question just graded, from the existing loop in `submit_placement`. |
| `correct` | `bool` | `grade_answer(...)`'s existing return value, already computed in the loop. |
| `criteria_met` | `list[str] \| null` | Existing grading result for free-text/multi-step placement questions, if any. |
| `criteria_missed` | `list[str] \| null` | Same. |
| `step_results` | `list[StepResultOut] \| null` | Same shape as `AnswerOut.step_results` (spec 018). |
| `prior_p_mastery` | `float \| null` | `MasteryUpdateResult.prior_p_mastery`, already computed by `apply_mastery_update` in the loop. |
| `posterior_p_mastery` | `float` | `MasteryUpdateResult.posterior_p_mastery`. |
| `refreshed` | `bool` | See §4 below. |

**`PlacementSubmitResponse`** gains: `per_question_results: list[PlacementQuestionResult]`, populated in existing loop order (one entry per submitted answer). Existing aggregate `mastery_state` field is unchanged.

**`QuizAnswerResult`** (correction, found during implementation -- quiz gets its own type, not `PlacementQuestionResult`, since it's reconstructed from historical audit events rather than an in-flight request and lacks one field as a result):

| Field | Type | Source |
|---|---|---|
| `question_id` | `uuid.UUID` | `GeneratedQuestion.question_id`, joined by the summary query. |
| `topic_id` | `str` | `GeneratedQuestion.topic_id`, needed for `AnswerResultView`'s existing topic-label line. |
| `correct` | `bool` | `ANSWER_SUBMITTED` event's `payload["correct"]`. |
| `criteria_met` | `list[str] \| null` | Same event's `payload["criteria_met"]`. |
| `criteria_missed` | `list[str] \| null` | Same event's `payload["criteria_missed"]`. |
| `step_results` | `list[StepResultOut] \| null` | Same event's `payload["step_results"]`. |
| `prior_p_mastery` | `float \| null` | The matching `MASTERY_UPDATED` event's `payload["prior_p_mastery"]`. |
| `posterior_p_mastery` | `float` | Same event's `payload["posterior_p_mastery"]`. |
| ~~`band`~~ | -- | **Not reconstructable**: `mastery_band_for` needs `consecutive_mastered_observations`, never persisted in any event payload. `AnswerResultView`'s `band` display becomes conditional to accommodate this (spec.md Assumptions) rather than inventing a way to recompute it from history. |

**`QuizSummaryOut`**/`QuizSummaryResponse` gains: `per_question_results: list[QuizAnswerResult]`, computed by extending `compute_quiz_summary`'s existing `GeneratedQuestion` + `ANSWER_SUBMITTED`-event join (`services/quiz/session.py`) with a second join to each question's `MASTERY_UPDATED` event. Shared by both `quiz-flow.tsx` and `LearnerAssignments.tsx` (both call `getQuizSummary`/render `<QuizSummary>`) -- one backend change covers both flows for this story.

## 4. "Refreshed" acknowledgment (extends `AnswerOut`, and `PlacementQuestionResult` above)

| Field | Type | Source | Notes |
|---|---|---|---|
| `refreshed` | `bool` | `refreshed_from_bands(prior_band, posterior_band)`, a shared helper co-located with `MasteryUpdateResult` in `mastery_tool.py`, called from each response-building call site (`questions.py`, `placement.py`) | `MasteryUpdateResult` gains `prior_band: MasteryBand`, derived from the already-constructed `prior_observation.band` (or `MasteryBand.STRUGGLING` when `prior_observation is None` -- no prior state can never already be mastered). The comparison itself (`prior_band != MASTERED and posterior_band == MASTERED`) is centralized in `refreshed_from_bands()` rather than repeated at each call site, so `questions.py` and `placement.py` can't drift onto two independently-maintained copies of the same check. Never persisted; recomputed fresh on every answer, discarded after the response is sent (Clarifications: no new tracking field). |

**State transitions**: None persisted. This is a pure derived value of one request's before/after mastery bands.

**Validation**: FR-011/SC-005 -- `refreshed` MUST be `true` in exactly the below-to-above `MASTERED` crossing case and `false` in every other case, including "already mastered, answered again" and "still below threshold after answering."

## 5. Mastery history (new read-only query + endpoint)

**`MasteryHistoryPoint`** (new response item, no new table)

| Field | Type | Source |
|---|---|---|
| `recorded_at` | `datetime` | `AssessmentEvent.created_at` |
| `p_mastery` | `float` | `AssessmentEvent.payload["posterior_p_mastery"]` |

Query: filter `AssessmentEvent` by `learner_id`, `subject_id`, `topic_id`, `event_type == MASTERY_UPDATED`; `order_by(created_at)` -- exact pattern reused from `weak_area.py`'s `_build_evidence`.

**New endpoint**: `GET /api/learners/{learner_id}/topics/{topic_id}/mastery-history` -> `MasteryHistoryOut { points: list[MasteryHistoryPoint] }`.

**Edge cases** (from spec.md Edge Cases): zero points for a topic with no `MASTERED_UPDATED` history ("unknown" topic) -- frontend renders no trend line, per FR-012. One point -- frontend renders a flat/single-point state, not an implied trend.

## 6. Weak-area report (no new entity)

Reuses `RecommendationsResponse` (`recommendation.py`) exactly as already returned by `GET /api/learners/{learner_id}/recommendations`. No new field, no new endpoint -- only a new frontend rendering.

## Cross-cutting: no new enums, no new audit event types

All six items above read existing `AssessmentEventType` values (`NEXT_TOPIC_SELECTED`, `MASTERY_UPDATED`) and existing `MasteryBand` values. No new event type is introduced -- these explanations were already being logged for other reasons (Principle V); this feature is the first thing to read them back out for the learner.

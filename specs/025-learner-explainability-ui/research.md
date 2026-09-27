# Phase 0 Research: Learner-Facing Explainability UI

All unknowns below were resolved by reading the actual code the feature extends, not by assumption -- each decision cites the exact existing function/model it reuses, per Constitution Principle I's "no second implementation" bar.

## 1. Why-this-question chip (User Story 1 / FR-001-004)

**Decision**: `select_next_topic` (`backend/src/agents/sequencing/agent.py`) already returns a `NextTopicSelection` carrying `is_fallback`, `p_mastery`, and `effective_p_mastery` (Milestone 22). These are already written into the `NEXT_TOPIC_SELECTED` audit payload but discarded before the HTTP response model is built. Add all three as additive fields on `NextQuestionOut` only. `build_next_question_out` (`questions.py`) is already the single shared builder for the ordinary next-question route and both timed-practice routes (`practice_sessions.py`) -- extending it there fixes three call sites at once.

**Correction (found during Phase 2 implementation, not caught during planning)**: `QuizQuestionOut` (`quiz.py`) does **not** get these fields. `generate_quiz_question` (`services/quiz/session.py`) selects its topic via `next_quiz_topic` -- a one-line round-robin (`topic_ids[questions_generated_so_far % len(topic_ids)]`) that never calls `select_next_topic`/`rank_eligible_topics` at all. There is no eligible-pool/fallback distinction for a quiz question to report; adding `is_fallback` to `QuizQuestionOut` would mean fabricating a value quiz never computes, which FR-004 explicitly prohibits. Quiz and instructor-assigned quiz attempts get no "why this question" chip (spec.md Edge Cases, Assumptions).

**Rationale**: Zero new computation -- the values already exist in memory at the exact point the response is built. This is an additive response-field change, not new logic.

**Alternatives considered**: Adding a `GET /api/questions/{id}/why` follow-up endpoint -- rejected as an extra round trip for data already computed in the same request that serves the question.

## 2. Developer-configurable explanation scope (FR-003)

**Decision**: An environment variable read on the frontend (e.g. `NEXT_PUBLIC_EXPLAIN_EVERY_PICK`, default `true`) gates whether `SelectionReasonChip` renders for an eligible-pool (non-fallback) pick. A fallback/decay pick's chip always renders regardless of the switch, since FR-003's "fallback/decay picks only" mode is the narrower of the two settings. The backend always includes the three fields in the response (cheap, already computed) -- the switch is purely a rendering decision, so toggling it needs no backend redeploy.

**Rationale**: Simplest mechanism that satisfies "developer-configurable" without inventing a new settings table or admin UI (ladder: env var before anything heavier). Matches this project's existing precedent for deployment-level toggles (`LLM_PROVIDER`, `EXPLAIN_EVERY_PICK`-shaped env vars already used elsewhere in this project's provider-switch history).

**Alternatives considered**: A backend-side flag that omits the fields entirely when scope is narrowed -- rejected because it would mean the backend, not the frontend, decides presentation policy, and would require a redeploy to toggle rather than a env-var-only change; also makes the always-safe "backend never fabricates, frontend never overclaims" boundary (FR-004) fuzzier than it needs to be.

## 3. Dashboard effective mastery (User Story 2 / FR-005-006)

**Decision**: `GET /api/learners/{learner_id}/mastery-state` (`mastery.py`) currently returns raw `p_mastery` only; `effective_mastery_for_review(p_mastery, updated_at=, now=)` (`decay.py`) is reachable today only from inside the Sequencing Agent's ranking. Call that same pure function from `mastery.py`'s route, once per topic, and add `effective_p_mastery` to `MasteryTopicOut`, alongside the existing `p_mastery` (kept as "peak") and `last_updated_at` (already fetched into frontend state today but unused -- `DashboardSubjectSection.tsx`).

**Rationale**: Reuses the exact function Milestone 22 built and locked; the dashboard route becomes a second *caller* of that function, not a second *implementation* of decay (Principle I).

**Alternatives considered**: Persisting a decayed value on `MasteryState` -- rejected; Milestone 22 deliberately made decay a read-time-only computation, never written back, specifically so the persisted `p_mastery` always stays the true, undecayed prior for the next BKT update (spec 024 User Story 2). Duplicating that value into a stored column would reintroduce the exact risk that design avoided.

## 4. Per-criterion grading view flow coverage (User Story 3 / FR-009-010)

**Decision**: Two distinct gaps, two distinct fixes:
- **Quiz (untimed/timed) and instructor-assigned attempts**: `POST /api/questions/{question_id}/answer` already returns the full shape (`correct`, `criteria_met`, `criteria_missed`, `step_results`, `prior_p_mastery`, `posterior_p_mastery`) for every flow that calls it, including quiz -- confirmed by reading `AnswerOut`'s construction in `questions.py`. `quiz-flow.tsx` calls this same endpoint but discards the result entirely (no `AnswerResultView`, not even a bare correct/incorrect banner today). **This is a frontend-only fix**: render the existing `AnswerResultView` component in `quiz-flow.tsx`'s per-question result step, identical to how `practice-flow.tsx` already does it.
- **Placement**: `submit_placement` (`placement.py`) grades every submitted answer in one loop (`for answer in body.answers`), calling `grade_answer` and `apply_mastery_update` per question, but `PlacementSubmitResponse` returns only the final aggregate `mastery_state` -- no per-question detail survives the loop. **This is a real backend gap**: add `per_question_results: list[PlacementQuestionResult]`, built inside the existing loop from values already computed there, with fields matching `AnswerOut`'s naming exactly (`question_id`, `correct`, `criteria_met`, `criteria_missed`, `step_results`, `prior_p_mastery`, `posterior_p_mastery`) for consistency.

**Rationale**: `AnswerResultView` already handles both the free-text (flat criteria) and multi-step (per-step criteria) shapes correctly (confirmed by reading the component) -- no component change needed, only extending where the data reaches it.

**Alternatives considered**: Building a new, simplified grading-summary component for quiz/placement -- rejected; the existing component already does exactly this job and reuse is strictly less code (ladder step 2).

## 5. "Refreshed" acknowledgment (User Story 4 / FR-011)

**Decision**: "Mastered" is not a raw `p_mastery >= 0.7` check -- `mastery_band_for(p_mastery, consecutive_mastered_observations)` (`models/enums.py`) requires *both* `p_mastery >= 0.7` *and* `consecutive_mastered_observations >= MASTERY_CONFIRMATION_THRESHOLD` (2). `apply_mastery_update` (`mastery_tool.py`) already constructs a `prior_observation: MasteryObservation | None` before overwriting it and already returns `posterior_band` on `MasteryUpdateResult`, but not `prior_band`. Add `prior_band: MasteryBand` to `MasteryUpdateResult` (derived one line from `prior_observation.band if prior_observation else MasteryBand.STRUGGLING`, since no prior state can never be "mastered"). Each caller (`questions.py`'s `AnswerOut` builder, and placement's new per-question result) computes `refreshed = prior_band != MasteryBand.MASTERED and posterior_band == MasteryBand.MASTERED` -- a one-line boolean comparison of two already-returned enum values, added to the response, never persisted (per Clarifications: no new tracking state, computed once per response).

**Rationale**: Reuses `mastery_band_for`'s exact compound condition rather than re-deriving a simpler (and subtly wrong) threshold check in the API layer -- the single most likely place a duplicate, drifting definition of "mastered" would otherwise get introduced.

**Alternatives considered**: A raw `posterior_p_mastery >= 0.7 and prior_p_mastery < 0.7` check in the API layer -- rejected; it would silently diverge from the real "mastered" definition (the confirmation-streak requirement) the first time a learner's streak, not just their score, is what crosses the line.

## 6. Mastery trend (User Story 5 / FR-012)

**Decision**: `MasteryState` is a single row per `(learner_id, subject_id, topic_id)`, overwritten in place -- no history table. `AssessmentEvent` (append-only) already carries `posterior_p_mastery` in the JSON `payload` of every `MASTERY_UPDATED` event (written at both `questions.py` and `placement.py`'s mastery-update call sites). `weak_area.py`'s `_build_evidence` already establishes the exact query pattern needed: filter by `learner_id`/`subject_id`/`topic_id`/`event_type == MASTERY_UPDATED`, `order_by(AssessmentEvent.created_at)`. Add one new query helper (`mastery_history.py`) following that same pattern, extracting `(created_at, payload["posterior_p_mastery"])` pairs, and one new route (`GET /api/learners/{learner_id}/topics/{topic_id}/mastery-history`).

**Rationale**: No new table, no new write path -- the audit log Milestone 1 already requires (Principle V) is repurposed as the trend's data source, exactly the kind of reuse this project's own precedent (`weak_area.py`) already established for reading assessment history.

**Alternatives considered**: A dedicated `mastery_history` table written alongside `MasteryState` on every update -- rejected; would be a second, redundant write path for data the audit log already captures durably.

## 7. Learner-facing weak-area summary (User Story 6 / FR-013-014)

**Decision**: `GET /api/learners/{learner_id}/recommendations` (`recommendation.py`) is already learner-scoped (not only instructor-scoped) and already has a frontend client function (`getRecommendations`, `api.ts`). **Zero backend change.** This story is purely a new frontend component (`WeakAreaSummary.tsx`) rendering the existing response in softened, encouraging copy.

**Rationale**: Confirms Constitution Principles III/IV are satisfied by construction -- there is no second weak-area-detection code path to accidentally introduce, because none is needed.

**Alternatives considered**: None -- this is the zero-risk story in the set.

## 8. Age-adaptive copy routing (FR-016)

**Decision**: Milestone 17 established three independent, DB-free, grade-band-keyed lookups sharing one pattern but no shared code: `determine_mediation_tier(unlocked_grade)` (backend), `getPacingProfile(unlockedGrade)` (`frontend/src/lib/pacing.ts`), and the read-aloud eligibility resolver -- all keyed off the same 1-2/3-5/6-8/9-12 grade bands via `GradeProgress.unlocked_grade`. No existing generic "adapt this copy string" function exists. Add one new frontend module, `explainabilityCopy.ts`, following `pacing.ts`'s exact shape: `getExplanationCopyTier(unlockedGrade)` returning a small phrasing-tier object the five new/extended components read from.

**Rationale**: Matches the established pattern exactly rather than inventing a different shape for the same kind of decision, keeping "age-adaptive" a single recognizable concept across the codebase even though no single shared function exists yet to call.

**Alternatives considered**: Extracting a shared generic tier-lookup function all four (mediation, pacing, read-aloud, explanation-copy) call through -- rejected as out of scope; refactoring Milestone 17's already-shipped, already-tested lookups is not this feature's job, and three independent small functions following one pattern is not the kind of duplication Principle III/IV's "one engine" concern is about (that principle targets subject-specific logic, not this general a pattern).

## Summary of resolved unknowns

No `NEEDS CLARIFICATION` markers remain. Every decision above reuses an existing pure function, an existing shared response-model builder, or an existing established pattern -- no new dependency, no new migration, no new agent, no new computation.

# API Contract Changes: Learner-Facing Explainability UI

All changes are additive (new optional/always-present fields, or one new endpoint). No existing field changes type or meaning; no existing endpoint's request shape changes. Backward compatible by construction -- an old frontend build talking to a new backend ignores the new fields; the new frontend requires the new backend.

## Modified: `GET /api/questions/next` (and the two timed-practice equivalents in `practice_sessions.py`, via shared `build_next_question_out`)

**`NextQuestionOut`** gains:
```
is_fallback: bool
p_mastery: float | null
effective_p_mastery: float | null
```

## Modified: `POST /api/quizzes/{quiz_id}/start` and next-question routes in `quiz.py` / `quiz_assignments.py`

**`QuizQuestionOut`** gains the same three fields as `NextQuestionOut` above.

## Modified: `POST /api/questions/{question_id}/answer`

**`AnswerOut`** gains:
```
refreshed: bool
```

## Modified: `GET /api/learners/{learner_id}/mastery-state`

**`MasteryTopicOut`** gains:
```
effective_p_mastery: float
```
(Existing `p_mastery` is unchanged and is read by the frontend as "peak" mastery; existing `last_updated_at` is unchanged -- already present, previously unused by the UI.)

## Modified: `POST /api/placement/submit`

**`PlacementSubmitResponse`** gains:
```
per_question_results: list[PlacementQuestionResult]
```
where `PlacementQuestionResult` is:
```
question_id: uuid
correct: bool
criteria_met: list[str] | null
criteria_missed: list[str] | null
step_results: list[StepResultOut] | null
prior_p_mastery: float | null
posterior_p_mastery: float
refreshed: bool
```
(Field-for-field aligned with `AnswerOut`; existing aggregate `mastery_state` field unchanged.)

## New: `GET /api/learners/{learner_id}/topics/{topic_id}/mastery-history`

Response:
```
MasteryHistoryOut {
  points: list[MasteryHistoryPoint]
}
MasteryHistoryPoint {
  recorded_at: datetime
  p_mastery: float
}
```
Empty `points` list for a topic with no `MASTERY_UPDATED` history (never a 404 -- an "unknown" topic is a valid, empty-history state per spec.md's Edge Cases). Auth/ownership check mirrors the existing `GET /api/learners/{learner_id}/mastery-state` route (guardian-or-self, same as every other learner-scoped route in this project).

## Unmodified, reused as-is

`GET /api/learners/{learner_id}/recommendations` -- zero change, User Story 6 reads this response as-is (research.md §7).

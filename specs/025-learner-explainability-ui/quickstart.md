# Quickstart: Learner-Facing Explainability UI

**Feature**: `025-learner-explainability-ui` | **Date**: 2026-09-27

Validates all six user stories against a real dev database. No migration ships with this feature (`alembic upgrade head` should show zero drift). Reuses the seeded demo learner and `algebra-1`, plus the same decay-backdating technique `specs/024-mastery-decay/quickstart.md` established (a 21-day grace + 45-day half-life can't be waited out live).

## Setup

```bash
cd backend
alembic upgrade head   # confirms zero drift -- no migration in this feature
```

## Scenario 1 -- User Story 1: why-this-question chip (SC-001)

Exhaust every other topic to force a fallback pick (same setup as spec 024's Scenario 1), then:

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/next-question?subject_id=algebra-1"
```

**Expected**: response includes `is_fallback: true`, `p_mastery` (raw), and `effective_p_mastery` (decayed). Answer a question from the normal eligible pool instead (any topic with an unmet prerequisite path): **Expected** `is_fallback: false`, `p_mastery == effective_p_mastery`. Confirm the frontend chip (`SelectionReasonChip`) renders distinct copy for each case.

## Scenario 2 -- User Story 2: decay-aware dashboard (SC-002/SC-003)

With `<topic-a>` backdated 90 days past decay onset (per spec 024's Scenario 1 SQL):

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/mastery-state?subject_id=algebra-1"
```

**Expected**: `<topic-a>`'s entry shows `effective_p_mastery < p_mastery`; a topic never backdated shows `effective_p_mastery == p_mastery`. Load the dashboard in the browser and confirm the "last practiced" indicator is visibly warmer for `<topic-a>` **and** carries a text label (not color alone -- FR-007).

## Scenario 3 -- User Story 3: grading detail in quiz (at the summary) and placement (immediately) (SC-004)

**Corrected during implementation** (spec.md Clarifications, research.md §4): quiz has no per-question pause, so grading detail is gathered into the end-of-session summary instead, disclosed upfront. Start a quiz, answer a question, then fetch the summary:

```bash
curl -s -X POST "$BACKEND_URL/api/questions/<question_id>/answer" \
  -H "Content-Type: application/json" -d '{"response": ...}'
curl -s "$BACKEND_URL/api/quizzes/<quiz_session_id>"
```

**Expected**: the answer response is unchanged (no immediate grading-detail render for quiz). The summary response's `per_question_results[]` contains one entry per answered question with `correct`/`criteria_met`/`criteria_missed`/`step_results`/`prior_p_mastery`/`posterior_p_mastery` (no `band` -- not reconstructable from history). In the browser, confirm the quiz start screen discloses "you'll see how you did... at the end" (FR-010a) and the summary renders `AnswerResultView` per question via `QuizSummary`. Repeat via `POST /api/placement/submit`: **Expected** `per_question_results[]` on that response directly (shown immediately, matching placement's existing timing) -- `criteria_met`/`criteria_missed`/`step_results` are always `null` there since placement never generates free-text/multi-step questions (research.md §4).

## Scenario 4 -- User Story 4: refreshed acknowledgment (SC-005)

With `<topic-a>` decayed below the mastered band (backdate + let a subsequent wrong answer or fresh state push it below `0.7`, or use a never-mastered topic answered up to crossing), answer it correctly enough to cross back into `mastered`:

```bash
curl -s -X POST "$BACKEND_URL/api/questions/<question_id>/answer" \
  -H "Content-Type: application/json" -d '{"response": <correct-response>}'
```

**Expected**: `refreshed: true` in that response only (this applies directly to practice and placement, which show it immediately). Answer the same (now-mastered) topic again: **Expected** `refreshed: false` (nothing to recover -- Acceptance Scenario 3). Reload the dashboard: **Expected** no acknowledgment reappears (Acceptance Scenario 4 -- it was shown once, in that one response, never recomputed).

**Quiz's own reveal (Acceptance Scenario 5, research.md §5 correction)**: repeat the crossing inside a quiz session instead. **Expected**: the live answer response still carries `refreshed: true` (same field, same one-shot computation), but the quiz UI does not show it immediately -- confirm in the browser that it instead appears once in that quiz's end-of-session summary, carrying forward the exact value from the crossing answer's own response (never re-derived from a later check).

## Scenario 5 -- User Story 5: mastery trend (FR-012)

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/topics/<topic-a>/mastery-history"
```

**Expected**: `points[]` in chronological order, one entry per `MASTERY_UPDATED` event for that learner/topic. For a topic answered only once: a single-point response (frontend renders it without implying a trend). For a topic with no `MasteryState` at all: empty `points[]` (frontend renders no trend line).

## Scenario 6 -- User Story 6: learner-facing weak-area summary (SC-006)

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/recommendations?subject_id=algebra-1"
```

**Expected**: identical response to what Milestone 4's dashboard and Milestone 7's instructor dashboard already consume (no change). In the browser, confirm the new learner-facing summary lists exactly these weak areas in softened copy, or the "nothing flagged right now" state when `weak_areas` is empty.

## Automated coverage

```bash
cd backend
uv run pytest tests/ -k "explainability or selection_reason or refreshed or mastery_history or placement_grading_detail" -v
cd ../frontend
npm test -- --run
```

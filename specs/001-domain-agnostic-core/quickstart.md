# Quickstart: Domain-Agnostic Core

**Feature**: `001-domain-agnostic-core` | **Date**: 2026-08-15

Validates the placement-through-first-follow-up-question flow end to
end -- the same flow SC-007's automated post-deploy smoke test runs
against the live Vercel deployment. See `data-model.md` for entity
detail and `contracts/api.md` for exact request/response shapes.

## Prerequisites

- Postgres database provisioned (Neon or equivalent), connection string
  set (`DATABASE_URL`).
- `ASSESSMENT_GEN_MODEL` env var set (default:
  `anthropic/claude-sonnet-...`, per `research.md` §2) plus the
  corresponding provider API key.
- Langfuse project + API keys configured (`tech-stack.md` Observability).
- Both content artifacts loaded and passing validation: `algebra-1`,
  `biology` (see `data-model.md`'s Subject/Topic/PrerequisiteEdge
  validation rule).
- One seeded `DemoLearnerProfile` row with `is_demo = true`.

## Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head          # or equivalent migration tool
python scripts/seed_demo_learner.py
python scripts/load_content_artifact.py content/algebra-1/
python scripts/load_content_artifact.py content/biology/

# Frontend
cd ../frontend
npm install
```

## Run locally

```bash
# Backend (FastAPI/ADK)
cd backend && uvicorn main:app --reload

# Frontend (Next.js)
cd frontend && npm run dev
```

## Validation scenario: placement through first follow-up question

Maps directly to spec.md User Stories 1-2's Acceptance Scenarios.

1. **Start placement**
   `POST /api/subjects/algebra-1/placement/start`
   → Confirm the response contains exactly one question per entry-level
   topic in `algebra-1`'s topic graph (FR-003).

2. **Submit placement answers**
   `POST /api/placement/{placement_session_id}/submit` with a scripted
   answer set.
   → Confirm every touched topic has an explicit `p_mastery`/`band`, and
   every untouched topic reports `"status": "unknown"` (FR-005).
   → Re-run steps 1-2 with the identical scripted answers against a
   fresh placement session; confirm byte-identical `mastery_state`
   output (SC-001).

3. **Request next question**
   `GET /api/learners/{learner_id}/next-question?subject_id=algebra-1`
   → Confirm the selected `topic_id` is `struggling`, `developing`, or
   `unknown` with every prerequisite `mastered` (FR-006,
   data-model.md's Next-topic eligibility rule) -- never a `mastered`
   topic while any lower-priority topic remains eligible.
   → Confirm `difficulty` matches the selected topic's band per
   data-model.md's Difficulty-selection rule (`easy` for
   struggling/unknown, `medium` for developing, `hard` only for a
   `mastered`-fallback topic).
   → Repeat 5 times for the same topic (after answering each, to move
   past the "already answered" gate); confirm no two `stem` values are
   text-identical (SC-002) and none are near-duplicates within the last
   5 (FR-008, research.md §3).
   → Separately, script a session where every topic reaches `mastered`;
   confirm the next request falls back to the lowest-`p_mastery`
   `mastered` topic instead of an error response.

4. **Submit an answer**
   `POST /api/questions/{question_id}/answer`
   → Confirm `correct` matches a direct comparison against the
   generated `answer_key` -- exact-match for `multiple_choice`, within
   the question's own relative tolerance for `numeric` (FR-009).
   → Confirm `posterior_p_mastery` moved in the expected direction from
   `prior_p_mastery`.

5. **Flag a question**
   `POST /api/questions/{question_id}/flag`
   → Confirm a subsequent `next-question` call for that topic never
   returns the flagged `question_id` (FR-011).

6. **Audit trail check** (SC-006)
   Query `AssessmentEvent` rows for the full session above → confirm one
   row exists per placement question shown, per answer submitted, per
   mastery update, and per next-topic selection, each with enough
   `payload` detail to reconstruct the decision.

7. **Trace check** (SC-008)
   Compare the count of agent invocations made during the session above
   against the count of traces received in Langfuse for the same time
   window → confirm equal counts, no dropped spans.

8. **Degenerate-answer-pattern check** (SC-005)
   Re-run steps 1-2 twice: once with a scripted answer set that picks
   the same multiple-choice option regardless of question content, and
   once with a scripted set that submits the same numeric value
   regardless of question content → confirm no touched topic's
   resulting `band` is `mastered` in either run.

9. **Second-subject check** (User Story 3, SC-004)
   Repeat steps 1-4 against `subject_id=biology` → confirm identical
   endpoint behavior with zero engine-file changes (verified separately
   by the automated subject-id-keyed-conditional scan, not by this
   manual run).

## Deployment smoke test (SC-007)

Playwright (research.md §4) drives the actual deployed frontend URL
through steps 1-4 above via the browser, not direct API calls -- this is
what "deployable and demoable," not just "the API responds correctly,"
means per Constitution Principle IX. Run after every deploy to
`staging` and `main`.

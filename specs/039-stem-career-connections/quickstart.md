# Quickstart: STEM-Career Connections

**Feature**: `039-stem-career-connections` | **Date**: 2026-10-04

Validates all three user stories against a real dev database. One
migration ships with this feature (`topics.career_connection`,
`learner_profiles.career_connections_enabled`) -- `alembic upgrade head`
should apply exactly that, no drift beyond it. Reuses the seeded demo
learner, both existing content artifacts (`algebra-1`, `biology`), and a
guardian-owned real (non-demo) learner (Milestone 7).

## Setup

```bash
cd backend
alembic upgrade head   # applies both new columns
python scripts/load_content_artifact.py content/algebra-1/subject.yaml
python scripts/load_content_artifact.py content/biology/subject.yaml
  # re-loads both subjects now that their topics carry `career_connection` (FR-010)
```

Confirm the reload populated real connections, not placeholders:

```sql
SELECT subject_id, topic_id, career_connection FROM topics
WHERE career_connection IS NOT NULL ORDER BY subject_id, topic_id;
```

**Expected**: every graded-and-ungraded topic in both `algebra-1` and
`biology` has a non-null `career_connection` naming a real career/field
(FR-010) -- unlike Standards Alignment, `biology`'s ungraded topics are
*not* excluded here (research.md Decision 2).

## Scenario 1 -- User Story 1: career connection displays for both actors (SC-002)

Demo learner (no auth):

```bash
curl -s "$BACKEND_URL/api/demo-learner"   # note learner_id
curl -s "$BACKEND_URL/api/learners/<demo_learner_id>/mastery-state?subject_id=algebra-1"
```

**Expected**: `MasteryStateResponse.career_connections` has one entry per
`algebra-1` topic with an authored connection, each naming a real career
and a short explanation. A topic with no authored connection (if any) is
simply absent from the list -- not an error, not a placeholder entry
(FR-007).

Guardian, for a real learner they own:

```bash
curl -s -b guardian_cookie.txt "$BACKEND_URL/api/learners/<learner_id>/mastery-state?subject_id=algebra-1"
```

**Expected**: same `career_connections` shape, same content for the same
topics -- confirming one shared computation, not two.

**Negative check**: a *different* guardian's cookie against the same URL
still returns `403` (`require_learner_ownership_if_real()`, unchanged).

## Scenario 2 -- User Story 2: both toggles work end to end (SC-001, SC-003, SC-004)

Demo learner, self-service:

```bash
curl -s "$BACKEND_URL/api/learners/<demo_learner_id>/career-connections-preference"
# {"enabled": true}  -- default-on (research.md Decision 3)
curl -s -X PATCH "$BACKEND_URL/api/learners/<demo_learner_id>/career-connections-preference" \
  -H "Content-Type: application/json" -d '{"enabled": false}'
curl -s "$BACKEND_URL/api/learners/<demo_learner_id>/mastery-state?subject_id=algebra-1"
```

**Expected**: after the `PATCH`, `career_connections` is an empty list
even for topics with authored content (FR-006) -- server-enforced, not a
frontend filter. Re-`PATCH` to `{"enabled": true}` and confirm the list
repopulates.

Guardian, on behalf of a real learner:

```bash
curl -s -b guardian_cookie.txt -X PATCH \
  "$BACKEND_URL/api/learners/<learner_id>/career-connections-preference" \
  -H "Content-Type: application/json" -d '{"enabled": false}'
curl -s -b guardian_cookie.txt "$BACKEND_URL/api/learners/<learner_id>/mastery-state?subject_id=algebra-1"
```

**Expected**: same empty-list effect, scoped to that one learner --
repeat Scenario 1's demo-learner check and confirm the demo learner's own
preference is unaffected (independent per learner, Edge Cases).

**Negative check**: `PATCH` against a real `learner_id` with no session
cookie, or a non-owning guardian's cookie, returns `401`/`403`
respectively -- never silently succeeds.

In the browser: load `/settings` from the demo-learner avatar menu
(`Nav.tsx`), toggle the control, and confirm `/dashboard`'s topic list
reflects the change immediately without a manual reload. Separately, load
`(auth)/guardian/learners`, add a learner, and confirm its own toggle
(next to `JoinRosterForm`/`GuardianLearnerStandards`/`LearnerAssignments`)
behaves the same way for that learner.

## Scenario 3 -- User Story 3: content-artifact validation (FR-002, FR-007)

```bash
python -c "
from src.services.content_artifact.validator import validate_content_artifact, ContentArtifactValidationError
import yaml
raw = yaml.safe_load(open('content/algebra-1/subject.yaml'))
raw['topics'][0]['career_connection'] = {'career': 'Civil Engineer'}  # missing 'description'
try:
    validate_content_artifact(raw)
    print('FAIL: should have raised')
except ContentArtifactValidationError as e:
    print('OK:', e)
"
```

**Expected**: raises, naming the missing `description` field. Repeat by
adding a valid `career_connection` to a `biology` topic (ungraded, no
`grade_bands` at all): **Expected** validates successfully -- confirming
research.md Decision 2's no-grade-gate rule, unlike Standards Alignment's
equivalent check.

## Full regression

```bash
cd backend && pytest
cd ../frontend && npx vitest run
```

**Expected**: all prior milestones' suites pass unchanged (this feature
adds columns/fields and two new routes, modifies no existing behavior).

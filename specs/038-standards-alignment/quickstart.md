# Quickstart: Standards Alignment

**Feature**: `038-standards-alignment` | **Date**: 2026-10-04

Validates all three user stories against a real dev database. One migration ships with this feature (`standards_tags` table) -- `alembic upgrade head` should apply exactly that, no drift beyond it. Reuses `algebra-1` (the only graded subject -- `biology` cannot be tagged at all, research.md Decision 1), a seeded instructor + roster (Milestone 7), and a guardian-owned real (non-demo) learner enrolled in that roster.

## Setup

```bash
cd backend
alembic upgrade head   # applies the new standards_tags table
python scripts/load_content_artifact.py content/algebra-1/subject.yaml
  # re-loads algebra-1 now that its topics carry `standards:` entries (FR-010)
```

Confirm the reload succeeded and populated real codes, not placeholders:

```sql
SELECT topic_id, framework, code, title FROM standards_tags WHERE subject_id = 'algebra-1' ORDER BY topic_id;
```

**Expected**: one or more rows per graded topic with a genuinely corresponding Common Core Math standard; a topic with no genuine match (if any) has zero rows, not a fabricated code (FR-010).

## Scenario 1 -- User Story 1: instructor and guardian both see standards coverage (SC-001, SC-003)

Using the seeded instructor's session cookie, with a roster enrolled in `algebra-1` containing a real, guardian-owned learner who has answered questions until at least one topic's `MasteryState.band == mastered`:

```bash
curl -s -b instructor_cookie.txt "$BACKEND_URL/api/rosters/<roster_id>/dashboard"
```

**Expected**: each `DashboardLearnerOut.standards` entry for that learner shows the mastered topic's standard as `"met"`, naming its real `code`/`title`; a topic the learner has never attempted shows `"not_yet_reached"`; a topic with zero `StandardsTag` rows (if any) is absent from the list entirely (FR-006).

Using the owning guardian's own session cookie instead:

```bash
curl -s -b guardian_cookie.txt "$BACKEND_URL/api/learners/<learner_id>/mastery-state?subject_id=algebra-1"
```

**Expected**: `MasteryStateResponse.standards` is byte-for-byte identical in shape and status to the instructor's view of that same learner above (FR-004's "both views" requirement) -- confirming the shared `coverage.py` function, not two independent computations.

**Negative check**: using a *different* guardian's cookie (one who does not own `<learner_id>`) against the same `mastery-state` URL returns `403` (`require_learner_ownership_if_real()`, unchanged by this feature).

## Scenario 2 -- User Story 2: roster-wide aggregate (SC-001)

With at least two enrolled learners at different mastery bands on the same standards-tagged topic:

```bash
curl -s -b instructor_cookie.txt "$BACKEND_URL/api/rosters/<roster_id>/dashboard"
```

**Expected**: `DashboardOut.standards_summary` contains one entry per distinct `(framework, code)`, each with `met_count` (learners with every tagged topic mastered) out of `total_count` (total enrolled). Manually tally Scenario 1's per-learner `standards` across both learners and confirm it matches `standards_summary` exactly.

Repeat the same request against a roster whose subject has zero `StandardsTag` rows (e.g. a freshly created roster on an as-yet-untagged subject): **Expected** `standards_summary` is an empty list, and the frontend renders no standards section at all -- no empty table, no error (US2 Acceptance Scenario 2).

## Scenario 3 -- User Story 3: content-artifact validation (FR-003, FR-009)

```bash
python -c "
from src.services.content_artifact.validator import validate_content_artifact, ContentArtifactValidationError
import yaml
raw = yaml.safe_load(open('content/algebra-1/subject.yaml'))
raw['topics'][0].setdefault('standards', []).append({'framework': 'Common Core Math'})  # missing 'code'
try:
    validate_content_artifact(raw)
    print('FAIL: should have raised')
except ContentArtifactValidationError as e:
    print('OK:', e)
"
```

**Expected**: raises, naming the missing `code` field. Repeat by adding a `standards` entry to a topic with `grade: null` in a copy of `biology/subject.yaml` (which has no `grade_bands` at all): **Expected** raises, naming FR-003's graded-topic-only rule. Repeat once more by giving two different topics the same `(framework, code)` pair but different `title` text: **Expected** raises, naming FR-012's title-consistency rule.

## Developer toggle check (FR-013)

With `NEXT_PUBLIC_STANDARDS_ALIGNMENT_ENABLED=false` set and the frontend rebuilt/restarted, repeat Scenario 1's browser checks for both the instructor dashboard and the guardian's learner view. **Expected**: no standards section renders anywhere, identical in appearance to a subject with zero `StandardsTag` rows -- even though `GET /api/rosters/<roster_id>/dashboard` and `GET /api/learners/<learner_id>/mastery-state` still return populated `standards`/`standards_summary` fields (confirm via `curl`, same commands as Scenario 1). Unset the variable (or set it to anything other than `"false"`) and confirm both views render again with no backend change needed.

## Accessibility check (FR-011)

Load the instructor dashboard and the guardian's learner-progress page in a browser. For every standard shown, confirm the status is readable with color perception disabled (e.g. a grayscale browser filter) -- each status must still be distinguishable by its text label ("Met" / "In progress" / "Not yet reached"), not by color alone.

## Full regression

```bash
cd backend && python scripts/check_no_standards_literals.py   # SC-002/FR-002 verification
pytest
cd ../frontend && npx vitest run
```

**Expected**: all prior milestones' suites pass unchanged (this feature adds rows/fields, modifies no existing behavior).

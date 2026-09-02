# Quickstart: Validating Prompt Versioning and Regression Testing

**Feature**: `022-prompt-versioning` | **Date**: 2026-09-01

These scenarios validate the feature end to end, once implemented,
without duplicating implementation detail already in `data-model.md` and
`research.md`.

## Prerequisites

- Repo checked out on this feature branch, `uv sync` run in `backend/`,
  `grading-agent/`, and `tutor-agent/`.
- `ANTHROPIC_API_KEY` set locally (needed for scenario 3's live
  generation call; scenarios 1-2 and 4-5 are pure static analysis /
  migration checks, no live model call required).

## Scenario 1 -- Scanner passes against the fully-migrated codebase (US1, FR-003 Acceptance Scenario 1)

```bash
python3 backend/scripts/check_prompt_versioning.py backend/src
python3 backend/scripts/check_prompt_versioning.py grading-agent/src
python3 backend/scripts/check_prompt_versioning.py tutor-agent/src
```

**Expected**: all three exit `0`, reporting zero unversioned inline
prompt strings (data-model.md §1's full table is fully migrated).

## Scenario 2 -- Scanner catches a new unversioned prompt (US1, FR-003 Acceptance Scenario 2 / SC-004)

Temporarily add a new call in `backend/src/agents/assessment_gen/agent.py`:
`LlmAgent(name="x", model=..., instruction="a bare inline instruction")`.

```bash
python3 backend/scripts/check_prompt_versioning.py backend/src
```

**Expected**: exits `1`, citing the exact file and line of the bare
string literal. Revert the temporary change afterward.

## Scenario 3 -- Version-bump enforcement (US1, FR-003 Acceptance Scenario 3 / FR-008)

On a throwaway branch, edit `tutor-agent/src/agent.py`'s `_INSTRUCTION`
content (any wording change) without touching
`TUTOR_INSTRUCTION_VERSION`.

```bash
git checkout -b throwaway-version-bump-test
# edit _INSTRUCTION's text only
python3 backend/scripts/check_prompt_versioning.py tutor-agent/src --base-ref origin/staging
```

**Expected**: exits `1`, citing `tutor-agent/src/agent.py` and naming
`TUTOR_INSTRUCTION_VERSION` as the constant that needed bumping. Bumping
the version constant alongside the content change makes the same
command exit `0`. Delete the throwaway branch afterward.

## Scenario 4 -- Assessment-Generation regression gate (US2, FR-005 / Acceptance Scenario 2)

```bash
cd backend
DATABASE_URL=<any working local Postgres URL> \
ANTHROPIC_API_KEY=<key> \
uv run python scripts/batch_eval_questions.py --fresh
```

**Expected**: generates a small fresh sample of questions from the
Assessment-Generation Agent's real path (no dependency on any
pre-existing `GeneratedQuestion` history) and re-validates each with
`_validate_draft`; exits `0` when all pass. To see it fail, deliberately
weaken `_validate_draft` (e.g. comment out one of its checks) on a
throwaway branch and re-run -- exits `1`, citing the failing question's
id and reason. Revert afterward.

## Scenario 5 -- Grading Agent regression gate already fires on a prompt change (US2, FR-006 / Acceptance Scenario 1)

```bash
git log --oneline -- grading-agent/src/prompt_defense.py
```

Confirms this file's own history (`GRADING_LOGIC_VERSION`'s real
`v1`→`v2` change, spec's Edge Cases). Opening any PR that touches this
file already triggers `grading-agent-tests.yml`'s
`check_grading_agent_eval.py` step today (research.md §6) -- no new
local reproduction needed beyond confirming the existing workflow's
`paths:` filter (`.github/workflows/grading-agent-tests.yml`) still
includes `grading-agent/**`.

## Scenario 6 -- `GeneratedQuestion` records its generation prompt version (US3, FR-009)

```bash
cd backend
uv run alembic upgrade head
```

Generate a question through the normal placement or next-question flow
(e.g. via the existing integration test suite or a manual API call),
then:

```sql
SELECT question_id, generation_prompt_version FROM generated_questions
ORDER BY generated_at DESC LIMIT 1;
```

**Expected**: `generation_prompt_version` is `"v1"` (matching
`GENERATION_PROMPT_VERSION` in `backend/src/agents/assessment_gen/agent.py`
at the time of generation), non-null.

## Scenario 7 -- Milestones 1-11 suites still pass (FR-011 / SC-005)

```bash
(cd backend && uv run pytest -q)
(cd grading-agent && uv run pytest -q)
(cd tutor-agent && uv run pytest -q)
(cd frontend && npm test)
```

**Expected**: same pass rate as immediately before this feature's
changes -- this migration must not alter any prompt's instructional
content (FR-011).

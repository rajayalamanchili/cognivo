---

description: "Task list for Prompt Versioning and Regression Testing"
---

# Tasks: Prompt Versioning and Regression Testing

**Input**: Design documents from `/specs/014-prompt-versioning/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included per this project's established convention (every prior milestone's `plan.md` Testing row commits to `pytest` coverage, and `roadmap.md`'s Definition of Done entries treat test counts as a hard gate, not optional).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3, priority order) so each can be implemented and demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3 -- Polish tasks carry no story label

## Path Conventions

Three existing engine-source trees touched: `backend/`, `grading-agent/`, `tutor-agent/` (plus their per-tree `.github/workflows/*.yml`). No new project or service, per `plan.md`'s Project Structure.

---

## Phase 1: Setup

**No new setup required.** This feature introduces no new dependency, package, or service (research.md §1) -- every task below runs against each tree's already-`uv sync`'d environment. Proceed directly to Phase 3.

---

## Phase 2: Foundational (Blocking Prerequisites)

**No separate foundational phase.** Per spec.md's own stated priority rationale ("a regression gate has nothing to attach to until every prompt is a discoverable, versioned unit"), User Story 1 itself *is* the shared foundation US2 and US3 build on -- there is no additional cross-story infrastructure outside what US1 delivers. US2 and US3's tasks below cite the specific US1 task IDs they depend on directly, the same pattern this project's Milestone 11 tasks.md used for its own US2/US3 depending on US1's `classify.py`.

---

## Phase 3: User Story 1 - Every prompt is a discoverable, versioned artifact (Priority: P1) 🎯 MVP

**Goal**: Every LLM prompt in `backend/src`, `grading-agent/src`, and `tutor-agent/src` is a module-level constant (or template + builder) paired with an explicit `*VERSION*` constant in the same file, and an automated CI-blocking scanner fails any PR that introduces a bare inline prompt or bumps a prompt's content without bumping its paired version.

**Independent Test**: Run the new scanner against the current, fully-migrated codebase (must pass, zero violations) and against a deliberately introduced unversioned inline prompt string (must fail, citing file:line) -- delivers discoverability/auditability value with no dependency on US2.

### Tests for User Story 1 ⚠️

> Write these tests first; confirm they fail before implementing T003/T004 below.

- [X] T001 [P] [US1] Unit tests for unversioned-prompt detection in `backend/tests/unit/evaluation/test_prompt_versioning.py`: (a) `find_violations(Path("backend/src"))` returns `[]` against the current tree (mirrors `test_no_subject_conditionals.py`'s "passes today" assertion), (b) a `tmp_path` fixture containing `LlmAgent(instruction="a bare inline instruction")` is flagged with the exact file:line, (c) a `tmp_path` fixture where `instruction=SOME_CONSTANT` references a module with no `*VERSION*`-named constant is flagged citing the constant's module, not the (already-fine) call site. **Done**: also added a fourth fixture (compliant: `_INSTRUCTION` + a sibling `*VERSION*` constant) confirming the pass case explicitly, not just implied by (a).
- [X] T002 [P] [US1] Unit tests for version-bump enforcement in `backend/tests/unit/evaluation/test_prompt_version_bump.py`, using two in-memory source strings (old/new) rather than a real git repo: (a) prompt content changed, paired `VERSION` constant unchanged -> flagged, (b) prompt content changed, `VERSION` constant also changed -> passes, (c) an unrelated line elsewhere in the same file changed, prompt content and `VERSION` both unchanged -> passes (Edge Case #2, spec.md)

### Implementation for User Story 1

- [X] T003 [US1] Implement `find_violations(src_dir: Path) -> list[str]` in `backend/scripts/check_prompt_versioning.py`: AST-walk every `.py` file under `src_dir`, find each `LlmAgent(...)` call's `instruction=` argument, flag it if it's a raw `ast.Constant`/`ast.JoinedStr` rather than a `Name`/`Name`-rooted `Call` reference, then flag the referenced symbol's defining module if that module has no module-level constant whose name contains `VERSION` (research.md §3) (depends on T001 failing first). **Correction during implementation**: research.md §3's original design said the check should "resolve the referenced symbol back to the module that *defines* it" -- but real code doesn't support that cleanly: Assessment-Gen and the Misconception baseline both pass `instruction` as a *function parameter* through a `_build_agent(model_name, instruction)` helper (not a direct module-level reference), and Grading Agent's real, already-compliant shape has its prompt *template* in `prompt_defense.py` while `GRADING_LOGIC_VERSION` lives in a different file, `agent.py` (the call-site file). True symbol/data-flow resolution across function boundaries would be real interprocedural analysis, well past this project's "simple scanner" bar (`check_no_subject_conditionals.py`'s own precedent). Simplified to a file-level rule instead: the check requires a `*VERSION*`-named constant *anywhere in the same file as the `LlmAgent(...)` call*, not resolved back to wherever the referenced symbol happens to be defined -- this is what Grading Agent already satisfies (`agent.py` has both the call and `GRADING_LOGIC_VERSION`) and what all six newly-migrated files now satisfy by construction (T005-T010 add each VERSION constant to the same file as its `LlmAgent(...)` call).
- [X] T004 [US1] Implement `find_version_bump_violations(old_source: str, new_source: str) -> list[str]` (pure, no git I/O) plus a thin `_git_show(base_ref, path) -> str` wrapper and CLI `main()` (`check_prompt_versioning.py <src_dir> [--base-ref REF]`, exit 1 on any violation from either check, printing file:line/module citations, mirroring `check_no_subject_conditionals.py`'s CLI shape) in the same file (research.md §4) (depends on T002 failing first, T003). **Correction, consistent with T003's**: "prompt content" for bump-detection is any module-level assignment whose target name contains `INSTRUCTION` (matching this codebase's own organically-consistent naming: `_INSTRUCTION`, `_INSTRUCTION_TEMPLATE`, `_MODERATION_INSTRUCTION`), compared as concatenated AST source text old-vs-new; not full interprocedural tracing.
- [X] T005 [P] [US1] Add `GENERATION_PROMPT_VERSION = "v1"` to `backend/src/agents/assessment_gen/agent.py`, colocated with `_INSTRUCTION_TEMPLATE`/`_build_instruction()` (data-model.md §1)
- [X] T006 [P] [US1] Add `TUTOR_INSTRUCTION_VERSION = "v1"` to `tutor-agent/src/agent.py`, colocated with `_INSTRUCTION`. **Correction**: did NOT remove the file's existing docstring note (as originally planned) -- on inspection that note is about a different, still-true design point (why the prompt-injection defense stays inline vs. Grading's separate `prompt_defense.py` module, since `_INSTRUCTION` has no template parameter), not about lacking a version identifier; removing it would have deleted accurate documentation.
- [X] T007 [P] [US1] Add `MODERATION_INSTRUCTION_VERSION = "v1"` to `backend/src/services/grading_client/moderation.py`, colocated with `_INSTRUCTION` (data-model.md §1)
- [X] T008 [P] [US1] Add `GRADING_GUARDRAIL_MODERATION_VERSION = "v1"` to `grading-agent/src/guardrails.py`, colocated with `_MODERATION_INSTRUCTION` (data-model.md §1)
- [X] T009 [P] [US1] Add `TUTOR_GUARDRAIL_MODERATION_VERSION = "v1"` to `tutor-agent/src/guardrails.py`, colocated with `_MODERATION_INSTRUCTION` (data-model.md §1)
- [X] T010 [P] [US1] Add `MISCONCEPTION_BASELINE_PROMPT_VERSION = "v1"` to `backend/src/services/misconception/baseline.py`, colocated with `_INSTRUCTION_TEMPLATE`/`_build_instruction()` (data-model.md §1). Note: `grading-agent/src/agent.py`'s `GRADING_LOGIC_VERSION` already satisfies this pattern -- no task needed for it.
- [X] T011 [US1] Add a `check_prompt_versioning.py backend/src --base-ref origin/${{ github.base_ref }}` step to `.github/workflows/backend-tests.yml`, add `backend/scripts/check_prompt_versioning.py` to its `paths:` filter, and ensure the workflow's `actions/checkout@v4` step fetches enough history (`fetch-depth: 0`, or an explicit `git fetch origin <base_branch>`) for `git merge-base`/`git show <base-ref>` to resolve (research.md §8) (depends on T004, T005, T007, T010). **Correction**: `backend/scripts/check_prompt_versioning.py` already matches this workflow's existing `"backend/**"` path filter -- no separate filter entry needed here (unlike grading-agent/tutor-agent's workflows, where the script lives outside their own trees). Used an explicit `git fetch --depth=1 origin "${{ github.base_ref }}"` step rather than `fetch-depth: 0`, and ran the check via plain `python3` (no `uv run`) since the script is pure stdlib -- runs fast, fails closed before the Neon branch is even created, and needs no dependency install step.
- [X] T012 [P] [US1] Same wiring as T011, scoped to `grading-agent/src`, added to `.github/workflows/grading-agent-tests.yml` -- including adding `backend/scripts/check_prompt_versioning.py` to *this* workflow's own `paths:` filter too (the script lives outside `grading-agent/**`, so without this the workflow won't re-run when the checker itself changes; mirrors how this workflow already lists `backend/scripts/check_grading_agent_eval.py` explicitly) (depends on T004, T008)
- [X] T013 [P] [US1] Same wiring as T011, scoped to `tutor-agent/src`, added to `.github/workflows/tutor-agent-tests.yml` -- including adding `backend/scripts/check_prompt_versioning.py` to *this* workflow's own `paths:` filter too, same reasoning as T012 (depends on T004, T006, T009)

**Checkpoint**: quickstart.md Scenarios 1-3 pass -- the scanner is clean against the fully-migrated tree, catches a new bare inline prompt, and catches a content change with no version bump. **Done 2026-09-01**: `check_prompt_versioning.py backend/src` / `grading-agent/src` / `tutor-agent/src` all report zero violations; 7/7 new unit tests pass; targeted regression run (assessment-gen, misconception-baseline, grading-agent guardrails/agent, tutor-agent guardrails/agent test files) all pass unchanged. Full Milestones 1-11 suite run deferred to Phase 6 (T023) per user direction.

---

## Phase 4: User Story 2 - A regressed prompt change is caught before merge, not after (Priority: P2)

**Goal**: A PR changing the Assessment-Generation or Grading Agent's versioned prompt automatically re-runs that agent's existing quantitative eval suite as a blocking CI step, in the same run that already gates every PR.

**Independent Test**: Deliberately regress a copy of the Grading Agent's scoring prompt (or weaken `_validate_draft` for Assessment-Generation) on a throwaway branch, open a PR, and confirm the relevant existing eval gate now blocks it automatically.

### Tests for User Story 2

- [X] T014 [P] [US2] Integration tests in `backend/tests/integration/evaluation/test_batch_eval_questions_fresh.py`: (a) `batch_eval_questions.py --fresh` generates a small sample via the real Assessment-Generation path (mocking the underlying model call the same way existing tests mock `_run_agent_once`, per `backend-tests.yml`'s own comment) and re-validates it with `_validate_draft`, exiting 0 on success and 1 (citing the failing question) when `_validate_draft` is monkeypatched to fail; (b) FR-007's fail-closed case -- when the generation call itself raises (mock it to raise, simulating a missing API key or model error), the script prints a clean `FAIL:` message and exits 1, it does not crash with an unhandled traceback or silently exit 0

### Implementation for User Story 2

- [X] T015 [US2] Add a `--fresh` CLI flag to `backend/scripts/batch_eval_questions.py`: instead of querying persisted `GeneratedQuestion` rows, calls the Assessment-Generation Agent's real generation path directly for a small fixed sample across this project's two subject content artifacts, then re-validates with the existing `_validate_draft` (default DB-sampling behavior stays unchanged for local/manual use). Wrap the generation call in a try/except that converts any failure (missing credentials, model/network error) into a clean `FAIL:` message and exit 1 -- mirroring `check_grading_agent_eval.py`'s `_run_eval_runner` try/except, satisfying FR-007's fail-closed requirement (research.md §5) (depends on T014 failing first). **Done**: reads content artifacts directly via `load_content_artifact_file()` (no DB session needed at all), uses an `InMemorySessionService`, defaults to 3 topics/subject. Verified end-to-end with a real (non-mocked) run: `6/6 passed internal-consistency re-validation` against both real content artifacts and a real Claude Sonnet call.
- [X] T016 [US2] Add `batch_eval_questions.py --fresh` as a new blocking step in `.github/workflows/backend-tests.yml`, with `ANTHROPIC_API_KEY` supplied the same way `grading-agent-tests.yml` already supplies it to `check_grading_agent_eval.py` (research.md §5, §8) (depends on T015). Placed right after `uv sync`, before the ephemeral Neon branch is even created -- this gate needs no database at all.
- [X] T017 [US2] Confirm `.github/workflows/grading-agent-tests.yml`'s existing `paths: ["grading-agent/**", ...]` filter and `check_grading_agent_eval.py` step already gate any change to `grading-agent/src/prompt_defense.py`/`agent.py` (research.md §6) -- no code change; add a one-line comment in the workflow noting this doubles as FR-006's trigger-condition requirement

**Checkpoint**: quickstart.md Scenarios 4-5 pass -- a weakened Assessment-Gen validation is caught by the new `--fresh` gate, and the Grading Agent's existing gate is confirmed to already fire on a prompt change. **Done 2026-09-01**: 3/3 new tests pass (success, validation-failure, and fail-closed-on-raise cases); real end-to-end `--fresh` run confirmed above; both workflow YAML files parse.

---

## Phase 5: User Story 3 - Every prompt-driven decision in the audit log names its prompt version (Priority: P3)

**Goal**: Every `GeneratedQuestion` record stores the exact prompt version that produced it, matching the existing `grading_logic_version`/`classifier_version` pattern.

**Independent Test**: Generate a question after this story ships and confirm its stored record includes a version field matching the Assessment-Generation prompt's current version identifier.

### Tests for User Story 3

- [X] T018 [P] [US3] Integration test in `backend/tests/integration/test_generated_question_prompt_version.py`: generating a question via the placement or next-question flow persists a `generation_prompt_version` column value equal to `GENERATION_PROMPT_VERSION`, non-null

### Implementation for User Story 3

- [X] T019 [US3] Add `generation_prompt_version: Mapped[str | None]` (nullable, no default -- `None` reserved for pre-milestone rows; every new-row code path sets a real value) to `GeneratedQuestion` in `backend/src/models/generated_question.py` (data-model.md §3) (depends on T005, T018 failing first)
- [X] T020 [US3] Alembic migration in `backend/alembic/versions/` adding the `generation_prompt_version` column (nullable, no default, no backfill of existing rows) to `generated_questions` (data-model.md §3) -- nullable is required, not optional, since `backend-tests.yml`'s ephemeral CI branch clones `staging`'s real accumulated data (not an empty DB), and a `NOT NULL` column with no default cannot be added to a non-empty Postgres table (depends on T019). **Done**: `be66baa35493_generated_question_prompt_version.py`, revises `c80b05244e1c`.
- [X] T021 [P] [US3] Pass `generation_prompt_version=GENERATION_PROMPT_VERSION` at the `GeneratedQuestion(...)` construction in `backend/src/api/routes/questions.py:100` (depends on T020)
- [X] T022 [P] [US3] Pass `generation_prompt_version=GENERATION_PROMPT_VERSION` at the `GeneratedQuestion(...)` construction in `backend/src/api/routes/placement.py:79` (depends on T020). **Correction, found during implementation**: a third real construction site exists that neither the spec's inventory nor this task list originally caught -- `backend/src/services/quiz/session.py:218`'s `persist_quiz_question()`, shared by both the quiz (spec 005) and quiz-assignment (spec 011) flows. Updated it too, for the same reason T021/T022 exist: every code path that creates a `GeneratedQuestion` must set a real version (FR-009's "every" is not scoped to only the two routes originally found).

**Checkpoint**: quickstart.md Scenario 6 passes -- a freshly generated question's row carries the correct version. **Done 2026-09-01**: integration test passes against a real (migrated) schema; targeted quiz/placement/next-question regression tests (17 + 5 + prior US1 targeted runs) all pass; one pre-existing, documented, unrelated flake reproduced and confirmed not a regression (`test_placement_api.py::test_submit_placement_response_shape_and_unknown_topics`, the known Neon/PgBouncer OID-cache-churn issue, roadmap.md's Milestone 8 entry) -- passes cleanly as part of its full test file (5/5).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and the end-to-end validation that only makes sense once every story above is done.

- [X] T023 [P] Run Milestones 1-11's full `backend`, `grading-agent`, `tutor-agent`, and `frontend` test suites; confirm the same pass rate as immediately before this feature's changes (FR-011/SC-005). **Done 2026-09-01**: `grading-agent` 23/23, `tutor-agent` 26/26, `frontend` 64/64 -- all clean on the first run. `backend`'s first full run (1562s) showed 398 passed/1 failed/17 errors, all clustered in `test_quiz_assignment_cancellation.py`/`test_quiz_assignment_create.py` with a generic `OperationalError` -- investigated rather than dismissed, since those files exercise `persist_quiz_question()` (the third `GeneratedQuestion` construction site this milestone touched, T021/T022's correction). Root cause found: that run overlapped in time with a separate, self-inflicted concurrent pytest invocation against the same dev DB (both doing session-scoped schema drop/create churn), which produced a real Postgres deadlock (`DROP TABLE tutoring_sessions` blocked by/blocking another process) -- not a code regression. Confirmed by re-running both flagged files alone: 13/13 passed cleanly (117s). Full backend suite not re-run in full afterward (would cost another ~25 min for a result already established file-by-file); the two directly-implicated files plus every touched-file's targeted run (Phase 3/4/5 checkpoints) together cover the same ground the full run would re-confirm.
- [X] T024 [P] Run `backend/scripts/check_no_subject_conditionals.py`; confirm this feature's new/changed files introduce zero subject-id-keyed conditionals (Constitution Principle III). **Done**: `OK: no subject-id-keyed conditionals found in backend/src for ['algebra-1', 'biology']`.
- [X] T025 Run `quickstart.md`'s full validation scenarios (1-7) end to end against a live/dev environment (depends on T011-T013, T016-T017, T021-T022). **Done**: Scenario 1 (scanner clean on all three trees) re-verified; Scenario 2/3 (7/7 unit tests) re-verified; Scenario 4 re-run for real (non-mocked): `6/6 passed internal-consistency re-validation` against a real Claude Sonnet call; Scenario 5 (Grading Agent's `paths:` filter already includes `grading-agent/**`) re-verified; Scenario 6 (`test_generated_question_prompt_version.py`) passed in isolation; Scenario 7 covered by T023 above.
- [X] T026 Update `roadmap.md`'s Milestone 12 status line to reflect implementation completion (depends on T025)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: Not applicable -- see Phase 1/2 notes above.
- **User Story 1 (P1)**: No dependency on other stories -- start immediately.
- **User Story 2 (P2)**: Depends on US1's `GENERATION_PROMPT_VERSION` (T005) existing conceptually (the prompt it's gating is now a versioned artifact) but not on any other US1 task -- can start once T005 lands; does not need T006-T013 to be done first.
- **User Story 3 (P3)**: Depends on US1's `GENERATION_PROMPT_VERSION` (T005) directly (T019 imports it) -- can start once T005 lands, independent of US2.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests are written first and must fail before the corresponding implementation task.
- US1: T003 (scanner core) before T004 (bump check + CLI, same file); the six per-prompt version-constant tasks (T005-T010) are independent of each other and of T003/T004, but the CI-wiring tasks (T011-T013) depend on both the script existing (T004) and that workflow's own tree being fully migrated (e.g. T011 needs T005/T007/T010, the three `backend/src` prompts).
- US2: T015 (script flag) before T016 (CI wiring); T017 is a verification-only task, no code dependency.
- US3: T019 (model column) before T020 (migration) before T021/T022 (call-site updates, parallel -- different files).

### Parallel Opportunities

- T001 and T002 (distinct test files) in parallel.
- T005-T010 (six distinct files, no shared state) in parallel once T003/T004 exist to test against.
- T012 and T013 (distinct workflow files) in parallel with each other, and with T011.
- T014 (US2 test) in parallel with any US1 task once US1's T005 has landed.
- T018 (US3 test) in parallel with US2's tasks -- distinct files, both only depend on US1's T005.
- T021 and T022 (distinct files) in parallel.
- T023 and T024 (distinct scopes) in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch both US1 test files together:
Task: "Unit tests for unversioned-prompt detection in backend/tests/unit/evaluation/test_prompt_versioning.py"
Task: "Unit tests for version-bump enforcement in backend/tests/unit/evaluation/test_prompt_version_bump.py"

# Once the scanner (T003/T004) exists, migrate all six remaining prompts together:
Task: "Add GENERATION_PROMPT_VERSION to backend/src/agents/assessment_gen/agent.py"
Task: "Add TUTOR_INSTRUCTION_VERSION to tutor-agent/src/agent.py"
Task: "Add MODERATION_INSTRUCTION_VERSION to backend/src/services/grading_client/moderation.py"
Task: "Add GRADING_GUARDRAIL_MODERATION_VERSION to grading-agent/src/guardrails.py"
Task: "Add TUTOR_GUARDRAIL_MODERATION_VERSION to tutor-agent/src/guardrails.py"
Task: "Add MISCONCEPTION_BASELINE_PROMPT_VERSION to backend/src/services/misconception/baseline.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3: User Story 1.
2. **STOP and VALIDATE**: the scanner passes against the fully-migrated repo, fails against a deliberately introduced unversioned prompt, and fails against a content change with no version bump (quickstart.md Scenarios 1-3).
3. This alone delivers real value (discoverability, auditability) and is this milestone's foundation -- US2/US3 have nothing to attach to before this.

### Incremental Delivery

1. User Story 1 -> test independently -> every prompt is now a discoverable, versioned, CI-enforced artifact (MVP).
2. Add User Story 2 -> test independently -> a regressed Assessment-Generation or Grading prompt change is caught before merge.
3. Add User Story 3 -> test independently -> every generated question traces to the exact prompt version that produced it.
4. Polish -> regression safety across Milestones 1-11, full quickstart run, roadmap status update.

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.

# Tasks: Privacy & Retention Spec -- the Real Learner Data Gate

**Input**: Design documents from `/specs/009-privacy-retention/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md, data-classification.md

**Tests**: Included -- FR-001/FR-008's gate script is exactly the kind
of behavior a unit test should lock down (a static-analysis rule that
must keep working as new models are added), not optional polish.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

No tasks. This spec reuses the existing `backend/` project structure
unchanged (`backend/scripts/`, `backend/tests/unit/`,
`.github/workflows/backend-tests.yml` already exist) -- no new project,
dependency, or scaffolding is needed (plan.md's Technical Context: no
new dependencies).

## Phase 2: Foundational

No tasks. Nothing in this spec blocks on shared infrastructure beyond
what already exists.

---

## Phase 3: User Story 1 - No real learner or instructor data can exist before this spec is approved (Priority: P1) 🎯 MVP

**Goal**: An automated, CI-enforced check fails the moment any code
path could create or persist a real (non-`is_demo`) learner or
instructor account, before this spec's other requirements are
satisfiable.

**Independent Test**: Run the gate script against the current codebase
(passes -- only `DemoLearnerProfile` exists, already `is_demo=True`);
add a synthetic account-shaped model without `is_demo` and re-run (must
fail).

### Tests for User Story 1

- [X] T001 [US1] Unit test: gate script exits `0` against the
      current `backend/src/models/` (no violations) in
      `backend/tests/unit/test_check_no_real_account_path.py`
- [X] T002 [US1] Unit test: gate script exits non-zero and names
      the offending class/table when a fixture model (a `Base`
      subclass named e.g. `Student`/`Instructor`/`Account` with no
      `is_demo` column) is present, using a temporary fixture directory
      the test constructs rather than modifying real source, in
      `backend/tests/unit/test_check_no_real_account_path.py` (same
      file as T001, no dependency on it)
- [X] T003 [US1] Unit test: gate script exits `0` once the same fixture
      model from T002 gains a non-nullable `is_demo` column -- confirms
      `is_demo` presence, not the table name alone, is the actual
      discriminating condition (quickstart.md scenario 3), in
      `backend/tests/unit/test_check_no_real_account_path.py` (depends
      on T002's fixture existing first)

### Implementation for User Story 1

- [X] T004 [US1] Implement `backend/scripts/check_no_real_account_path.py`
      (research.md §1): parse every `.py` file under
      `backend/src/models/` with `ast`, find every class whose bases
      include `Base` (`src/models/base.py`), and fail with a clear
      per-violation message if any such class's `__tablename__`
      contains `learner`, `student`, `instructor`, `teacher`,
      `guardian`, `parent`, `account`, or `user`
      (case-insensitive) and the class has no `is_demo` column that is
      non-nullable -- recognizing non-nullability from *either* an
      explicit `nullable=False` keyword in a `mapped_column(...)` call
      *or* a `Mapped[bool]` annotation with no `Optional`/`| None`
      wrapper (SQLAlchemy 2.0's type-inferred non-nullability, e.g.
      `DemoLearnerProfile.is_demo`'s own style), so a model correctly
      relying on type inference doesn't false-positive (research.md
      §1's revised heuristic). Exit `0` if none found, exit `1` with
      all violations listed otherwise. Depends on T001-T003 existing
      first (tests written before implementation, per this project's
      convention).
- [X] T005 [US1] Wire `check_no_real_account_path.py` into CI (depends
      on T004). **Revised during implementation** (research.md §2): no
      new workflow step needed -- `backend/tests/unit/
      test_check_no_real_account_path.py` (T001-T003) imports
      `find_violations` directly, the same pattern
      `test_no_subject_conditionals.py` already uses for
      `check_no_subject_conditionals.py`, so `backend-tests.yml`'s
      existing `pytest` step (`pyproject.toml`'s `testpaths = ["tests"]`)
      already runs it on every PR with no workflow file change at all.

**Checkpoint**: User Story 1 is fully functional and independently
verifiable -- `check_no_real_account_path.py` passes today and blocks
any future PR that introduces a real-account-shaped model without
`is_demo`.

---

## Phase 4: User Story 2 - A real learner's or instructor's data can be deleted on request (Priority: P1)

**No tasks in this spec.** FR-004/FR-005's deletion cascade has no real
account, roster, or activity data of its own to operate on yet -- there
is nothing to delete until Milestone 7 proper's `RealLearnerAccount`/
`RealInstructorAccount`/`ClassroomRoster` tables (data-model.md) exist.
Building a deletion pathway against tables that don't exist, or against
`DemoLearnerProfile` as a stand-in, would be speculative code with no
real caller -- this project's own working norms explicitly avoid that
(CLAUDE.md: "Don't design for hypothetical future requirements").
FR-004/FR-005 stand as this spec's *requirements*; Milestone 7 proper's
own tasks.md is where they become implementation tasks, using
`data-model.md`'s `DeletionRequest` entity and this user story's
Acceptance Scenarios as its acceptance bar.

---

## Phase 5: User Story 3 - An instructor can only ever see their own roster's data (Priority: P1)

**No tasks in this spec.** FR-006's cross-tenant access-control
scoping has no second tenant to scope against -- there is exactly one
learner concept in the system today (the single seeded
`DemoLearnerProfile`) and zero instructors. This user story's
Independent Test (two instructors, non-overlapping rosters) is
unimplementable until Milestone 7 proper's `RealInstructorAccount`/
`ClassroomRoster` tables exist. Deferred to that spec's tasks.md, using
this user story's Acceptance Scenarios as its acceptance bar.

---

## Phase 6: User Story 4 - A demo account is always, unmistakably distinguishable from a real account (Priority: P2)

**No tasks in this spec.** FR-007/FR-008's demo-vs-real distinguishability
requires a real sign-up/login flow to distinguish the demo path *from*
-- Milestone 1's `DemoLearnerProfile` already satisfies FR-007's
`is_demo`/dedicated-entry-point requirements in isolation (there is no
real sign-up flow yet for it to be confused with), and FR-008's
automated check (no real-sign-up-reachable account can have
`is_demo: true`) is subsumed by this spec's own gate script (T004):
today, no sign-up-reachable path creates *any* account at all, real or
otherwise, so the check trivially holds. A dedicated FR-008 check
distinct from T004's gate becomes meaningful only once Milestone 7
proper's real sign-up flow exists -- deferred to that spec's tasks.md.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T006 [P] Review `data-classification.md` against `data-model.md`
      -- confirm every non-key field in each of the six entities has a
      row with a non-empty retention period and deletion trigger
      (quickstart.md scenario 5)
- [X] T007 Run `quickstart.md`'s scenarios 1-4 and record results.
      Scenarios 1-3 run directly as the automated pytest tests
      (T001-T003), a stronger check than the manual quickstart process
      they describe. Scenario 4 (CI wiring) was **not** verified via an
      actual throwaway PR -- confirmed instead by configuration
      inspection: `pyproject.toml`'s `testpaths = ["tests"]` means
      `backend-tests.yml`'s existing `pytest` step already discovers
      `test_check_no_real_account_path.py`, the same mechanism already
      proven live for `check_no_subject_conditionals.py`
      (`test_no_subject_conditionals.py`). Reconciled 2026-08-23 after
      `claude-review` on PR #27 correctly flagged this line's original
      wording as claiming a throwaway-PR verification that was never
      actually performed.
- [X] T008 [P] Regression check: run `backend/tests/` (excluding
      `grading-agent/tests/`, independent per Constitution Principle
      VI) and confirm the full suite still passes unmodified after
      T004/T005's changes
- [X] T009 Update `roadmap.md`'s Milestone 7 status line to record this
      spec (009-privacy-retention) as approved, per this milestone's
      own Definition of Done requiring it before the rest of Milestone
      7's work begins

## Dependencies & Execution Order

- **Setup / Foundational**: No tasks -- nothing blocks Phase 3.
- **User Story 1 (T001-T005)**: The only implementable story in this
  spec. T001-T003 (tests) before T004 (implementation) before T005
  (CI wiring), per this project's test-first convention.
- **User Stories 2, 3, 4**: No tasks -- explicitly deferred to
  Milestone 7 proper, which depends on this spec being approved first
  (spec.md's own framing, roadmap.md's Milestone 7 Definition of Done).
- **Polish (T006-T009)**: Depends on T001-T005 being complete.

## Parallel Example: Polish Phase

T001-T003 share one file and (per the corrected dependency above) T003
depends on T002 -- genuinely sequential, not a parallel example. T006
and T008 are the real parallel opportunity in this spec: different
files, no dependency on each other.

```bash
Task: "Review data-classification.md against data-model.md"
Task: "Run backend/tests/ regression check"
```

## Implementation Strategy

### MVP = User Story 1 (the only story this spec implements)

1. T001-T003: write the three unit tests (they fail -- the script
   doesn't exist yet).
2. T004: implement the gate script until all three tests pass.
3. T005: wire it into CI.
4. **STOP and VALIDATE**: `quickstart.md` scenarios 1-4.
5. T006-T009: Polish.

There is no "incremental delivery across stories" for this spec --
User Story 1 *is* the entire implementable scope; Stories 2-4 are
requirements handed to Milestone 7 proper, not phases of this spec's
own rollout.

# Quickstart: Sequencing Evaluation Harness

**Feature**: `006-personalization-eval` | **Date**: 2026-08-16

Validates that the evaluation harness produces a real comparison report
and that the live report page shows it. See `data-model.md` for entity
detail and `contracts/api.md` for the report endpoint's exact shape. Run
against a **local/dev** database, not `staging`/production
(research.md §6).

## Prerequisites

- Same as `specs/001-domain-agnostic-core/quickstart.md` (Postgres,
  both content artifacts loaded) -- this feature adds no migrations, only
  a new script and one new read-only endpoint/route.
- Backend and frontend running locally per that same quickstart's Run
  Locally section.

## Validation scenario: run the harness and confirm the result

Maps directly to spec.md User Stories 1-4's Acceptance Scenarios.

1. **Run the harness for one subject/profile** (User Story 1)
   `python -m src.services.evaluation.run_harness --subject algebra-1 --profile cold-start --seed 1`
   → Confirm it prints/writes a per-condition questions-to-mastery
   summary, and that the `sequencing` condition's mean is lower than the
   `random` condition's mean (SC-001).

2. **Full run across all profiles and both subjects** (User Story 2)
   `python -m src.services.evaluation.run_harness --seed 20260816`
   (no `--subject`/`--profile` filters -- runs the full matrix per
   research.md §10)
   → Confirm `backend/evaluation/reports/latest.json` is written with one
   `breakdowns` entry per (profile, subject) pair (8 entries) plus an
   `aggregate` entry.
   → Confirm the `sequencing` condition beats `random` in *every*
   individual `breakdowns` entry, not only in `aggregate` (SC-001).

3. **Fixed-order baseline present** (User Story 3)
   → In the same report, confirm every `breakdowns` entry and `aggregate`
   include a `fixed_order` condition alongside `sequencing`/`random`, and
   that `aggregate.sequencing.mean <= aggregate.fixed_order.mean` (SC-002).

4. **Reproducibility check** (FR-007, SC-003)
   Re-run step 2 with the identical `--seed 20260816` → confirm the new
   `latest.json` is byte-identical to the previous one (aside from
   `run_timestamp`).

5. **Code-path-fidelity check** (FR-008, SC-004)
   Inspect `src/services/evaluation/` → confirm the `sequencing`
   condition's topic choice is produced by calling
   `src.agents.sequencing.agent.select_next_topic` directly (an import,
   not a re-derivation of its eligibility/tie-break logic).

6. **No real-data / cleanup check** (FR-009, FR-014, SC-006)
   Before and after running step 2:
   - Query `SELECT count(*) FROM demo_learner_profiles WHERE is_demo = false`
     (and the equivalent for any pre-existing real `assessment_events` rows)
     → confirm both are unchanged (real data untouched).
   - Confirm no `eval-harness-*` rows remain in `demo_learner_profiles`,
     `mastery_states`, or `assessment_events` after the run completes
     (synthetic-data cleanup, research.md §6-§7).
   - During the run, confirm `assessment_events` rows of type
     `next_topic_selected` are being written for the `sequencing`
     condition's decisions (FR-014) -- absent for `random`/`fixed_order`.

7. **Publish and view the report page** (User Story 4)
   Commit `backend/evaluation/reports/latest.json` (as an engineer would
   to publish -- Clarifications: manual/on-demand), then:
   - `GET /api/evaluation/report` → confirm `published: true` and the
     same figures as `latest.json` (contracts/api.md).
   - Load the report page in a browser → confirm it's reachable from the
     main navigation without needing a direct URL, shows the headline
     Sequencing-vs-random result in plain language within one screen
     (SC-005), and requires no login.

8. **Unpublished-state check** (User Story 4 Acceptance Scenario 2)
   Temporarily rename/remove `latest.json` → confirm
   `GET /api/evaluation/report` returns `{"published": false}` and the
   report page states clearly that no evaluation has run yet, rather than
   showing blank or fabricated figures. Restore the file afterward.

9. **Non-convergence handling check** (Edge Cases)
   Run the harness with a deliberately tiny budget (e.g.
   `--max-questions-per-topic 1`) for one profile/subject → confirm the
   resulting `breakdowns` entry shows a non-zero `non_converged_count`
   and that its `mean`/`median` are computed only over converged
   learners (not skewed by excluding non-convergers silently from the
   count).

10. **Subject-agnosticism check** (Constitution Principle III)
    `python backend/scripts/check_no_subject_conditionals.py` → confirm
    it still passes after the harness code is added (research.md §11).

11. **Regression check** (SC-007)
    Run the full backend test suite (`pytest` from `backend/`), including
    Milestone 1's and Milestone 2's existing test directories → confirm
    all still pass; this feature's changes must not regress prior
    milestones.

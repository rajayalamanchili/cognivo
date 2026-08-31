# Implementation Plan: Fine-Tuned Misconception Classifier

**Branch**: `020-misconception-classifier` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-misconception-classifier/spec.md`

## Summary

Adds a per-subject misconception classifier -- a Voyage `voyage-3`
embedding of a learner's incorrect free-text answers fed into a small,
offline-trained `scikit-learn` classifier -- that names a specific,
content-artifact-authored misconception pattern (e.g. "confuses X with
Y") instead of a bare correctness count. Classification runs on a new
Vercel Cron schedule, never inline in a request, and its result is
written as a new `AssessmentEvent` type
(`misconception_classified`) the existing Recommendation Agent reads
at report-build time. The Recommendation Agent's `WeakAreaFlag` gains
one new, optional, evidence-cited field; every other field and the
agent's own logic is untouched. If no classification exists (no
taxonomy, no trained model, insufficient evidence, or low confidence),
the report is produced exactly as Milestone 2 already guarantees --
graceful degradation is structural, not a try/except wrapper. The
classifier's accuracy is measured against a hand-labeled validation set
and reported against a prompted-only baseline, honestly, whether or not
it wins.

## Technical Context

**Language/Version**: Python 3.12, unchanged (existing `backend/`).
TypeScript/Next.js frontend gains one new optional response field to
render; no new frontend logic beyond displaying it. No new deployment
unit -- everything in this feature lives inside the existing `backend/`
project (research.md §10: no new agent, no new A2A service).

**Primary Dependencies**: Adds `scikit-learn` to `backend/` (research.md
§1) -- the only new dependency this feature introduces. Reuses
Voyage AI's `voyage-3` embedding call already locked for the Tutor
Agent (`tech-stack.md`, Milestone 9) via LiteLLM's `embedding()`
function -- no new embeddings provider or credential. Reuses the
existing ADK `LlmAgent`/`LiteLlm` (Claude Haiku default) pattern for
the prompted-only baseline (research.md §2), mirroring
`grading-agent/src/guardrails.py`'s `check_moderation()`.

**Storage**: PostgreSQL via Neon, same database as every other
milestone -- no new tables (research.md §4). One enum-value addition
(`assessment_event_type` gains `misconception_classified`), via the
same `ALTER TYPE ... ADD VALUE` Alembic technique this project already
uses for every prior enum extension. The trained classifier artifact
itself is a checked-in, versioned file per subject
(`backend/misconception_models/<subject_id>/<version>/classifier.joblib`,
research.md §8), not a database row.

**Testing**: `pytest` (`backend/tests/{unit,integration}/`) for the
classifier's read path (evidence-threshold gating, confidence gating,
graceful-`null` behavior, the new `WeakAreaFlag.misconception` field),
the new cron route's auth (mirroring `test_cron_reset_demo_data.py`'s
existing bearer-secret tests, if present, or the same pattern this
project uses for every `Authorization: Bearer` route), and a new
`backend/scripts/check_misconception_classifier_eval.py` (research.md
§7), extending Milestone 6's ground-truth-eval-gate precedent. This
feature's model *training* code gets its own narrow unit coverage
(the offline `train_misconception_classifier.py` script), not a full
ML test suite -- consistent with this project's existing "the smallest
runnable check for non-trivial logic" pattern.

**Target Platform**: The existing Vercel Services project
(`backend/`+`frontend/`) only -- no new deployment unit. The
classification job runs as a new Vercel Cron entry against the
existing `backend` service (research.md §3), the same mechanism the
existing demo-data-reset cron already uses.

**Project Type**: Web service monorepo, unchanged deployable-unit count
(`backend/`, `frontend/`, `grading-agent/`, `tutor-agent/`) -- this
feature adds no fifth unit.

**Performance Goals**: No new request-path latency budget -- the
Recommendation Agent's read of a `misconception_classified` event is a
single indexed-by-recency query, the same shape as its existing
`EvidenceCitation` lookups, adding no measurable latency to
`GET /api/learners/{learner_id}/recommendations` (contracts/api.md).
The classification cron job itself has no learner-facing latency
requirement -- it runs on a schedule, not in response to a request
(research.md §3).

**Constraints**: Classification and training MUST NOT run inline in
any request path (research.md §3, spec.md FR-006) -- this is a hard
constraint, not a preference, since Vercel Functions have no
persistent background process to fall back on if an inline call runs
long (`tech-stack.md`'s Deployment target section). The classifier
artifact MUST be read-only at request/job time (research.md §8) --
training is an offline, manually-triggered step, never a
runtime-mutating one.

**Scale/Scope**: Two seeded subjects (`algebra-1`, `biology`), each
with at least one topic's misconceptions authored (research.md §9),
proving Constitution Principle III continues to hold for a second
subject. Single-learner classification granularity (`learner_id`,
`subject_id`, `topic_id`), same solo-learner-then-instructor-aggregated
scope every prior milestone has used.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1
design below.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | The BKT mastery model is completely untouched -- this feature reads `AssessmentEvent` history and writes a new, separate event type; it never touches `MasteryState` or the Sequencing Agent's tool call (research.md §4). | PASS |
| II. Generated content graded against a rubric | Free-text grading itself (Milestone 6) is unmodified. This feature's own risk is analogous -- a misconception label could be an ungrounded LLM guess -- addressed the same way: every label MUST cite specific evidence events (FR-004, data-model.md's `MisconceptionEnrichment.evidence`), never shown unsupported. | PASS |
| III. One engine, many subjects | The misconception taxonomy is entirely content-artifact-owned (`subject.yaml`'s new `misconceptions` field, research.md §9) -- zero engine-level subject conditionals, covered by the existing `check_no_subject_conditionals.py` scan. Both seeded subjects opt in. | PASS |
| IV. Agent boundaries reflect real responsibility | No new agent boundary is introduced (research.md §10) -- the classifier is a plain service module, not a distinct agent with its own evaluation criteria/failure modes. It's consumed by the existing Recommendation Agent exactly the way `next_step.py` already is, not split out for its own sake. | PASS |
| V. Logged and explainable | Every classification decision is a new, distinct `AssessmentEvent` (`misconception_classified`, data-model.md) citing the specific evidence events that produced it -- "why was this misconception flagged" has a real, traceable answer, same bar as every other pedagogical decision in this project. | PASS |
| VI. A2A justified by concrete need | Not applicable -- no A2A service is introduced (research.md §10); the Constitution Check for this principle is trivially satisfied by not invoking it where no concrete need exists. | PASS |
| VII. Spec before code | This plan follows the approved spec.md (checklist passed with zero `NEEDS CLARIFICATION` markers). | PASS |
| VIII. No real learner data | Introduces no new data-collection surface -- classifier training/inference operates only on `AssessmentEvent` rows already covered by Milestone 7's privacy/retention rules (FR-009, spec.md's Assumptions); no new retention policy needed. | PASS |
| IX. Deployable and demoable | The classifier's offline-cron-job shape (research.md §3) and read-only bundled-artifact storage (research.md §8) are both direct, deliberate consequences of Vercel's stateless execution model, not afterthoughts -- no new deployment unit, no assumed persistent process. | PASS |
| X. Staged release discipline | Feature branch `020-misconception-classifier` -> PR into `staging`, per existing workflow. No new Vercel project needs a branch-deployment mapping -- this feature ships inside the existing `backend` service. | PASS (process, not a design gate) |

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/013-misconception-classifier/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── api.md            # Phase 1 output
└── tasks.md               # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── enums.py                        # + AssessmentEventType.MISCONCEPTION_CLASSIFIED
│   ├── services/
│   │   ├── misconception/                  # NEW -- classification service
│   │   │   ├── __init__.py
│   │   │   ├── embed.py                    # NEW: Voyage voyage-3 call (research.md §1),
│   │   │   │                                 # reuses tutor_agent_client's existing embedding
│   │   │   │                                 # helper rather than a second implementation
│   │   │   ├── classify.py                 # NEW: loads classifier.joblib, applies evidence/
│   │   │   │                                 # confidence thresholds (research.md §5), writes
│   │   │   │                                 # misconception_classified events
│   │   │   └── baseline.py                 # NEW: prompted-only ADK LlmAgent call
│   │   │                                      # (research.md §2), used by the eval script only
│   │   └── recommendation/
│   │       └── weak_area.py                # + reads latest misconception_classified event,
│   │                                          # attaches MisconceptionEnrichment (data-model.md)
│   ├── agents/
│   │   └── recommendation/
│   │       └── agent.py                    # + WeakAreaFlag.misconception field (additive)
│   └── api/routes/
│       └── cron.py                         # + classify_misconceptions_route (contracts/api.md),
│                                              # identical auth pattern to reset-demo-data
├── scripts/
│   ├── train_misconception_classifier.py   # NEW: offline training (research.md §1/§8),
│   │                                          # never run at request/deploy time
│   └── check_misconception_classifier_eval.py  # NEW: eval gate (research.md §7)
├── misconception_models/                   # NEW: checked-in trained artifacts
│   ├── algebra-1/v1/classifier.joblib
│   └── biology/v1/classifier.joblib
├── evaluation/
│   └── misconception_ground_truth.jsonl    # NEW: hand-labeled validation set (research.md §6)
├── alembic/versions/
│   └── <new>_misconception_classified_event_type.py  # NEW: one ALTER TYPE ADD VALUE
└── content/
    ├── algebra-1/subject.yaml              # + misconceptions on >=1 topic (research.md §9)
    └── biology/subject.yaml                # + misconceptions on >=1 topic

frontend/
├── src/
│   └── components/
│       └── WeakAreaSection.tsx             # + renders misconception.description/evidence
│                                              # when present, unchanged when null (existing
│                                              # component; already renders flag.topic_id/
│                                              # p_mastery/next_step from RecommendationsResponse)
└── tests/
    └── (unit test files added at /speckit-tasks time)

vercel.json                                 # + crons entry for classify-misconceptions
```

**Structure Decision**: Extends the existing `backend/` monorepo only --
no new top-level project. Follows the established
`services/<name>/` (orchestration) + `api/routes/<name>.py` (thin HTTP
layer) split, adding `services/misconception/` alongside the existing
`services/recommendation/`, `services/grading_client/`,
`services/tutor_agent_client/` precedent. The cron route is added to
the existing `cron.py` module (not a new file) since it's one more
scheduled endpoint of the same shape, not a new subsystem of routes.

## Post-Design Constitution Check

*Re-checked after Phase 1 (data-model.md, contracts/api.md,
quickstart.md).* Phase 1 confirmed two decisions beyond the Phase 0
table above: (1) the "Misconception Classification" entity (spec.md Key
Entities) maps onto the existing `AssessmentEvent` stream with a richer
payload rather than a new table (research.md §4, data-model.md) -- no
new schema surface beyond one enum value, consistent with Milestones
2 and 6's precedent; (2) `WeakAreaFlag`'s new `misconception` field is
additive-only (contracts/api.md's response diff) -- a client built
against spec 002's existing contract keeps working unchanged, so
FR-006's "no degraded behavior" guarantee is structural (an absent
field defaults to `null`), not merely tested-for. Neither revisits a
`tech-stack.md`-locked choice; both apply patterns Milestones 1/2/6/9
already established. All ten principles re-checked above still PASS;
no new gate failure.

## Complexity Tracking

*No Constitution Check violations -- table intentionally omitted.*

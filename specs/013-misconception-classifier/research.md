# Research: Fine-Tuned Misconception Classifier

**Feature**: `020-misconception-classifier` (spec directory
`013-misconception-classifier`) | **Phase**: 0 (outline & research)

## §1. Classifier approach: embeddings + a lightweight, classically-trained classifier -- not a fine-tuned LLM

**Decision**: "Fine-tuned classifier" is implemented as: Voyage AI's
`voyage-3` embedding of each free-text answer (concatenated with its
question stem for context) -- the exact embedding model `tech-stack.md`
already locked for the Tutor Agent (Milestone 9) -- fed into a small,
per-subject `scikit-learn` classifier (multinomial logistic regression)
trained offline on this project's own accumulated, labeled data. New
dependency: `scikit-learn` (backend only).

**Rationale**: Anthropic's Claude API (this project's only configured
LLM provider, `tech-stack.md`) has no general-purpose fine-tuning
endpoint available to this project as of this stack's decision date --
"fine-tune Claude directly" is not an option without adopting a second
LLM provider purely for this one milestone, which `tech-stack.md`
nowhere else does and which roadmap.md's Assumptions never ask for.
Reusing the already-locked Voyage embedding call and adding one small,
boring, extremely standard library (`scikit-learn`) for the classifier
head is the "lightweight classifier" roadmap.md actually asks for --
genuinely trained on this project's own labeled data (satisfying
FR-001/FR-007's measured-accuracy requirement), without a new external
service or provider account.

**Alternatives considered**:
- Fine-tune a hosted LLM (OpenAI, or a smaller open-weights model via a
  fine-tuning provider): rejected -- introduces a second LLM provider
  account/dependency for one narrow classification task, which
  `tech-stack.md`'s existing "Explicitly not yet decided" note for this
  exact milestone leaves open but doesn't require, and which conflicts
  with this project's consistent single-provider (Anthropic via
  LiteLLM) pattern everywhere else.
- Prompted-only classification as the *production* mechanism (ask
  Claude directly, no training at all): rejected as the primary
  approach -- this is exactly the baseline FR-007/SC-001 requires the
  fine-tuned classifier to be measured *against*, not a substitute for
  it. Used here as the baseline (§2), not the classifier.
- A full fine-tuned transformer (e.g., fine-tuning a small open-weights
  model's weights directly): rejected as unnecessarily heavy for
  "lightweight" -- would require a GPU training step and a model-serving
  runtime this project has no infrastructure for, whereas an embedding +
  linear classifier trains in seconds on a laptop and loads in
  milliseconds inside a Vercel Function.

## §2. Baseline: prompted-only classification, mirroring the existing moderation-check pattern

**Decision**: The FR-007 baseline is a single-shot ADK `LlmAgent` call
(`LiteLlm`, defaulting to `anthropic/claude-haiku-4-5` via a new
`MISCONCEPTION_BASELINE_MODEL` env var) with a Pydantic `output_schema`
naming the closest matching taxonomy label (or `none`) -- structurally
identical to `grading-agent/src/guardrails.py`'s `check_moderation()`
(`_ModerationResult(BaseModel)`, `InMemorySessionService`/`Runner`,
single-shot, no DB session, fails closed).

**Rationale**: This project already has exactly this pattern in
production for a different classification-style judgment call; reusing
it for the baseline avoids inventing a second LLM-call shape, and Haiku
matches the "cheap, non-generation classification call" tier moderation
already established.

**Alternatives considered**: A separate, more elaborate prompted
classifier (e.g., few-shot with worked examples): rejected -- the
baseline's entire purpose is to be the *unfine-tuned* comparison point;
over-engineering it would understate the value a trained classifier
adds, which is the opposite of what SC-001's honest comparison exists
to measure.

## §3. Where classification runs: an offline/scheduled job, never inline in the Recommendation Agent's request path

**Decision**: Classification runs as a new Vercel Cron job (`vercel.json`
`crons` array gains `{"path": "/api/cron/classify-misconceptions",
"schedule": "0 7 * * *"}`, one hour after the existing demo-reset cron),
backed by a new `backend/src/api/routes/cron.py` route following that
file's existing `Authorization: Bearer $CRON_SECRET` /
`hmac.compare_digest` / fail-closed pattern exactly. The job scans for
learner/topic pairs with newly-qualifying free-text evidence since the
last run and classifies each; the Recommendation Agent's weak-area
report (`build_weak_area_report`) only ever *reads* the most recent
result at request time -- it never invokes the classifier or an LLM
call itself.

**Rationale**: `tech-stack.md`'s Vercel deployment section is explicit
that no persistent, long-running background process is available and
that any per-request agent call must stay inside the function's
execution window. Running embedding + classification inline would add
a new, non-optional latency/failure dependency to every weak-area
report request -- directly contradicting spec.md's FR-006 (graceful
degradation) and its own Assumption that this is an asynchronous
enrichment, not a new real-time critical path. A scheduled cron job,
already an established pattern in this codebase (demo-data reset,
Milestone 7), needs no new infrastructure and keeps the Recommendation
Agent's read path a cheap, already-proven DB query.

**Alternatives considered**:
- Classify inline, on-demand, inside `build_weak_area_report`: rejected
  per FR-006/Constraints above -- turns an optional enrichment into a
  request-blocking dependency with its own new failure mode.
- A dedicated always-on worker process polling for new evidence:
  rejected -- exactly the "persistent, long-running background process"
  Constitution Principle IX and `tech-stack.md` rule out for this
  project's Vercel deployment model.

## §4. Storage: a new `AssessmentEventType` value, zero new tables

**Decision**: A classification result is a new `AssessmentEvent` row,
`event_type = misconception_classified`, written by the cron job (never
per-report-request, unlike Milestone 2's `weak_area_flagged`/
`next_step_suggested`, which *are* written per report request -- this
event type is written on a schedule instead). Payload:

```json
{
  "misconception_id": "confuses-independent-dependent-variable",
  "confidence": 0.82,
  "cited_event_ids": ["<uuid>", "<uuid>", "<uuid>"],
  "classifier_version": "v1"
}
```

The Recommendation Agent reads the single most recent
`misconception_classified` event for a given `(learner_id, subject_id,
topic_id)` (if any) when building a weak-area flag -- same "most recent
row of a given event type" query shape `_already_answered()` and
`EvidenceCitation`'s `mastery_updated` lookups already use.

**Rationale**: This project has a strong, repeated precedent (Milestone
2, Milestone 6) of extending the existing append-only `AssessmentEvent`
log with a new enum value and a richer payload rather than adding a new
table, specifically because a classification decision *is* the kind of
point-in-time, cite-its-evidence decision that log already exists to
record (Constitution Principle V). No new table also means no new
migration beyond the enum addition, matching Milestone 6's
"minimal-schema-footprint" precedent.

**Alternatives considered**: A dedicated `misconception_classifications`
materialized table (like `MasteryState`): rejected -- `MasteryState`
is materialized because Bayesian updates are incremental and must
overwrite in place; a misconception classification has no equivalent
incremental-update need and is a natural fit for an immutable,
append-only decision record instead.

## §5. Evidence and confidence thresholds

**Decision**: A misconception label is only classified (and only
written as an event) once a learner/topic pair has `>= 3` qualifying
free-text `ANSWER_SUBMITTED` events, reusing the exact threshold
Milestone 2 already established for `MasteryState.update_count`'s
"confident" data-sufficiency bar (`data-model.md`, spec 002). The
classifier's own confidence threshold for emitting a label (vs. `none`)
is a separate, explicit constant (`MISCONCEPTION_CONFIDENCE_THRESHOLD
= 0.6`), tunable without a schema change since it's read at
job-run-time, not persisted per-classification.

**Rationale**: Reusing Milestone 2's `>= 3` evidence bar keeps this
milestone's "enough evidence to say something" bar consistent with the
one this project's own Recommendation Agent already established for
the same underlying question ("do we have enough observations to trust
this signal"), rather than inventing an unrelated second number with no
precedent.

## §6. Training and validation data

**Decision**: Training examples are derived from existing `AssessmentEvent`
rows (`event_type=ANSWER_SUBMITTED`, free-text questions,
`payload.correct = false`) joined to their `GeneratedQuestion.stem` --
no new data-collection mechanism (FR-001). Because no row is
pre-labeled with a specific misconception, an initial hand-labeled
validation/training seed set is authored as a checked-in fixture,
`backend/evaluation/misconception_ground_truth.jsonl`, mirroring
`grading_ground_truth.jsonl`'s existing shape (`question`, `learner
answer`, `expected_grade`, plus this feature's new `expected_misconception_id`
field) -- built from real (privacy-gated, per Milestone 7) or synthetic
accumulated grading data, per spec.md's Assumptions.

**Rationale**: Matches this project's existing ground-truth-fixture
precedent (Milestone 6) instead of inventing a new data-authoring
mechanism; keeps the classifier's training data traceable to a
reviewable, checked-in file rather than an opaque live-data pull.

## §7. Accuracy/baseline eval gate

**Decision**: A new `backend/scripts/check_misconception_classifier_eval.py`,
structurally mirroring `check_grading_agent_eval.py`: runs both the
classifier and the prompted-only baseline (§2) against
`misconception_ground_truth.jsonl`, computes accuracy for each, and
writes both numbers to a report. Unlike the grading eval gate, this
script's exit code is **never** non-zero merely because the classifier
scores below the baseline -- FR-007/SC-001 require the comparison to be
recorded honestly, not to pass a bar. The script only fails (non-zero)
if it cannot produce a comparison at all (e.g., a crash, a malformed
fixture, or fewer than 2 ground-truth rows for a subject) -- the
measurement itself is the gate, not a specific accuracy floor.

The classifier side of the comparison is measured via **leave-one-out
cross-validation**, not by scoring the shipped `classifier.joblib`
against its own training data (corrected post-review, 2026-09-01 --
the original implementation did exactly that, which is train/
validation leakage: it reports training-fit accuracy, not a genuine
generalization estimate, and isn't comparable to the baseline's honest
zero-shot number). With only 7 rows per subject there's no volume for
a real held-out split -- LOOCV is the standard way to get an unbiased
generalization estimate from a dataset that small without discarding
any of it. For each row, a fresh classifier is fit (via
`train_misconception_classifier.py`'s now-shared `fit_classifier()`)
on every *other* row for that subject and scored on the held-out one,
so no prediction ever comes from a model that saw that example during
training. The shipped artifact -- trained on all rows, for production
use -- is untouched by this script.

**Rationale**: Directly implements spec.md's FR-007 ("reported even
when the fine-tuned classifier does not outperform the baseline") --
gating merge on "classifier must win" would create an incentive to
hide or discard an honest negative result, exactly what that
requirement exists to prevent. That same honesty requirement is what
the leakage violated: an inflated, non-generalizing number is its own
kind of hidden negative result.

## §8. Model artifact storage

**Decision**: The trained classifier (embedding-classifier pipeline
weights) is serialized and checked into the repo per subject, e.g.
`backend/misconception_models/algebra-1/v1/classifier.joblib`, bundled
with the deployed backend function the same way `backend/content/<subject>/`
YAML artifacts already are -- no new database column, no new external
model-hosting service.

**Rationale**: Matches `tech-stack.md`'s existing content-schema
pattern ("bundled with the deployed function ... avoids relying on
local filesystem writes, which are not reliably persistent across
serverless invocations") -- the artifact is read-only at request time,
never written to at runtime, so bundling it exactly like a content
artifact is the smallest change consistent with an already-locked
precedent.

**Alternatives considered**: Storing serialized model bytes in Postgres:
rejected -- adds a new large-blob column and a runtime DB fetch for
something that changes only when retrained (a rare, offline event),
where a bundled file already works and needs no new schema.

## §9. Taxonomy authored per subject, inside the content artifact

**Decision**: Each subject's `subject.yaml` gains an optional
`misconceptions` list at the top level (or per-topic, under
`skill_definition`, matching where `preferred_question_types` and
`difficulty_calibration` already live) -- each entry a `misconception_id`
+ human-readable `description`. Validated in
`services/content_artifact/validator.py` alongside the existing
`_REQUIRED_TOPIC_FIELDS` checks (optional field -- a subject with none
defined is valid, per spec.md's edge cases). Both seeded subjects
(`algebra-1`, `biology`) get at least one topic's misconceptions
authored, proving Constitution Principle III continues to hold for a
second subject, consistent with every prior milestone's pattern.

**Rationale**: Directly implements FR-002/FR-009 and Principle III --
subject-specific knowledge (what misconceptions exist for this
subject's topics) lives in the content artifact the same way skill
definitions and difficulty calibration already do, never as an
engine-level hardcoded list.

## §10. No new agent, no new A2A service

**Decision**: The classifier is a plain Python service module
(`backend/src/services/misconception/classify.py`) called by the cron
route, and its output is read by the existing Recommendation Agent
(`backend/src/agents/recommendation/agent.py`) -- no new ADK agent, no
new A2A service.

**Rationale**: Per Constitution Principle IV/VI and spec.md's own
Assumptions -- no concrete independent-versioning or
independent-evaluation need for a separate deployment has been
identified; the classifier is a batch data-processing step, not a
conversational or generative responsibility distinct enough to warrant
its own agent boundary.

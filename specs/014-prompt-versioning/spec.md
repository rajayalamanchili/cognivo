# Feature Specification: Prompt Versioning and Regression Testing

**Feature Branch**: `022-prompt-versioning`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "milestone 12"

## User Scenarios & Testing *(mandatory)*

<!--
  This feature has no learner- or instructor-facing surface at all -- its
  "users" are the developers/maintainers of this codebase, and its
  "user journeys" are engineering workflows (writing a prompt, changing
  a prompt, reviewing a PR that touches one). This mirrors this
  project's existing precedent for engineering-process capabilities
  (e.g. spec 001's SC-004 subject-conditional scanner, spec 002's
  SC-005 agent-fixture-independence scanner) -- an automated CI check
  enforcing an architectural rule, not a product feature with an end
  user.
-->

### User Story 1 - Every prompt is a discoverable, versioned artifact (Priority: P1)

A developer working anywhere in this codebase (`backend/`, `grading-agent/`,
`tutor-agent/`) can find every LLM prompt used by every agent by looking
in one predictable place per agent, not by grepping for string literals.
Each prompt carries an explicit version identifier that changes whenever
its content changes -- extending the pattern the Grading Agent's
`GRADING_LOGIC_VERSION` and the Misconception Classifier's
`classifier_version` already establish to every remaining prompt in the
codebase. If a developer adds a new prompt (or edits an existing one) as
a bare inline string with no version identifier, an automated check
fails their pull request before a human reviewer has to catch it by eye.

**Why this priority**: This is the foundational capability everything
else in this milestone depends on -- a regression gate (User Story 2)
has nothing to attach to until every prompt is a discoverable, versioned
unit rather than an anonymous string buried in an agent's code. It is
also independently valuable on its own: today, tracing "which exact
prompt produced this behavior" requires reading git blame on a whole
file, not consulting one clearly-versioned artifact.

**Independent Test**: Can be fully tested by running the new automated
scanner against the current codebase (must pass, since every existing
prompt gets migrated as part of this story) and then against a
deliberately introduced new inline, unversioned prompt string (must
fail) -- delivers real value (discoverability, auditability) with no
dependency on User Story 2.

**Acceptance Scenarios**:

1. **Given** the full codebase after this story ships, **When** the
   automated prompt-artifact scanner runs, **Then** it reports zero
   unversioned inline LLM prompt strings across `backend/src`,
   `grading-agent/src`, and `tutor-agent/src`.
2. **Given** a developer adds a new agent capability that calls an LLM
   with a bare inline instruction string (no versioned artifact),
   **When** they open a pull request, **Then** the automated check fails
   and blocks merge, citing the offending file and line.
3. **Given** an existing versioned prompt (e.g. the Grading Agent's
   scoring instruction), **When** a developer changes its content,
   **Then** they are required to also change its version identifier, or
   the check fails.

---

### User Story 2 - A regressed prompt change is caught before merge, not after (Priority: P2)

A developer changes a versioned prompt belonging to an agent that
already has a quantitative, automated quality check (the Assessment-
Generation Agent's generated-question internal-consistency check, spec
001 SC-003; the Grading Agent's ground-truth accuracy/consistency gate,
spec 007 FR-008). Opening a pull request that changes that prompt
automatically re-runs the relevant check against the new prompt version,
in the same CI run that already gates every PR (Constitution Principle
X) -- no separate manual step. If the change measurably regresses the
agent's output quality below its already-locked threshold, the PR is
blocked exactly the way a failing test would block it today.

**Why this priority**: Directly implements this milestone's headline
goal ("a candidate prompt change... before it can be promoted") and is
the load-bearing safety property -- versioning alone (User Story 1)
makes regressions visible in git history after the fact; this story
stops a real regression from reaching `staging`/`main` at all. Ranked
below User Story 1 because it has nothing to gate until prompts are
versioned artifacts with a stable identity a CI step can key off of.

**Independent Test**: Can be fully tested by deliberately regressing a
copy of the Grading Agent's scoring prompt (e.g. reversing a scoring
rule) in a throwaway branch, opening a PR, and confirming the existing
ground-truth accuracy gate (already proven to fail below its 90%/95%
thresholds, spec 007 FR-008) now runs automatically against that PR and
blocks it -- delivers real value (a concrete, demonstrated regression
catch) independent of any other user story.

**Acceptance Scenarios**:

1. **Given** a pull request that changes the Grading Agent's versioned
   scoring prompt, **When** CI runs, **Then** the existing ground-truth
   accuracy/consistency eval (spec 007 FR-008's locked 90%/95%
   thresholds) automatically runs against the changed prompt as part of
   that same CI run.
2. **Given** a pull request that changes the Assessment-Generation
   Agent's versioned generation prompt, **When** CI runs, **Then** the
   existing generated-question internal-consistency check (spec 001
   SC-003) automatically runs against a fresh sample generated with the
   new prompt.
3. **Given** an eval run inside a prompt-change PR that scores below the
   already-locked threshold for that agent, **When** CI evaluates the
   result, **Then** the PR is marked failing and cannot be merged,
   consistent with Constitution Principle X's "automated check must pass
   before eligible to merge."
4. **Given** a pull request that changes a versioned prompt belonging to
   an agent with no existing quantitative eval suite (the Tutor Agent's
   conversational prompt, either guardrail's moderation prompt, the
   Misconception Classifier's baseline-comparison prompt), **When** CI
   runs, **Then** the versioning check from User Story 1 still applies,
   but no regression-quality gate blocks the PR (building a new
   automated quality eval for those prompts is explicitly out of scope
   for this milestone -- see Assumptions).

---

### User Story 3 - Every prompt-driven decision in the audit log names its prompt version (Priority: P3)

An instructor or developer investigating "why was this question
generated this way" or "why was this graded this way" (Constitution
Principle V) can already answer that question for grading outcomes
(`grading_logic_version` in the `answer_submitted` payload) and
misconception classifications (`classifier_version`). This story
extends the same already-established pattern to the one prompt-driven
decision that doesn't yet carry a version field: the Assessment-
Generation Agent's output. Every `GeneratedQuestion` this milestone
onward records which prompt version produced it.

**Why this priority**: A real gap in Principle V's explainability
guarantee, but strictly additive to Stories 1-2 -- versioning (Story 1)
must exist before there's a version identifier to log, and this story
adds no new safety property of its own (nothing here blocks a bad
change; it only makes an already-shipped decision more explainable
after the fact).

**Independent Test**: Can be fully tested by generating a question after
this story ships and confirming its stored record includes a version
field matching the Assessment-Generation prompt's current version
identifier -- delivers real value (traceability) independent of Stories
1-2's CI-gate mechanics.

**Acceptance Scenarios**:

1. **Given** a question generated by the Assessment-Generation Agent
   after this story ships, **When** its stored record is inspected,
   **Then** it includes a version field identifying exactly which
   prompt version produced it, in the same shape `grading_logic_version`
   already establishes.
2. **Given** the Assessment-Generation Agent's prompt is later changed
   and re-versioned, **When** a new question is generated, **Then** its
   recorded version field reflects the new identifier, while previously
   generated questions retain their original recorded version
   unmodified.

---

### Edge Cases

- What happens when a prompt change is a deliberate, accepted trade-off
  (e.g. the Grading Agent's real `v1`→`v2` change, which fixed a
  moderation gap and was not expected to be quality-neutral)? The gate
  in User Story 2 checks the same absolute, already-locked thresholds
  this codebase's existing eval suites already enforce (e.g. Grading's
  90%/95%) -- it is not a "must never move" comparison against the
  immediately prior version. A deliberate change that still clears the
  locked threshold merges normally; a change that would drop the agent
  below its committed quality floor requires that floor to be
  consciously relocked (its own reviewed change), not silently bypassed
  by a failing gate.
- What happens when a pull request touches a versioned prompt file for
  unrelated reasons (e.g. a comment fix, a rename) without changing the
  prompt's actual instruction content? The version-identifier check
  (User Story 1, Acceptance Scenario 3) and the regression gate (User
  Story 2) key off of a content change to the instruction itself, not a
  diff touching the file -- a no-op content change requires no version
  bump and triggers no eval re-run.
- What happens when the eval suite an agent's regression gate depends on
  cannot run at all in CI (e.g. no live model credentials configured)?
  This mirrors the existing precedent already established for the
  Grading Agent's gate (spec 007 FR-008, `check_grading_agent_eval.py`):
  an eval that cannot be evaluated at all fails closed, the same as a
  threshold miss -- it is never silently skipped.
- What happens to a prompt belonging to an agent whose eval suite is
  added later (after this milestone ships)? User Story 1's versioning
  requirement already covers it from day one; wiring a regression gate
  to a not-yet-existing eval suite is picked up automatically once that
  suite exists, requiring no further change to the prompt artifact
  itself.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every LLM prompt/instruction used anywhere in engine
  source (`backend/src`, `grading-agent/src`, `tutor-agent/src`) MUST be
  stored as a discoverable artifact colocated with the code that uses
  it, never as a bare inline string with no explicit identity.
- **FR-002**: Every such prompt artifact MUST carry an explicit,
  human-readable version identifier that changes whenever the prompt's
  instructional content changes, following the existing
  `GRADING_LOGIC_VERSION`/`classifier_version` precedent.
- **FR-003**: System MUST provide an automated check, mirroring this
  repository's existing `check_no_subject_conditionals.py` pattern, that
  scans engine source for LLM instruction content not backed by a
  versioned artifact and fails (non-zero exit) if any is found.
- **FR-004**: The check in FR-003 MUST run as a blocking step in this
  project's CI on every pull request touching `backend/src`,
  `grading-agent/src`, or `tutor-agent/src` -- not merely exist as a
  runnable local script (an explicit gap this milestone closes: neither
  `check_no_subject_conditionals.py` nor `check_misconception_
  classifier_eval.py` is currently wired into CI, despite functioning
  correctly as local scripts).
- **FR-005**: For the Assessment-Generation Agent, a pull request that
  changes its versioned prompt's content MUST automatically trigger the
  existing generated-question internal-consistency check (spec 001
  SC-003) against output generated with the new prompt version, as a
  blocking CI step.
- **FR-006**: For the Grading Agent, a pull request that changes its
  versioned scoring prompt's content MUST automatically trigger the
  existing ground-truth accuracy/consistency gate (spec 007 FR-008,
  `check_grading_agent_eval.py`) as a blocking CI step -- extending that
  gate's existing "changed source" trigger condition to explicitly
  include "changed prompt version," if it does not already.
- **FR-007**: A prompt-change PR's regression check (FR-005, FR-006)
  MUST fail the PR when the resulting score is below that agent's
  already-locked quality threshold, with the same fail-closed behavior
  (an eval that cannot run at all is a failure, not a skip) already
  established by `check_grading_agent_eval.py`.
- **FR-008**: A prompt-content change with no corresponding version-
  identifier change MUST fail the check in FR-003 -- version bumps are
  mandatory, not advisory.
- **FR-009**: The Assessment-Generation Agent's output (`GeneratedQuestion`
  records) MUST record an explicit version field identifying which
  prompt version produced it, matching the existing pattern
  `grading_logic_version` (grading outcomes) and `classifier_version`
  (misconception classifications) already establish -- extending
  Constitution Principle V's explainability guarantee to cover every
  prompt-driven decision, not just grading and classification.
- **FR-010**: Versioning (FR-001-FR-004, FR-008) MUST apply uniformly to
  every LLM prompt in engine source, including prompts that do not yet
  have a quantitative regression-eval suite to wire up (the Tutor
  Agent's conversational prompt; the Grading Agent's, Tutor Agent's, and
  backend's own moderation-guardrail prompts; the Misconception
  Classifier's baseline-comparison prompt) -- these prompts MUST be
  versioned artifacts even though FR-005/FR-006's regression gate does
  not yet apply to them (see Assumptions).
- **FR-011**: Milestones 1-11's full existing test/eval suites MUST
  continue to pass unmodified after this milestone's changes (roadmap.md
  Milestone 12 DoD) -- prompt content itself MUST NOT be altered as a
  side effect of migrating it into a versioned artifact.

### Key Entities

- **Prompt Artifact**: A single agent's LLM instruction content, stored
  as a discoverable, colocated unit rather than an anonymous inline
  string. Attributes: the instruction content itself, an explicit
  version identifier, and the agent it belongs to.
- **Regression Gate**: The CI-enforced binding between a specific prompt
  artifact and the existing quantitative eval suite (if any) that
  verifies a change to that prompt hasn't dropped agent output quality
  below its already-locked threshold.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An automated scan of the entire codebase finds zero LLM
  prompts that are bare inline strings without an explicit version
  identifier.
- **SC-002**: A deliberately regressed prompt change to the Assessment-
  Generation or Grading Agent is caught and blocks merge within the same
  automated CI run that already gates every pull request today -- no
  additional manual review step, separate pipeline, or human eval
  reading is required to catch it.
- **SC-003**: 100% of questions generated, and grading/classification
  decisions made, after this milestone ships can be traced to the exact
  prompt version that produced them, with zero ambiguity.
- **SC-004**: A developer who introduces a new, unversioned inline
  prompt anywhere in engine source has that mistake caught automatically
  before a human reviewer needs to notice it by reading the diff.
- **SC-005**: Milestones 1-11's full backend and frontend test/eval
  suites pass at the same rate they did immediately before this
  milestone's changes (no regression introduced by the migration
  itself).

## Assumptions

- **Storage mechanism deferred to planning**: `tech-stack.md` already
  lists "prompt-versioning storage mechanism (a dedicated table, a
  file-based store, or a third-party prompt-management tool)" as an
  explicit Milestone 12 decision not yet made. This spec intentionally
  does not pre-select one -- FR-001/FR-002 state the required property
  (discoverable, versioned, colocated with the code that uses it), not
  the storage technology. `plan.md` makes and records that choice in
  `tech-stack.md`, weighing it against this project's existing
  `GRADING_LOGIC_VERSION`/`classifier_version` precedent of treating a
  version string as a code constant with git as the audit trail (not a
  runtime database row) -- a strong prior given Constitution Principle
  IX's stateless-execution constraint.
- **Regression-gate scope is bounded to agents with an existing
  quantitative eval suite.** Only the Assessment-Generation Agent (spec
  001 SC-003) and the Grading Agent (spec 007 FR-008) have an existing
  automated, quantitative, pass/fail quality check today. The Tutor
  Agent has no automated conversational-quality eval at all; the three
  moderation-guardrail prompts (backend's own, Grading Agent's, Tutor
  Agent's) and the Misconception Classifier's baseline-comparison prompt
  likewise have no quantitative "did this get worse" check. Building new
  automated quality-eval harnesses for those prompts is a distinct,
  substantially larger capability not implied by "versioning and
  regression testing" -- the same reasoning roadmap.md already applies
  to explicitly exclude "automatic prompt optimization." Those prompts
  are versioned (FR-010) but not regression-gated in this milestone;
  wiring a gate for them is a natural future milestone once a
  quantitative eval exists for each.
- **Roadmap citation correction**: roadmap.md's Milestone 12 scope text
  names "Milestone 3's personalization eval" as one of the two existing
  eval suites this milestone's regression harness runs. Milestone 3
  (spec 006-personalization-eval) evaluates the Sequencing Agent's
  mastery-model efficacy -- Sequencing has no LLM prompt at all
  (Constitution Principle I: an explicit, deterministic BKT model, never
  an LLM call), so it cannot be what gates an Assessment-Generation
  prompt change. This spec instead wires FR-005 to Milestone 1's
  generated-question internal-consistency check (spec 001 SC-003,
  `batch_eval_questions.py`) -- the eval suite that actually measures
  Assessment-Generation's output quality and would plausibly catch a
  regressed generation prompt. Milestone 3 is read as loose shorthand
  for "this codebase already has the general pattern of an eval-suite
  CI gate," not a literal second suite to wire up here.
- **No new user-facing surface.** This milestone is entirely a
  developer-facing engineering-process capability, enforced through this
  project's existing GitHub PR/CI workflow (Constitution Principle X) --
  no new UI, API endpoint, or learner/instructor-visible behavior is
  introduced.
- **`batch_eval_questions.py`'s current DB-sampling approach may need
  adaptation for a stateless CI job.** It re-validates a random sample of
  *already-persisted* `GeneratedQuestion` rows, which assumes a database
  with accumulated history -- not guaranteed to exist in a fresh CI run
  the way the Grading Agent's fixture-based ground-truth file
  (`grading_ground_truth.jsonl`) does. Resolving this (e.g. generating a
  fresh sample in-CI, or introducing a fixture-based ground truth
  mirroring `grading_ground_truth.jsonl`/`misconception_ground_truth.jsonl`)
  is a `plan.md`-level implementation decision, not a scope change to
  FR-005 itself.

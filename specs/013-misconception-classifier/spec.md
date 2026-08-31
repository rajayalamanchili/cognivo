# Feature Specification: Fine-Tuned Misconception Classifier

**Feature Branch**: `020-misconception-classifier`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "milestone 11"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Named misconception in a weak-area next step (Priority: P1)

A learner has submitted several free-text answers on a topic they're
struggling with, and the pattern in their wrong answers isn't random --
they keep making the same specific conceptual error (e.g. consistently
confusing two related concepts). Today, the Recommendation Agent's
weak-area report can only say "this topic is weak" backed by a
correctness count. This story adds a named, specific misconception
label to that report when the evidence supports one, so the learner (and
any instructor viewing the same report) sees *what* is going wrong, not
just *that* something is going wrong.

**Why this priority**: This is the entire point of the milestone -- richer
signal into the existing Recommendation Agent output. Without this,
nothing the milestone builds is ever seen by anyone.

**Independent Test**: Feed the classifier a learner's accumulated
free-text grading history for a topic where the wrong answers cluster
around one known misconception pattern (per that subject's content
artifact). Confirm the resulting weak-area report carries the specific
misconception label plus citations to the graded answers that support
it, without changing any other field the report already produces.

**Acceptance Scenarios**:

1. **Given** a learner has enough graded free-text answers on a topic to
   meet the minimum-evidence bar, and their wrong answers match a named
   misconception pattern defined for that subject, **When** the
   Recommendation Agent generates its weak-area report, **Then** the
   flagged weak area for that topic includes the misconception label and
   cites the specific graded answers that support it.
2. **Given** a learner's wrong answers on a topic don't match any defined
   misconception pattern with sufficient confidence, **When** the report
   is generated, **Then** the weak-area flag for that topic is produced
   exactly as it was before this milestone (topic, mastery, evidence,
   next step), with no misconception label attached.

---

### User Story 2 - Recommendation Agent works with no classifier at all (Priority: P2)

A subject has no misconception taxonomy authored yet, or the classifier
has not been trained for that subject, or the scheduled classification
job hasn't produced a result yet (or failed) for a given learner/topic.
The Recommendation Agent (Milestone 2) must keep
producing its existing weak-area report exactly as it does today --
this enrichment is optional, never a new hard dependency.

**Why this priority**: The roadmap's own Definition of Done requires
graceful degradation. An optional enrichment that can silently break the
agent it enriches would be worse than not building it at all.

**Independent Test**: Request a weak-area report for a subject/learner
with no classification result available (untrained, no taxonomy, or the
classification job itself failed for that pair) and confirm the report is produced with
the same fields, same evidence, and same next-step suggestions Milestone
2 already guarantees -- no error surfaced, no missing report, no
degraded latency-sensitive behavior.

**Acceptance Scenarios**:

1. **Given** a subject's content artifact defines no misconception
   taxonomy, **When** a weak-area report is requested for a learner in
   that subject, **Then** the report is generated with no misconception
   labels anywhere and no error.
2. **Given** the classifier is trained and taxonomy exists but the
   scheduled classification job itself fails or times out for a given
   learner/topic pair, **When** a weak-area report
   is requested, **Then** the report still completes successfully using
   only Milestone 2's existing logic.

---

### User Story 3 - Classifier accuracy is measured honestly against a baseline (Priority: P3)

Before the classifier's output is trusted enough to show a learner or
instructor, its misconception-detection accuracy is measured against a
hand-labeled set of real (question, learner answer, expected grade,
expected misconception label) examples, and compared against a
prompted-only baseline that does the same classification without
fine-tuning. The result is reported as-is, including the case where the
fine-tuned classifier does not beat the baseline.

**Why this priority**: Mirrors the eval-gate pattern already established
for grading (Milestone 6) and personalization (Milestone 3) --a model
that classifies misconceptions without a measured accuracy number is an
unfalsifiable claim, which this project's constitution treats as a
defect, not a shortcut worth taking to ship faster.

**Independent Test**: Run the classifier and the prompted-only baseline
against the same hand-labeled validation set and confirm an accuracy
comparison is produced and recorded for both, independent of which one
wins.

**Acceptance Scenarios**:

1. **Given** a hand-labeled validation set of graded free-text answers
   with known expected misconception labels, **When** the classifier and
   the prompted-only baseline are each run against it, **Then** an
   accuracy score is recorded for both and the comparison is available
   for review.
2. **Given** the fine-tuned classifier scores lower than the
   prompted-only baseline on the validation set, **When** results are
   reported, **Then** that outcome is recorded as-is, not hidden or
   silently discarded.

---

### Edge Cases

- What happens when a learner has only one or two graded free-text
  answers on a topic? No misconception label is emitted below the
  defined minimum-evidence threshold -- a single wrong answer is not
  evidence of a *pattern*.
- What happens when the classifier's top-scoring label and the
  Recommendation Agent's existing prerequisite-based next-step
  suggestion point in different directions? The existing next-step
  suggestion is left unchanged; the misconception label is additive
  context, not a replacement for the prerequisite-chain logic already
  proven in Milestone 2.
- What happens when a second subject with no misconception taxonomy at
  all is added to the platform? The classifier produces no labels for
  that subject's learners, and the weak-area report for that subject is
  unaffected -- no engine-level code path exists that requires a
  taxonomy to be present (Principle III).
- What happens when the classifier flags a misconception that the
  learner has already since resolved (e.g., their next several answers
  show the error is gone)? The label is scoped to the evidence window
  used to compute it; a subsequent report recomputed against fresher
  evidence would no longer surface it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The classifier's training and evaluation data MUST reuse
  the question/answer text already accumulated in free-text grading
  records -- no new mechanism for *collecting* answers. Because no
  existing record carries a misconception label (that dimension has
  never been captured by anything before this milestone), the label
  itself MUST be hand-authored against that existing question/answer
  text, not collected passively -- this hand-labeling step is the one
  new, deliberately small authoring task this milestone introduces.
- **FR-002**: Each subject's misconception taxonomy (the specific,
  named patterns that can be detected for that subject, e.g.
  "consistently confuses X with Y") MUST be authored inside that
  subject's own content artifact -- never hardcoded in engine source
  (Principle III: one engine, many subjects).
- **FR-003**: A misconception classification MUST name a specific
  pattern from the relevant subject's taxonomy -- never a generic
  "this learner is weak here" signal, which the Recommendation Agent
  already produces without this milestone.
- **FR-004**: Every misconception label surfaced to a learner or
  instructor MUST cite the specific graded answer(s) that support it --
  an unsupported label MUST NOT be shown (Principle II: never vibes).
- **FR-005**: A misconception label MUST NOT be emitted for a given
  learner/topic pair until a defined minimum number of qualifying
  graded free-text answers exists for that pair.
- **FR-006**: The Recommendation Agent MUST treat the classifier's
  output as an optional enrichment of its existing weak-area flag --
  if the classifier is unavailable, untrained for the relevant subject,
  or below its confidence threshold, the weak-area report MUST still be
  produced with exactly Milestone 2's existing fields and behavior.
- **FR-007**: The classifier's misconception-detection accuracy MUST be
  measured against a hand-labeled validation set of real graded
  free-text answers and reported against a prompted-only (not
  fine-tuned) baseline -- the comparison MUST be recorded even when the
  fine-tuned classifier does not outperform the baseline.
- **FR-008**: Every misconception classification decision (which label,
  from what evidence, at what confidence) MUST be logged in a way that
  is traceable after the fact, to the same explainability bar as this
  project's existing sequencing and grading decisions (Principle V).
- **FR-009**: The classifier MUST operate only on grading data already
  covered by this project's existing privacy/retention rules
  (Milestone 7) -- it introduces no new real-learner-data collection
  surface or retention policy of its own.

### Key Entities

- **Misconception Pattern**: A named, subject-scoped category of
  conceptual error (e.g., "confuses correlation with causation"),
  authored in that subject's content artifact alongside its existing
  topic/skill definitions.
- **Misconception Classification**: The classifier's output for a given
  learner/topic pair -- which Misconception Pattern (if any), a
  confidence value, and citations to the specific graded free-text
  answers that support it.
- **Validation Set**: A hand-labeled collection of (question, learner
  answer, expected grade, expected misconception label) examples used
  to measure classifier accuracy against a prompted-only baseline.
- **Weak-Area Flag** *(existing, extended)*: The Recommendation Agent's
  per-topic flag from Milestone 2, gaining one new optional field --
  a **Misconception Enrichment** -- carrying the display-ready form of
  the most recent matching Misconception Classification (its pattern,
  description, confidence, and cited evidence) for that flag's topic.
  The enrichment is a read-time view over a Misconception Classification,
  not a separate decision -- no existing field changes shape or meaning.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The classifier's misconception-detection accuracy, and its
  comparison against a prompted-only baseline, is measured and recorded
  for 100% of the hand-labeled validation set, regardless of which one
  scores higher.
- **SC-002**: 100% of weak-area reports generated while the classifier
  is unavailable, untrained, or below confidence complete successfully
  with Milestone 2's existing fields -- zero reports fail, error, or
  degrade because of this milestone's addition.
- **SC-003**: 100% of misconception labels shown to a learner or
  instructor carry at least one cited graded answer as evidence -- zero
  unsupported labels.
- **SC-004**: Zero misconception labels are emitted for a learner/topic
  pair below the defined minimum-evidence threshold, verified across a
  synthetic test population.
- **SC-005**: Milestones 1-10's full acceptance-scenario and regression
  suites still pass.

## Assumptions

- Classifier training and inference run as an asynchronous/offline
  enrichment step, not a synchronous dependency blocking every
  Recommendation Agent request -- consistent with FR-006's graceful
  degradation and the roadmap's framing of this as "optional
  enrichment," not a new real-time critical path.
- The specific minimum-evidence count and confidence threshold are
  configuration values decided during this milestone's `/speckit-plan`,
  not fixed by this spec -- mirroring how mastery-band thresholds are
  already explicit, tunable values elsewhere in the system.
- The misconception taxonomy is authored by whoever maintains a
  subject's content artifact, the same way topic/skill definitions are
  authored today -- not auto-discovered from data with no human
  curation, at least for this milestone.
- The base model and fine-tuning approach are deliberately left
  undecided by this spec (`tech-stack.md` explicitly reserves this
  decision for this milestone's own `/speckit-plan`, made once real
  accumulated grading data is available to inspect).
- Since Milestone 7's privacy/retention gate is already in place, this
  milestone may train and evaluate on real (not only synthetic)
  accumulated grading data, subject to the exact same retention and
  deletion rules already governing that data -- this milestone creates
  no new data-handling exemption.
- This milestone does not introduce a new agent boundary: the
  classifier is consumed by the existing Recommendation Agent (local
  ADK sub-agent), not split out as its own A2A service -- no concrete
  independent-versioning or independent-evaluation need for a separate
  deployment has been identified (Principle IV/VI).

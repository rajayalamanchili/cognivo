# Feature Specification: Domain-Agnostic Core -- Content Schema, Structured Assessment, Single-Learner Mastery Model

**Feature Branch**: `001-domain-agnostic-core`

**Created**: 2026-08-14

**Status**: Draft -- pending `/speckit-clarify`

**Input**: User description: "Domain-agnostic content schema,
structured-only dynamically generated assessments, and single-learner
mastery model as the foundational engine for Cognivo"

## Clarifications

### Session 2026-08-15

- Q: What mastery-probability value counts as "below threshold" (needs
  more practice) versus "mastered", for FR-006's topic selection and
  SC-005's "not high-confidence mastery" test? → A: Three-band model --
  mastery < 0.4 is "struggling", 0.4-0.7 is "developing", >= 0.7 is
  "mastered"; only struggling or developing topics are eligible for
  next-topic selection.
- Q: How many questions should the initial placement assessment
  include, and how are they distributed across a subject's entry-level
  topics? → A: Exactly one placement question per entry-level topic.
- Q: Which two subjects should the content artifacts cover, to prove
  the engine is genuinely domain-agnostic (User Story 3 / FR-012 /
  SC-004)? → A: Algebra I and Biology.
- Q: How many recent questions (per learner and topic) should the
  near-duplicate check look back across when generating a new question
  (FR-008)? → A: Last 5 questions per learner+topic.
- Q: How many difficulty levels/bands should a content artifact define
  per topic, for the Assessment-Generation Agent to calibrate against?
  → A: 3 bands (easy/medium/hard).
- Q: When a topic has never been touched (mastery = "unknown") but its
  prerequisites just became satisfied, should the Sequencing Agent be
  able to select it for the next question? → A: Yes -- an untouched
  topic with satisfied prerequisites is eligible for next-topic
  selection alongside "struggling"/"developing" topics; without this,
  the prerequisite graph could never progress past entry-level topics
  once placement ends.
- Q: For a topic's prerequisites to count as "satisfied," does the
  prerequisite topic need to reach the "mastered" band, or is a lower
  bar enough? → A: The prerequisite topic must be "mastered" (mastery
  >= 0.7); a topic dependent on it is not eligible for selection until
  then.
- Q: When multiple topics are simultaneously eligible for selection,
  what rule breaks the tie so topic selection stays deterministic? →
  A: Lowest mastery first ("unknown" topics sort ahead of any numeric
  value, since they need evidence most urgently); if still tied, the
  topic earlier in the content artifact's authored topic order wins.
- Q: What should happen when a learner requests a next question but
  zero topics are currently eligible (everything is "mastered" or
  prerequisite-blocked)? → A: Fall back to re-serving the "mastered"
  topic with the lowest mastery value (spaced-repetition-style review)
  rather than returning an error -- the learner always gets a question.
- Q: For numeric-answer questions, should grading (FR-009) require an
  exact match, or allow a small tolerance? → A: A small relative
  tolerance (e.g. ±0.5%), generated per-question alongside the answer
  key by the Assessment-Generation Agent -- not a single global
  constant.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Take a placement assessment and get a real starting mastery estimate (Priority: P1)

A solo learner starts a new subject with no prior data. The system asks
one structured (multiple-choice/numeric) question per entry-level topic
and produces an initial, per-topic mastery estimate -- not a guess, a
value computed by an explicit model.

**Why this priority**: Nothing else in the product means anything without
a real starting mastery state -- personalized sequencing (User Story 2)
and every later milestone's grading and tutoring depend on this existing
first.

**Independent Test**: Load a subject's content artifact, run the
placement flow end to end with a scripted set of answers, and confirm
the resulting per-topic mastery values are deterministic given those
answers -- rerunning the identical answer sequence produces identical
mastery values.

**Acceptance Scenarios**:

1. **Given** a subject's content artifact defines a topic graph (topics
   and their prerequisite relationships), **When** a new learner starts
   placement, **Then** the Diagnostic Agent selects exactly one
   placement question per entry-level topic in the graph, not just one
   topic overall.
2. **Given** a learner answers all placement questions, **When** the
   Sequencing Agent's mastery model processes the results, **Then** each
   topic touched by placement receives an explicit mastery value (e.g. a
   probability of mastery, not a vague label), and topics never touched
   by placement are explicitly marked as unknown, not defaulted to zero
   or to full mastery.
3. **Given** the exact same sequence of placement answers is replayed,
   **When** the mastery model runs again, **Then** the resulting mastery
   values are identical to the first run -- the model is deterministic
   given its inputs (Constitution Principle I).
4. **Given** a learner's resulting mastery state, **When** the learner
   asks "why was I placed here" (no instructor role exists in this
   milestone; see Assumptions), **Then** the system can
   state which answers drove which topic's mastery value -- the
   computation is explainable, not just a stored number (Constitution
   Principle V).

---

### User Story 2 - Get the next question chosen for you, not from a fixed bank (Priority: P1)

Given a mastery state, the learner asks for their next question, and the
Assessment-Generation Agent produces a new, previously-unseen structured
question calibrated to a topic and difficulty the Sequencing Agent
selected -- not pulled from a static pool.

**Why this priority**: This is the "generate assessments dynamically
rather than pulling from a fixed question bank" requirement from the
original product brief, and it's the second half of what makes
Milestone 1 a complete, demoable slice on its own (placement without
dynamic follow-up questions wouldn't prove the core claim).

**Independent Test**: With a mastery state already established, request
the next question five times in a row for the same topic and confirm no
two generated questions are text-identical, while all five remain
correctly scoped to the requested topic and difficulty band.

**Acceptance Scenarios**:

1. **Given** a mastery state showing a topic that is "struggling",
   "developing", or "unknown" with satisfied prerequisites, **When**
   the learner requests a next question, **Then** the Sequencing Agent
   selects that topic (never an already-"mastered" topic, and never an
   "unknown" topic whose prerequisites aren't yet satisfied) and passes
   it to the Assessment-Generation Agent.
2. **Given** a topic and difficulty level, **When** the
   Assessment-Generation Agent generates a question, **Then** the
   question is structured (multiple-choice or numeric-answer), is
   accompanied by its own answer key generated at the same time
   (Constitution Principle II), and is validated against the content
   artifact's topic definition before being shown to the learner.
3. **Given** a generated question's answer key, **When** the learner
   submits a structured answer, **Then** grading is a direct comparison
   against that key -- deterministic, not an LLM judgment call (free-text
   grading is explicitly out of scope for this milestone; see
   Assumptions).
4. **Given** a learner answers a question correctly or incorrectly,
   **When** the mastery model updates, **Then** the affected topic's
   mastery value changes in the expected direction, and the update is
   itself explainable (which question, which answer, which topic).

---

### User Story 3 - See the engine work for a second subject with zero engine code changes (Priority: P2)

A developer (or future Claude Code session) adds a second subject's
content artifact and confirms placement, question generation, and
mastery tracking all work for it without touching any engine file.

**Why this priority**: This is the direct proof of Constitution Principle
III (domain-agnostic core) -- but it's scoped below User Stories 1-2
because a single working subject has to exist and be correct first
before a second one is worth adding to prove generality.

**Independent Test**: Add a second subject's content artifact (topic
graph, skill definitions), with zero edits to any file outside the new
content artifact and its own directory, and confirm placement and
question generation both work correctly for it.

**Acceptance Scenarios**:

1. **Given** a second subject's content artifact exists, **When** the
   full placement and question-generation flow runs against it, **Then**
   it behaves correctly with no engine-file changes -- verified by an
   automated check scanning engine source for subject-id-keyed
   conditionals.

---

### Edge Cases

- What happens if a generated question's own answer key is later found to
  be wrong (e.g. a numeric question with a calculation error)? (The
  question must be flaggable by a learner, and a flagged question must
  be excluded from future selection until reviewed -- never silently
  continue being served.)
- What happens if the topic graph has a cycle or an unreachable topic (a
  prerequisite that's never satisfiable)? (Content artifact validation
  must catch this before the subject is usable, not fail at runtime
  mid-placement.)
- What happens if a learner answers every placement question identically
  regardless of content (e.g. always picks option A for multiple-choice,
  or always submits the same value for numeric questions)? (The mastery
  model must not produce a false-confident mastery estimate from a
  degenerate answer pattern, for either question type -- this is a real
  risk worth a specific test, not just a theoretical concern.)
- What happens when two consecutive generated questions for the same
  topic/difficulty are near-duplicates of each other, even though not
  text-identical? (The generation step must check for and avoid
  semantic near-duplication within the learner's last 5 questions for
  that topic, not only exact text matches.)
- What happens if the Assessment-Generation Agent produces a
  structured question whose options don't actually match its own answer
  key (e.g. the "correct" option isn't among the listed choices)? (Must
  be caught by validation before the question is ever shown, not
  discovered by a confused learner.)
- What happens if a learner requests a next question but every topic is
  either "mastered" or blocked on an unmastered prerequisite (zero
  topics eligible)? (The Sequencing Agent falls back to re-selecting the
  "mastered" topic with the lowest mastery value for review -- the
  learner always receives a question, never an error.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a subject content-artifact schema
  (topic graph with prerequisite relationships, skill definitions) that
  is the only place subject-specific knowledge lives -- engine code MUST
  contain no subject-id-keyed conditionals.
- **FR-002**: The system MUST validate a content artifact (no cycles, no
  unreachable topics) before it can be used, failing at artifact-load
  time, not at runtime mid-session.
- **FR-003**: The Diagnostic Agent MUST select an initial placement
  question set containing exactly one question per entry-level topic
  (a topic with no prerequisites) for a new learner with no prior
  mastery data, generated at "easy" difficulty (every entry-level topic
  is "unknown" at placement time, per FR-006's difficulty mapping).
- **FR-004**: The Sequencing Agent's mastery model MUST compute an
  explicit, deterministic per-topic mastery value from a learner's
  answers -- given identical answers, it MUST produce identical mastery
  values every time (Constitution Principle I).
- **FR-005**: Topics not yet touched by any assessment MUST be explicitly
  represented as "unknown," never defaulted to a zero or full mastery
  value.
- **FR-006**: The Sequencing Agent MUST select the next topic for
  assessment, not randomly or in a fixed order, from topics with
  satisfied prerequisites that are "struggling" (< 0.4), "developing"
  (>= 0.4 and < 0.7), or "unknown" (never yet touched by any
  assessment) -- per the three-band mastery model below. A prerequisite
  topic is "satisfied" only once it is itself "mastered" (>= 0.7); a
  topic at or above 0.7 mastery ("mastered") is never selected. When
  more than one topic is eligible, the Sequencing Agent MUST select the
  one with the lowest mastery value first ("unknown" topics rank ahead
  of any numeric value); if still tied, it MUST select the topic that
  appears earliest in the content artifact's authored topic order --
  this ordering rule MUST be deterministic given the same mastery state
  and content artifact (Constitution Principle I). If zero topics are
  eligible (every topic is "mastered" or prerequisite-blocked), the
  Sequencing Agent MUST fall back to re-selecting the "mastered" topic
  with the lowest mastery value for review, rather than returning an
  error -- a next-question request always yields a question. The same
  tie-breaking rule (lowest mastery value, then earliest authored topic
  order) applies when multiple "mastered" topics tie during this
  fallback. The Sequencing Agent MUST also select the difficulty band
  for the generated question, deterministically derived from the
  selected topic's current mastery band: "struggling" or "unknown"
  topics get "easy," "developing" topics get "medium," and a "mastered"
  topic selected via the zero-eligible fallback gets "hard" (a stretch
  review question). This is a fixed mapping, not within-session
  adaptive difficulty -- see Assumptions.
- **FR-007**: The Assessment-Generation Agent MUST generate a structured
  (multiple-choice or numeric) question for a given topic and difficulty,
  along with its own answer key, generated together and validated for
  internal consistency (the marked-correct option must actually be among
  the listed choices) before the question is shown to a learner.
- **FR-008**: The system MUST avoid generating near-duplicate questions
  within the last 5 generated questions for the same learner and topic.
- **FR-009**: Grading of structured answers in this milestone MUST be a
  deterministic comparison against the generated answer key -- no LLM
  judgment call is involved (free-text grading is out of scope, see
  Assumptions). Multiple-choice grading is exact-match; numeric-answer
  grading MUST allow a small relative tolerance (e.g. ±0.5%) that the
  Assessment-Generation Agent generates per-question alongside that
  question's answer key, not a single global constant.
- **FR-010**: Every mastery-model update and every question-selection
  decision MUST be logged with enough context to answer "why was this
  question chosen" and "why did mastery change this way" after the fact
  (Constitution Principle V).
- **FR-011**: A learner MUST be able to flag a question as incorrect
  (bad answer key), and a flagged question MUST be excluded from future
  selection until reviewed (no instructor role exists in this
  milestone; see Assumptions).
- **FR-012**: The system MUST support at least two independently
  configured subjects running against the same engine codebase --
  Algebra I and Biology for this milestone -- verified by an automated
  check for subject-id-keyed conditionals in engine source.
- **FR-013**: All learner mastery state and agent session state MUST be
  persisted to the database on every write, never held only in an
  agent's in-process memory -- required so the system behaves correctly
  when deployed as stateless, ephemeral Vercel Functions, where no
  request can assume the same function instance handled the previous
  request.
- **FR-014**: Every agent invocation (Diagnostic, Sequencing,
  Assessment-Generation) MUST emit a trace to the observability backend
  (inputs, outputs, latency, token cost), flushed before the handling
  request completes -- distinct from and in addition to the pedagogical
  audit log required by FR-010 (Constitution Principle V).

### Key Entities *(include if feature involves data)*

- **ContentArtifact**: a subject's topic graph (topics, prerequisite
  edges), skill definitions, and difficulty bands (three per topic:
  easy/medium/hard) -- the only place subject-specific knowledge lives.
- **MasteryState**: a learner's per-topic mastery values (including
  explicit "unknown" for untouched topics), plus the update history that
  produced the current values. Touched topics fall into one of three
  bands, always computed live from the current mastery value (never
  cached, so a band can change immediately after any answer):
  "struggling" (< 0.4), "developing" (>= 0.4 and < 0.7), or "mastered"
  (>= 0.7); struggling, developing, and unknown-with-satisfied-
  prerequisites topics are all eligible for next-topic selection
  (FR-006) -- only "mastered" topics are excluded.
- **GeneratedQuestion**: a structured question (multiple-choice or
  numeric), its answer key (for numeric questions, including a
  per-question relative tolerance, e.g. ±0.5%, per FR-009), the
  topic/difficulty it was generated for, and its validation status
  (including any learner flag).
- **AssessmentEvent**: a logged record of a question shown, an answer
  given, the resulting grade, and the mastery-model update it triggered
  -- the audit trail behind Constitution Principle V's explainability
  requirement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given an identical sequence of placement answers submitted
  in the same order, the resulting per-topic mastery values are
  byte-for-byte identical across ten repeated runs.
- **SC-002**: Across five consecutive question-generation requests for
  the same topic and difficulty, no two generated questions are
  text-identical, and 100% remain correctly scoped to the requested topic
  (verified against the content artifact's topic definition).
- **SC-003**: 100% of generated questions pass internal-consistency
  validation (the marked-correct option is among the listed choices)
  before ever being shown to a learner -- verified by an automated check,
  not by learner-reported bugs.
- **SC-004**: Adding a second subject's content artifact requires zero
  changes to any engine file outside that artifact's own directory,
  verified by an automated check scanning for subject-id-keyed
  conditionals.
- **SC-005**: For a scripted "degenerate" answer pattern -- an identical
  option chosen regardless of question content for multiple-choice
  questions, and an identical value submitted regardless of question
  content for numeric questions -- the resulting mastery estimate on
  the affected topics stays below 0.7 (does not register as "mastered"
  per the three-band model in Key Entities) -- verified by a specific
  test for each question type, not merely by inspection.
- **SC-006**: Every mastery-model update and question-selection decision
  in a full placement-through-first-follow-up-question session is
  present in the audit log with enough detail to reconstruct why each
  decision was made.
- **SC-007**: The complete placement-through-first-follow-up-question
  flow works end to end against the live Vercel deployment (not only in
  local development), with mastery state correctly persisted across
  separate serverless function invocations -- verified by an automated
  post-deploy smoke test, per Constitution Principle IX.
- **SC-008**: 100% of agent invocations during a full placement-through-
  first-follow-up-question session produce a corresponding trace in the
  observability backend, with no dropped spans -- verified by comparing
  the count of agent calls made against the count of traces received.

## Assumptions

- Free-text answer grading (and the Grading Agent as its own A2A
  service) is explicitly out of scope for this milestone -- Milestone 1
  is structured-only, per the phased approach agreed in the project's
  own scoping discussion. Introducing free-text grading here, on top of
  a domain-agnostic content schema and a from-scratch mastery model,
  would stack three genuinely hard axes into one milestone at once --
  exactly the kind of combined risk (harder debugging, harder to demo
  reliably, the eval work most likely to get cut under time pressure)
  this project's own design process deliberately avoided when scoping
  this milestone.
- Instructor/classroom multi-tenancy is out of scope for this milestone
  -- a single, synthetic solo-learner profile is sufficient to prove the
  content schema, question generation, and mastery model all work
  correctly, per Constitution Principle VIII's requirement that no real
  learner data appears until a dedicated privacy/retention spec exists.
- The mastery model's specific statistical approach (Bayesian Knowledge
  Tracing vs. a simpler heuristic) is a `/speckit-plan`-level decision,
  to be recorded in `tech-stack.md` once chosen -- this spec requires
  only that the model be explicit, deterministic, and explainable, not a
  specific algorithm.
- The Diagnostic, Sequencing, and Assessment-Generation agents are
  implemented as local ADK sub-agents for this milestone, not remote A2A
  services -- per Constitution Principle VI, an A2A boundary must be
  justified by a concrete need, and no such need exists yet for these
  three agents at this milestone's scope. The Grading Agent's likely
  future A2A boundary (Milestone 6, once free-text grading exists) is
  anticipated but not built here.
- At least two subjects' content artifacts are built in this milestone
  specifically to prove User Story 3's extensibility claim -- not
  deferred to a later "second subject" milestone, because
  content-artifact authoring is a much smaller lift than a full new
  agent or feature and doesn't justify its own milestone. The two
  subjects are Algebra I and Biology (see Clarifications).
- Difficulty selection in this milestone is a fixed mapping from a
  topic's current mastery band (FR-006), not within-session adaptive
  difficulty -- that is Milestone 5's ("Adaptive Difficulty Quiz")
  scope per `roadmap.md`, which explicitly depends on this milestone's
  difficulty bands already existing rather than duplicating them here.

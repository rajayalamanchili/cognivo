# Feature Specification: Free-Text Grading via a Real A2A Service

**Feature Branch**: `007-grading-agent`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "milestone 6"

## Clarifications

### Session 2026-08-19

- Q: When a call to the Grading Agent times out or fails but may have actually completed on its end, should the system automatically retry with a safeguard against double-grading the same answer, or should it surface the failure to the learner and require them to manually resubmit? → A: Automatic retry -- the system retries a bounded number of times, keyed to the specific answer submission so a retry can never record a second grading decision or a second mastery-state update for the same submission. Only once retries are exhausted does the learner see a "grading unavailable" state.
- Q: Does "rubric version" (FR-007, FR-008) refer to each individual generated question's own rubric, or to a separate, shared version number for the Grading Agent's scoring logic/prompt that many rubrics are evaluated under? → A: Two distinct concepts -- each question's rubric is a unique, immutable artifact generated once alongside its question (never edited in place); separately, the Grading Agent's scoring logic/prompt carries its own version number, which is what FR-008's ground-truth eval gate protects, and every Grading Decision records which scoring-logic version graded it.
- Q: Must the hand-labeled ground-truth set (FR-008's merge gate) include triples covering edge-case answers -- blank, off-topic, and boundary-threshold-score answers -- as a required minimum? → A: Yes -- the ground-truth set MUST include triples for each edge case named in this spec (blank/whitespace-only, off-topic/nonsensical, and near-threshold-score answers), in addition to typical correct/incorrect answers, so the merge gate actually protects the edge-case behavior this spec promises.
- Q: When a learner submits toxic/abusive text as a free-text answer, what should the system do with it? → A: Reject it before grading -- a pre-grading moderation check blocks the submission (no Grading Decision, no mastery update), the learner is prompted to resubmit an on-topic answer, and the individual attempt is recorded as a new Moderation Flag (a system-initiated flag on a *submission*, distinct in shape from Milestone 1 FR-011's learner-initiated flag on a *question* -- the two are not the same mechanism, though both share the pattern of "flag now, no reviewer role exists yet"). Additionally, repeated flagged submissions from the same learner increment a per-learner counter that escalates to an account-level review flag once a locked threshold is crossed -- consistent with Milestone 1's FR-011 already having no defined reviewer until Milestone 7's content-review workflow exists, this milestone only produces the flag; who reviews or acts on an account-level flag is explicitly out of scope until Milestone 7 (no instructor role exists yet).
- Q: Should there be a maximum length enforced on a learner's free-text answer submission? → A: Yes -- a fixed maximum length is enforced on submission, rejected before it reaches moderation or grading, with a clear "answer too long" message. The exact character limit is locked at `/speckit-plan` time, consistent with how other numeric parameters are locked at planning time rather than in the spec.
- Q: Should there be a rate limit on how many free-text answers a single learner can submit for grading within a given time window? → A: Yes -- a fixed per-learner rate limit is enforced on free-text grading submissions; a learner exceeding it sees a distinct rate-limited state and can retry once the window resets. The exact limit and window are locked at `/speckit-plan` time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Learner gets a fair, rubric-grounded grade on a free-text answer (Priority: P1)

A learner is presented with a free-text (short-answer) question instead
of a multiple-choice or numeric one. They type an answer in their own
words and submit it. The system grades that answer against the rubric
generated alongside the question -- not against a grading model's
freeform impression of whether the answer "seems right" -- and the
result updates the learner's persistent mastery state through the same
mechanism a structured question's grade would.

**Why this priority**: This is the core value of the milestone: without
it, free-text questions cannot exist in the product at all, and the
grading agent has no reason to exist. Every other story in this feature
depends on this one working first.

**Independent Test**: Can be fully tested by generating a free-text
question for an existing seeded topic, submitting a learner answer, and
verifying (a) a grade is returned, (b) the grade was determined by
applying the question's own rubric, and (c) the learner's mastery state
for that topic changes exactly as it would after a structured question
answer.

**Acceptance Scenarios**:

1. **Given** a free-text question has been generated for a topic,
   **When** the question is about to be shown to a learner, **Then** it
   already carries a rubric that was generated alongside it, before
   display.
2. **Given** a learner submits a free-text answer, **When** grading
   completes, **Then** the learner sees a grade result and the same
   mastery-update pipeline used for structured answers records this
   answer's outcome.
3. **Given** two learners give differently-worded but equally correct
   answers to the same free-text question, **When** both are graded,
   **Then** both receive the same grading outcome, because both are
   evaluated against the same rubric rather than compared to each other
   or to one fixed expected string.

---

### User Story 2 - Learner can see why a free-text answer was graded the way it was (Priority: P2)

After receiving a grade on a free-text answer, a learner (and, in a
later milestone, an instructor) can see which rubric criteria their
answer met or missed, not just a bare "correct" or "incorrect."

**Why this priority**: Constitution Principle V requires that "why was
this marked wrong" have a real, traceable answer, and Principle II's
rationale specifically calls out that a rubric-based grade must be
auditable and appealable, not a one-off opinion. This is the difference
between a grade a learner can trust and one that feels arbitrary.

**Independent Test**: Can be fully tested by submitting a free-text
answer, then retrieving the recorded grading decision and confirming it
references specific rubric criteria (met/missed) and the Grading Logic
Version applied, not just a boolean.

**Acceptance Scenarios**:

1. **Given** a free-text answer has been graded, **When** the learner
   views the result, **Then** they see which rubric criteria were met
   and which were missed, in addition to the overall outcome.
2. **Given** a grading decision has been recorded, **When** that record
   is inspected after the fact, **Then** it identifies the exact rubric
   applied, the Grading Logic Version that graded it, and the
   mastery-state change it triggered.

---

### User Story 3 - Grading logic can be fixed and redeployed without touching the rest of the platform (Priority: P3)

When the Grading Agent's scoring logic is found to have a problem (e.g.
it's too strict, too lenient, or mis-scores a known answer pattern
against an otherwise-correct rubric), the team can correct and redeploy
the Grading Agent by itself, and verify the fix live, without
redeploying the Assessment-Generation Agent, the Sequencing Agent, or
any other part of the platform. (A problem with how a rubric itself was
generated is a different concern, owned by the Assessment-Generation
Agent's own generate-before-display guarantee in FR-002 -- not something
this story's Grading-Agent-only redeploy fixes.)

**Why this priority**: This is the concrete justification the
constitution requires (Principle VI) before an agent boundary is
allowed to become a network boundary at all -- if this isn't true in
practice, the Grading Agent should not have been split out as an A2A
service in the first place. It is scoped last because it is an
operational capability the team exercises, not a capability a learner
directly experiences.

**Independent Test**: Can be fully tested by deploying a rubric-scoring
change to the Grading Agent alone, confirming the change is live and
graded answers reflect it, and confirming no other agent or platform
component required a new deployment to pick it up.

**Acceptance Scenarios**:

1. **Given** a grading-logic fix is ready, **When** it is deployed,
   **Then** only the Grading Agent's deployment changes -- the rest of
   the platform's deployed version is untouched.
2. **Given** a proposed grading-logic change, **When** it is evaluated
   against the hand-labeled ground-truth set of (question, learner
   answer, expected grade) triples, **Then** the change is blocked from
   shipping if it does not meet the agreed accuracy/consistency
   threshold -- this evaluation is a merge gate, not an optional check.

---

### Edge Cases

- What happens when a learner submits a blank or whitespace-only
  free-text answer? The system must return a definite grade (not
  silently drop it or treat it as ungraded), consistent with how a
  blank structured-question submission is already handled today.
- What happens when a learner's answer is well-formed but entirely
  off-topic or nonsensical relative to the question? The rubric-based
  grade must still be deterministic and explainable, not just "the
  grading model didn't like it."
- What happens when the Grading Agent (now a real network call, not an
  in-process function) is slow to respond or unreachable? The system
  automatically retries a bounded number of times, using an idempotency
  key tied to the specific answer submission so a retry can never
  double-grade the same answer or double-count it toward mastery -- the
  same broad category of bug (a single answer's effect on mastery state
  counted more than once) this project already hit once for the quiz
  feature's answer-history bug, though that bug's actual mechanism (a
  same-transaction query re-reading its own just-flushed event) was a
  different failure than a retried network call, so its specific fix is
  not directly reusable here -- a new, network-retry-appropriate
  idempotency approach is needed (see plan.md's research). Only once
  retries are exhausted
  does the learner see a clear "grading is temporarily unavailable,
  please retry" state, rather than a false grade or a silently skipped
  mastery update. This is a new failure mode this milestone introduces
  that did not exist while grading was in-process.
- What happens when the Grading Agent's scoring logic itself turns out
  to be flawed after learners have already been graded under it? A
  fix ships as a new scoring-logic version (see Clarifications); it is
  not applied by editing any already-generated question's rubric, which
  remains immutable. Retroactively re-grading already-graded answers
  under the new version is out of scope for this milestone (see
  Assumptions).
- What happens when a free-text question is presented inside an
  Adaptive Quiz session (Milestone 5) rather than the regular
  next-question flow? It must be graded and feed mastery through the
  identical path as any other in-quiz question, per that milestone's
  existing guarantee.
- What happens when a learner submits toxic or abusive text as a
  free-text answer? The submission is rejected by a pre-grading
  moderation check -- it never reaches the Grading Agent, produces no
  Grading Decision, and triggers no mastery-state update. The learner
  sees a clear "content flagged -- please revise and resubmit your
  answer" state (deliberately not phrased as "on-topic," which this
  spec already uses elsewhere for a different, explicitly-not-rejected
  concept -- an off-topic-but-not-abusive answer is graded normally,
  not rejected; distinct also from FR-010's "grading unavailable"
  state) and the individual attempt is
  recorded as a Moderation Flag -- a distinct mechanism from Milestone
  1's FR-011 learner-initiated question flag, since this one is
  system-initiated and attaches to a submission, not a question.
  A learner with repeated flagged submissions crosses a locked threshold
  that raises a separate, account-level review flag -- reviewing or
  acting on that flag is out of scope until Milestone 7's instructor
  role and content-review workflow exist.
- What happens when a learner's free-text answer contains text
  attempting to manipulate the grading outcome (e.g., embedded
  instructions telling the grader to mark it correct regardless of
  content)? The Grading Agent evaluates only whether the answer's
  actual content meets the rubric's criteria; embedded instructions
  must not influence the outcome. A grading result that doesn't
  validate against the rubric it claims to have graded is rejected and
  retried (FR-014), not accepted.
- What happens when a learner submits an answer longer than the
  system's maximum length? The submission is rejected before it reaches
  moderation (FR-012) or grading (FR-003) -- no Moderation Flag, no
  Grading Decision, no mastery update -- and the learner sees a clear
  "answer too long" message distinct from both the moderation-rejection
  and grading-unavailable states.
- What happens when a learner exceeds the per-learner rate limit on
  free-text grading submissions? The submission is rejected before it
  reaches moderation or grading -- no Moderation Flag, no Grading
  Decision, no mastery update -- and the learner sees a distinct
  rate-limited state, separate from the "answer too long," "content
  flagged," and "grading unavailable" states, with the option to retry
  once the time window resets.
- What happens while a free-text answer is being graded? The learner
  sees a distinct "grading in progress" state for the duration of the
  call (bounded by SC-006's 5-second budget), separate from all five
  other named states (too-long, rate-limited, content-flagged,
  grading-unavailable, and the final graded result).
- What happens if a learner submits a free-text answer twice in quick
  succession (e.g., a duplicate client-side click) for the same
  question, as opposed to FR-010's server-side network-retry case? This
  is handled identically to a duplicate submission attempt on any other
  question type today: the same per-question single-submission
  enforcement rejects the second attempt once the first has been
  recorded, with no free-text-specific handling needed.
- What happens if a learner navigates away or ends their session while
  a free-text submission is still being graded? Grading is a stateless,
  server-side request-response cycle independent of the learner's
  continued presence; it completes and is persisted (or exhausts
  retries into "grading unavailable") regardless, and the learner sees
  the result whenever they next view that question.
- What happens to a learner's rejected (moderation-flagged, too-long,
  or rate-limited) submission text after rejection? It is not
  preserved for the learner to re-edit -- they compose a new submission
  from scratch, the same as if they were answering the question for the
  first time.
- What happens when no topic in a subject has opted into `free_text`
  via `preferred_question_types`? This is an explicitly valid,
  unremarkable state -- free-text questions are simply never selected
  for that subject, exactly as today for any question type a subject
  doesn't list.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support a free-text (short-answer)
  question type, subject-agnostically, alongside the existing
  multiple-choice and numeric types -- adding this type MUST NOT require
  subject-specific logic in the engine (Constitution Principle III). At
  least one topic in each of this project's seeded subjects MUST opt
  into `free_text` (not merely permitted to, per Milestone 1's existing
  precedent of proving a second subject from day one) -- a subject with
  no topic opted in remains a valid, unremarkable state for any subject
  added later, but the two seeded subjects specifically must demonstrate
  the type works.
- **FR-002**: Every free-text question MUST carry a grading rubric
  generated alongside the question itself, before the question is ever
  shown to a learner (Constitution Principle II) -- the same
  generate-before-display guarantee Milestone 1 already enforces for
  structured answer keys. A rubric MUST have at least one criterion; a
  single criterion covering the whole answer (weight 1.0) is a valid,
  unremarkable case, not an error -- there is no fixed maximum criterion
  count. If an individual question's rubric is later found to be
  flawed, it is corrected via Milestone 1's existing FR-011
  flagging mechanism (the question is flagged and excluded from future
  selection until reviewed) -- the same path already used for a bad
  structured answer key, not a new free-text-specific correction
  mechanism.
- **FR-003**: Free-text answers MUST be graded by a dedicated Grading
  Agent, invoked as a remote A2A service rather than in-process logic
  inside the Assessment-Generation Agent, so that grading (scoring)
  logic can be versioned and evaluated independently of the rest of the
  platform (Constitution Principle VI).
- **FR-004**: A free-text grading decision MUST evaluate the learner's
  answer against that question's own generated rubric -- never against
  the grading model's freeform judgment of whether the answer "seems
  right," and never against a single fixed expected string (Constitution
  Principle II).
- **FR-005**: Free-text grading MUST produce a graduated score against
  the rubric's weighted criteria (not a single all-or-nothing judgment),
  and that score MUST be collapsed to a binary correct/incorrect signal
  via a fixed, locked threshold before it reaches the mastery model --
  a score exactly equal to the threshold counts as correct (>=, not >) --
  the mastery model's own algorithm (Bayesian Knowledge Tracing) is
  unchanged by this milestone and continues to consume only a binary
  observation, exactly as it does for multiple-choice and numeric
  answers today. The full graduated score and per-criterion
  met/missed breakdown MUST be retained for learner-facing feedback and
  audit (see FR-007), even though only the thresholded binary outcome
  feeds mastery. The specific threshold value is locked at this
  feature's `/speckit-plan` time, consistent with how this project
  already locks other numeric model parameters at planning time rather
  than in the spec.
- **FR-006**: Every free-text grading decision MUST update the
  learner's persistent mastery state through the exact same mechanism a
  structured question's grading result would use -- specifically, the
  mastery-update step itself (from a binary correct/incorrect signal
  onward) is identical and unmodified; FR-005's graduated-score-to-
  threshold step is what produces that binary signal for free-text, the
  same way exact-match/tolerance comparison produces it for MC/numeric.
  A free-text answer MUST NOT become a second, inconsistent source of
  truth about what a learner knows (mirrors Milestone 5's SC-002
  guarantee for quiz sessions).
- **FR-007**: Every free-text grading decision MUST be logged with
  enough context to answer, after the fact: which question's rubric was
  applied, which version of the Grading Agent's scoring logic graded it,
  which criteria were met or missed, and what mastery-state change
  resulted -- so "why was this marked wrong" has a real, traceable
  answer (Constitution Principle V).
- **FR-008**: The system MUST evaluate any change to the Grading
  Agent's scoring logic -- which MUST carry its own version number,
  distinct from any individual question's immutable rubric -- against a
  hand-labeled ground-truth set of (question, learner answer, expected
  grade) triples, and MUST block that change from shipping if it does
  not meet an agreed accuracy/consistency threshold -- this evaluation
  is a required merge gate, not an advisory report. The ground-truth
  set MUST include triples covering each edge case named in this spec
  (blank/whitespace-only, off-topic/nonsensical, and near-threshold-
  score answers -- "near" meaning within a small margin of FR-005's
  locked threshold, the margin itself locked alongside the threshold
  at `/speckit-plan` time), not only typical correct/incorrect answers.
  The ground-truth set MUST also include at least one prompt-injection-
  attempt triple, giving SC-008's injection-defense claim a concrete,
  reusable test corpus rather than an unspecified one.
- **FR-009**: The Grading Agent's deployment MUST be independently
  updatable -- a scoring-logic change MUST be deployable and verifiable
  without requiring a new deployment of the Assessment-Generation,
  Sequencing, Diagnostic, or Recommendation agents, or the frontend.
- **FR-010**: When a call to the Grading Agent times out or fails, the
  system MUST automatically retry a bounded number of times, keyed to
  the specific answer submission so that a retry can never record a
  second grading decision or trigger a second mastery-state update for
  the same submission. Only after retries are exhausted MUST the system
  surface a clear "grading unavailable, please try again" state to the
  learner, rather than recording a false grade or silently skipping the
  mastery update. This is the same single retry policy FR-014 also
  invokes for a response-validation failure -- one bounded-retry
  mechanism total, not two with potentially different counts or
  backoff.
- **FR-011**: Free-text questions MUST be usable everywhere structured
  questions already are today, including inside an Adaptive Quiz
  session (Milestone 5), without a separate integration path.
- **FR-012**: Every free-text submission MUST pass a pre-grading
  moderation check before it reaches the Grading Agent. "Toxic or
  abusive" means content such as harassment, hate speech, sexually
  explicit material, or threats of violence directed at any person or
  group -- the same general category of content this project's
  underlying LLM provider already documents a moderation-filter pattern
  for (research.md §5); the precise classification approach is a
  plan-time implementation detail, but the category itself is not left
  undefined. A submission flagged as toxic or abusive MUST be rejected -- it MUST NOT produce a
  Grading Decision or trigger a mastery-state update -- and the learner
  MUST see a clear, distinct "content flagged -- please revise and
  resubmit your answer" state (deliberately not phrased as "on-topic,"
  which is a different, explicitly-not-rejected concept elsewhere in
  this spec -- see Edge Cases; not to be confused with FR-010's
  "grading unavailable" state either). The rejected attempt MUST be recorded as a Moderation Flag -- a new
  mechanism distinct from Milestone 1's FR-011 (which flags a
  *question* at a learner's initiative, not a *submission* at the
  system's initiative).
- **FR-013**: The system MUST track, per learner, a count of Moderation
  Flags -- specifically FR-012 moderation rejections, never a too-long
  (FR-015) or rate-limited (FR-016) rejection -- and MUST raise a
  separate, account-level review flag once a fixed, locked threshold is
  crossed. This milestone is only responsible for raising that flag;
  reviewing or acting on it, including handling a case where the flag
  was raised by false-positive moderation calls rather than genuinely
  abusive content, is out of scope until Milestone 7's instructor role
  and content-review ownership exist (mirrors the scope boundary
  Milestone 1 already accepted for its own FR-011 flagged-question
  mechanism, which likewise has no reviewer yet). The system MUST NOT
  notify the learner when their account crosses this threshold -- the
  flag is silent to the learner in this milestone, consistent with
  there being no reviewer yet to act on it or explain it.
- **FR-014**: The Grading Agent MUST treat a learner's free-text answer
  strictly as data to be evaluated against the rubric, never as
  instructions to follow -- text within an answer that attempts to
  override the rubric, claim a specific grade, or otherwise redirect the
  Grading Agent's behavior MUST NOT influence the grading outcome. The
  distinction is behavioral, not topical: an answer that merely
  discusses or quotes instructions as its subject matter (e.g., a
  computer-science question about prompt engineering) is ordinary
  rubric-graded content: what this requirement guards against is text
  addressed *at the grader itself*, attempting to redirect its
  behavior, regardless of subject matter.
  Every grading result the Grading Agent returns MUST be validated
  against that question's own rubric (criteria set and score range)
  before being accepted; a result that doesn't correspond to the rubric
  it was supposedly graded against MUST be rejected and retried rather
  than recorded, mirroring the generate-before-display validation gate
  this project already applies to generated answer keys (Milestone 1).
  This retry follows the same bounded, idempotency-keyed policy as
  FR-010 -- it does not introduce a second, separate retry mechanism --
  and if validation keeps failing after retries are exhausted, the
  learner sees FR-010's "grading unavailable" state rather than a new
  failure state.
- **FR-015**: The system MUST enforce a fixed maximum length on a
  free-text answer submission, rejected before it reaches moderation
  (FR-012) or grading (FR-003), with a clear "answer too long" message
  to the learner -- it MUST NOT produce a Moderation Flag, a Grading
  Decision, or a mastery-state update. The limit MUST be on the order
  of a few thousand characters -- generous enough that no genuine
  short-answer response could plausibly reach it. The specific
  character limit is locked at this feature's `/speckit-plan` time,
  consistent with how other numeric parameters are locked at planning
  time rather than in the spec.
- **FR-016**: The system MUST enforce a fixed per-learner rate limit on
  free-text grading submissions within a time window -- counting
  free-text submissions only, since MC/numeric answers involve no
  Grading Agent call and carry no comparable cost/abuse exposure to
  bound. A learner exceeding it MUST see a distinct rate-limited state
  and MAY retry once the window resets; a rejection under this limit
  MUST NOT produce a Moderation Flag, a Grading Decision, or a
  mastery-state update. The limit MUST be on the order of tens of
  submissions per window, generous enough to cover a full quiz
  session's worth of free-text questions for a genuine learner. The
  specific limit and window are locked at this feature's `/speckit-plan`
  time, consistent with how other numeric parameters are locked at
  planning time rather than in the spec.
- **FR-017**: For a submission that would independently trigger more
  than one of this spec's rejection conditions (e.g., a submission that
  is both over-length and would separately have been moderation-
  flagged), the checks MUST be applied in a fixed order -- length
  (FR-015), then rate limit (FR-016), then moderation (FR-012), then
  grading and its response validation (FR-003, FR-014) -- and the
  submission MUST be rejected for the first condition it fails in that
  order, never evaluated against more than one rejection reason at
  once.
- **FR-018**: Each of the five distinct learner-facing states this spec
  names (answer-too-long, rate-limited, content-flagged, grading-
  unavailable, and grading-in-progress) MUST have its own distinct
  message -- a learner MUST be able to tell which of the five occurred
  from the message alone, not only from an internal error code.

### Key Entities

- **Free-Text Question**: A generated question of the new free-text
  type; carries the same subject/topic/difficulty attributes as
  existing structured questions, plus its own generated rubric.
- **Grading Rubric**: The criteria a specific free-text answer is
  evaluated against, generated alongside its question, before display.
  A unique, immutable artifact per question -- never edited in place;
  correcting a systemic grading problem happens by shipping a new
  Grading Logic Version, not by altering an already-generated rubric.
- **Grading Logic Version**: The versioned scoring logic/prompt the
  Grading Agent uses to evaluate answers against a rubric. Distinct
  from any individual question's rubric -- many rubrics are graded
  under the same Grading Logic Version, and this is the entity FR-008's
  ground-truth eval gate protects when it changes.
- **Grading Decision**: The record of a single grading event -- which
  question's rubric was applied, which Grading Logic Version performed
  the grading, which criteria were met/missed, the graduated score, the
  threshold-derived binary outcome that was passed to the mastery
  model, and the mastery-state change it triggered. Uniquely keyed to
  its answer submission, so an automatic retry of a failed/timed-out
  grading call resolves to this same record rather than creating a
  duplicate.
- **Ground-Truth Evaluation Set**: The hand-labeled collection of
  (question, learner answer, expected grade) triples used as the merge
  gate for any Grading Agent scoring-logic change; required to include
  triples for each named edge case (blank, off-topic, near-threshold
  score) in addition to typical correct/incorrect answers.
- **Moderation Flag**: The record of a single rejected submission that
  failed the pre-grading toxicity/abuse check -- distinct from a Grading
  Decision, since a moderation-flagged submission is never graded.
  Contributes to a per-learner moderation-flag count that, past a locked
  threshold, raises a separate account-level review flag.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of free-text questions shown to learners have a
  rubric that was generated before the question was displayed --
  verified automatically, not by inspection (mirrors Milestone 1's
  SC-003 pattern for structured answer-key validation).
- **SC-002**: 100% of graded free-text answers are confirmed to update
  the learner's persistent mastery state through the same mechanism as
  a structured answer's grade (mirrors Milestone 5's SC-002 guarantee).
- **SC-003**: Any proposed change to the Grading Agent's rubric-scoring
  logic is evaluated against the hand-labeled ground-truth set before
  it can ship, and is blocked from shipping when it falls below the
  agreed accuracy/consistency threshold (threshold value locked and
  recorded at planning time in this feature's `research.md`, consistent
  with how this project already locks numeric model parameters at
  `/speckit-plan` time rather than in the spec -- so the exact value
  this criterion checks against is traceable to one place, not left
  perpetually unspecified).
- **SC-004**: For 100% of graded free-text answers, a learner can view
  which specific rubric criteria were met or missed, not only an
  overall correct/incorrect outcome.
- **SC-005**: A grading-logic fix can be deployed and verified live
  while every other agent and the frontend remain on their
  previously-deployed version -- demonstrated at least once as proof
  the A2A boundary delivers its stated justification, not merely
  claimed. The demonstration is objectively satisfied by three
  conditions, all required: (1) only the Grading Agent's deployment
  changes -- its live responses reflect the new Grading Logic Version;
  (2) no other agent or the frontend is redeployed as part of shipping
  it; (3) the ground-truth evaluation gate (SC-003) ran and passed as
  part of that deployment.
- **SC-006**: 95% of free-text answer submissions receive a grade
  within 5 seconds of submission -- including any automatic retries --
  so the added network hop to a remote Grading Agent does not make the
  experience feel broken relative to today's in-process structured-
  question grading.
- **SC-007**: 100% of moderation-flagged free-text submissions are
  confirmed to never reach the Grading Agent and never produce a
  mastery-state update -- verified automatically, not by inspection.
- **SC-008**: 100% of accepted grading results are confirmed to have
  passed validation against their question's own rubric (criteria set
  and score range) before being recorded -- verified using at least the
  prompt-injection-attempt triple FR-008's ground-truth set is required
  to include, confirming the injected instruction did not change the
  recorded grade.
- **SC-009**: 100% of over-length free-text submissions are confirmed
  to be rejected before reaching moderation or grading, with zero
  Moderation Flags, Grading Decisions, or mastery-state updates produced
  -- verified automatically, not by inspection.
- **SC-010**: 100% of free-text submissions exceeding the per-learner
  rate limit are confirmed to be rejected before reaching moderation or
  grading, with zero Moderation Flags, Grading Decisions, or
  mastery-state updates produced -- verified automatically, not by
  inspection.

## Assumptions

- Free-text questions integrate into every existing
  question-delivery context (the regular next-question flow and
  Milestone 5's Adaptive Quiz sessions) using the same delivery and
  mastery-update paths structured questions already use -- no separate
  free-text-only flow is introduced.
- Retroactively re-grading answers already graded under a since-corrected
  Grading Logic Version is out of scope for this milestone; only
  grading going forward is affected by a scoring-logic fix.
- The hand-labeled ground-truth evaluation set is curated and maintained
  by the project team (not learner-sourced), stored alongside the
  codebase similar to this project's existing evaluation-harness
  precedent (Milestone 3), and is expected to start small (on the order
  of tens of triples spanning both seeded subjects, to stay consistent
  with Constitution Principle III's subject-agnostic requirement, plus
  the required edge-case triples per FR-008) and grow over time.
- The Grading Agent's implementation language and specific deployment
  shape (a separate Vercel project vs. a route within the same project)
  are explicitly deferred to this feature's own `/speckit-plan`, per
  `tech-stack.md`'s "Explicitly not yet decided" section -- this spec
  does not presuppose either answer.
- A free-text answer is submitted once per question, consistent with
  how structured-question answers are already handled; mid-answer
  editing or multiple attempts per question are out of scope. This is
  enforced authoritatively server-side (the existing per-question
  single-submission guard applies uniformly across question types); a
  client-side safeguard against an accidental double-submission is a
  UX nicety, not the source of truth.
- The Grading Agent's continued reachability is a hard dependency of
  every free-text grading attempt -- FR-010's bounded retry, then the
  "grading unavailable" state, is the sole mitigation this milestone
  provides for that dependency. No separate uptime/availability target
  is specified beyond that fallback; a formal SLA is out of scope,
  consistent with this project's pre-Milestone-7 solo-learner
  operational scope.
- This milestone provides only per-event observability (FR-007's audit
  log entry per grading decision, FR-012's per-rejection Moderation
  Flag) -- aggregate observability of guardrail-rejection *rates* (e.g.
  alerting on a spike in moderation or rate-limit rejections) is out of
  scope; each agent invocation's Langfuse trace (Constitution Principle
  V) already provides the technical-level signal this could be built
  from later, without a new mechanism being introduced now.
- A Vercel deployment of the Grading Agent is assumed atomic from a
  caller's perspective -- traffic swaps to a new Grading Logic Version
  as a unit, not gradually. This milestone does not attempt to prevent
  or specify behavior for the brief window a deployment platform might
  itself take to complete a swap; two versions being simultaneously
  reachable mid-rollout is a deployment-platform concern, not one this
  spec adds requirements for.
- Milestone 1's FR-011 flagging mechanism (reused by FR-002 for
  correcting an individual flawed rubric) is an explicit dependency of
  this feature, not merely an incidental cross-reference -- this
  feature assumes that mechanism continues to exist and behave as
  Milestone 1 specified it.
- This milestone does not introduce instructor-facing grading review or
  override -- that capability, if needed, belongs to Milestone 7's
  content-review ownership, which currently has no owner for any
  flagged-content workflow, free-text or otherwise.
- The specific moderation check's implementation approach (e.g. an
  off-the-shelf toxicity-classification API/model vs. a prompt-based
  check), the per-learner escalation threshold value, the maximum
  free-text answer length (FR-015), and the per-learner grading
  rate limit and time window (FR-016) are deferred to this feature's
  `/speckit-plan`, consistent with how other numeric parameters and
  technology choices are locked at planning time rather than in the
  spec.
- Account-level review flags raised by FR-013 accumulate but are not
  acted upon by any human or automated process until Milestone 7 --
  this milestone's responsibility ends at raising the flag correctly,
  the same scope boundary Milestone 1's FR-011 already established for
  flagged questions.

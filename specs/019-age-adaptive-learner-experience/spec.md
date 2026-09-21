# Feature Specification: Age-Adaptive Learner Experience

**Feature Branch**: `019-age-adaptive-learner-experience`

**Created**: 2026-09-20

**Status**: Draft

**Input**: User description: "Age-Adaptive Learner Experience (Milestone
17, roadmap.md): nothing currently adapts to grade band, only to
mastery level. A grade-1 learner and a grade-12 learner move through
the identical interaction model today -- same question format, same UI
complexity, same session pacing, just different content difficulty
(Milestone 15). This feature adapts the *interaction model* -- not
content or difficulty -- to a learner's grade band: (1) read-aloud/
audio support for learners who aren't yet reading fluently, so a young
learner's math or science accuracy isn't accidentally testing reading
ability instead; (2) session-length and motivation mechanics that
differ by developmental age -- short bursts with immediate positive
reinforcement for younger bands, longer autonomy-respecting sessions
for older bands; (3) guardian-mediation intensity that varies by grade
band, layered onto the existing guardian role (Milestones 7/8) --
already clarified as four discrete tiers keyed to Milestone 15's grade
band: grades 1-2 co-present (guardian starts/sits with every session),
3-5 check-in (guardian starts session, reviews summary after), 6-8
opt-in nudges (guardian notified, no action required), 9-12 independent
(guardian remains a viewer only, same as today)."

## Clarifications

### Session 2026-09-20

- Q: How should question text and answer choices actually become
  read-aloud audio? → A: Browser-native text-to-speech (e.g., the Web
  Speech API) run client-side on the learner's device. No new backend
  dependency, no per-request cost, no `tech-stack.md` change required.
- Q: How should a grade 6-8 learner's guardian actually be notified
  when a session completes, given no email/SMS/push infrastructure
  exists today? → A: Email notification. Requires a new transactional-
  email provider dependency (a `tech-stack.md` update, per this
  project's rule that the tech stack is locked, not a suggestion) and a
  verified guardian email address gated by Milestone 7's existing
  consent flow (Constitution Principle VIII).
- Q (revised, same session): reconsidered -- A: In-app-only for v1
  instead (no new external dependency, no `tech-stack.md` change), with
  an explicit requirement (FR-007a) that the notification-delivery step
  be decoupled from tier-determination/trigger logic so email can be
  added later as a second delivery channel with minimum lift.

### Session 2026-09-20 (plan-time correction, `/speckit-plan`)

- Q: What bounded "session" should guardian-mediation gating (Story 2)
  and pacing checkpoints (Story 3) actually hook into, given the
  codebase has no session boundary around ordinary open-ended practice
  -- only Milestone 5's `QuizSession` has a start/complete lifecycle? →
  A: Quiz Sessions only. Guardian-mediation tiers and pacing checkpoints
  apply within the existing `QuizSession` lifecycle exclusively;
  ordinary (non-quiz) practice is unaffected by this feature and keeps
  today's unmediated, continuous behavior. Every "session" reference
  below means "quiz session" specifically, superseding this spec's
  original, now-corrected Assumption that a shared session concept
  already existed across both flows.
- Q: A real learner has no login of their own today -- every
  real-learner quiz session already runs entirely on the guardian's own
  authenticated session, re-checked on every single next-question and
  answer-submission call, not just at start. Given that, how should the
  check-in/opt-in-nudges/independent tiers actually let a learner
  continue a quiz without the guardian's session present for every
  request? → A: A scoped quiz-session hand-off token. The guardian still
  starts every real learner's quiz session (unchanged -- there is no
  other way to create one); for every tier except co-present, starting
  also mints a short-lived token scoped to that one `quiz_session_id`,
  which the learner's device then uses for the remainder of that quiz
  session instead of the guardian's own session. The co-present tier
  never issues this token -- the guardian's own session must stay
  present for every request in that tier, matching today's only
  existing behavior exactly. This corrects FR-005/FR-008 and Story 2's
  acceptance scenarios below, which previously implied grades 3-12
  needed no guardian action to start at all -- guardian-initiated start
  is universal; what varies by tier is what happens *after* start.

### Session 2026-09-20 (analysis-time correction, `/speckit-analyze`)

- Q: `/speckit-analyze` found that `has_unviewed_activity` (research.md
  Decision 7, backing FR-007's in-app indicator) was designed and
  documented as unconditional on completion status alone, with no tier
  check -- meaning it would also fire for the independent tier, directly
  violating FR-008's "MUST NOT produce ... a notification." → A:
  Corrected to require `determine_mediation_tier(...) == OPT_IN_NUDGES`
  in addition to the existing completion/unviewed check. FR-006/FR-007/
  FR-008 amended below to state this exclusivity explicitly; the same
  correction is carried into research.md, data-model.md, contracts/api.md,
  tasks.md, and quickstart.md.
- Q: `/speckit-analyze` also found Story 3 had no corresponding
  `SC-###`, FR-014/its edge case mis-described demo-learner behavior as
  "the independent tier's behavior" (which the actual design never
  applies to demo learners at all), and FR-012/SC-007's "read-aloud
  toggle" wording didn't match the shipped per-question `read_aloud_used`
  boolean design (research.md Decision 2). → A: Added SC-009 for Story
  3; reworded FR-014/its edge case to state demo learners are entirely
  outside tier logic, not resolved to `INDEPENDENT`; reworded FR-012/
  SC-007 to "read-aloud usage" (a per-question fact); added a clause to
  FR-013 clarifying that a `tier: null` audit-log entry for an ungraded
  subject is not itself a behavior change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read-aloud support for pre-fluent readers (Priority: P1)

A grade-1 or grade-2 learner opens a question. Because they aren't yet
reading fluently, they need the question text and every answer choice
read aloud to them on demand, so their math or science answer reflects
what they know about the subject -- not whether they can decode the
question.

**Why this priority**: This is the correctness-critical gap: without
it, a young learner's assessment result conflates reading ability with
subject mastery, undermining the mastery model's validity (Constitution
Principle I) for exactly the learners most exposed to the problem.

**Independent Test**: Can be fully tested by placing a synthetic
grade-1 learner profile in front of a question from either seeded
subject (`algebra-1` or `biology`) and confirming read-aloud is offered
for the question text and every answer choice, independent of whether
Story 2 or Story 3 are implemented.

**Acceptance Scenarios**:

1. **Given** a learner whose unlocked grade band is 1 or 2, **When**
   they are shown any question (any subject, any question type),
   **Then** a control to hear the question text and every answer choice
   read aloud is available before they answer.
2. **Given** a learner in grades 3-12, **When** they are shown a
   question, **Then** no read-aloud control is forced on them (today's
   text-only presentation is unchanged).
3. **Given** a grade-1 or grade-2 learner mid-question, **When** they
   replay the read-aloud audio, **Then** it plays again in full without
   navigating away from the question or losing their in-progress
   answer.

---

### User Story 2 - Guardian-mediation intensity by grade band (Priority: P2)

A guardian of a grade-1 learner starts and stays present for the whole
quiz session, matching how home practice realistically works for a
non-independent learner; a guardian of a grade-10 learner starts the
quiz session and then hands the device to their learner, who works
through it independently from there, because that learner practices
independently. (Ordinary, non-quiz practice is unaffected, and a
guardian starting every real learner's quiz session is universal across
all tiers -- see the 2026-09-20 plan-time Clarifications on session
scope and the hand-off token.)

**Why this priority**: Directly extends the existing guardian role
(Milestones 7/8) rather than treating "guardian" as a one-size-fits-all
viewer -- second priority because it changes account/session behavior
guardians and learners both depend on, but doesn't block Story 1's
correctness fix if sequenced after it.

**Independent Test**: Can be fully tested by creating one real
guardian-learner pair per grade band (1-2, 3-5, 6-8, 9-12), having the
guardian start a quiz session for each, and confirming each pair's
post-start, mid-session, and session-end behavior matches its tier,
independent of whether Story 1 or Story 3 are implemented.

**Acceptance Scenarios**:

1. **Given** a learner whose unlocked grade band is 1 or 2 (co-present
   tier), **When** their guardian starts a quiz session, **Then** no
   hand-off token is issued -- every subsequent question and answer in
   that quiz session still requires the guardian's own authenticated
   session, exactly as today.
2. **Given** a learner in grades 3-5 (check-in tier), **When** their
   guardian starts a quiz session, **Then** a hand-off token is issued
   so the learner can continue answering questions without the
   guardian's session present, and once the quiz session completes, a
   session summary becomes available for the guardian to review.
3. **Given** a learner in grades 6-8 (opt-in-nudges tier), **When**
   their guardian starts a quiz session, **Then** a hand-off token is
   issued the same way, and once the quiz session completes, the
   guardian's dashboard shows an in-app indicator of the activity
   instead of a summary.
4. **Given** a learner in grades 9-12 (independent tier), **When**
   their guardian starts a quiz session, **Then** a hand-off token is
   issued the same way, and completion produces neither a summary nor a
   notification -- guardian access stays read-only/viewer, exactly as
   it behaves today.
5. **Given** any tier's issued hand-off token, **When** it is used
   against a different `quiz_session_id` than the one it was minted
   for, or after that quiz session has already reached a terminal
   status (completed or ended early), **Then** the request is rejected.

---

### User Story 3 - Session pacing and motivation by age (Priority: P3)

A grade-1 learner taking a quiz is offered short, frequent bursts with
immediate positive reinforcement after each question; a grade-11
learner taking a quiz is offered a longer, uninterrupted session that
respects their ability to self-pace. (Ordinary, non-quiz practice is
unaffected -- see the 2026-09-20 plan-time Clarification on session
scope.)

**Why this priority**: Real, but the softest of the three to verify
objectively (motivation mechanics are qualitative) and the least
tangled with existing account/session infrastructure -- sequenced last
so Stories 1 and 2's harder guarantees land first.

**Independent Test**: Can be fully tested by starting a quiz session as
a synthetic learner in each of two grade bands (e.g., grade 1 vs. grade
11) and confirming the recommended session length and reinforcement
cadence differ between them, independent of whether Story 1 or Story 2
are implemented.

**Acceptance Scenarios**:

1. **Given** a learner in an early grade band taking a quiz session,
   **When** they reach the band's recommended session length, **Then**
   the system surfaces a natural stopping point with positive
   reinforcement, rather than continuing to present questions as if
   session length were unbounded.
2. **Given** a learner in a later grade band taking a quiz session,
   **When** they are practicing, **Then** no early stopping point is
   imposed and the session continues until the learner ends it, as
   today.

---

### Edge Cases

- What happens when a learner's unlocked grade advances across a tier
  boundary (e.g., 2 to 3) while a quiz session is already in progress?
  The quiz session already in progress keeps the tier it started with;
  the new tier takes effect starting with the learner's next quiz
  session.
- What happens when any tier's guardian is unavailable to start a quiz
  session? The quiz session simply does not start -- guardian-initiated
  start is universal across every tier (there is no other way to create
  a real learner's quiz session today), not a co-present-specific
  restriction.
- What happens if a co-present-tier guardian's own session expires or
  they log out mid-quiz? The quiz session cannot continue until the
  guardian re-authenticates -- the same failure mode any guardian-driven
  quiz session has today, not a new one introduced by this feature.
- What happens if a check-in/opt-in-nudges/independent tier's hand-off
  token is intercepted or shared? Its blast radius is bounded to
  answering the remaining questions of the one quiz session it was
  minted for -- it grants no broader account access and stops working
  once that quiz session reaches a terminal status.
- What happens for a seeded demo learner profile, which has no real
  guardian account? Its quiz sessions are never assignment-linked, so
  guardian-mediation-tier logic never runs at all -- no tier is
  determined (not even `null`), no audit event is logged, and no
  hand-off token is minted, regardless of the demo learner's assigned
  grade band. This is distinct from resolving to the `INDEPENDENT`
  tier (FR-014), which does log an event and does mint a token.
- What happens for a subject/topic with no grade-band data at all
  (e.g., `biology`, deliberately left ungraded per Milestone 15's
  precedent)? No read-aloud gating or mediation-tier behavior applies --
  these learners see today's unmodified experience for that subject,
  the same regression guarantee Milestone 15 already established.
- What happens if a learner is in a grade band with a required
  reinforcement stopping point (Story 3) but is also in a blocking
  guardian tier (Story 2) and the guardian ended the quiz session
  early? Ending a quiz session, whether learner- or guardian-initiated,
  is always treated as a normal completion -- no penalty or
  partial-session state is recorded differently from a
  learner-initiated stop.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST offer on-demand read-aloud audio for a
  question's full text and every answer choice to any learner whose
  unlocked grade band is 1 or 2, across every subject and question
  type, generated client-side via the learner's device/browser
  text-to-speech capability -- no server-side audio generation or new
  external dependency.
- **FR-002**: System MUST NOT force-play or auto-advance past read-aloud
  audio -- the learner controls when it plays and may replay it as many
  times as needed before answering.
- **FR-002a**: System MUST degrade gracefully (read-aloud control
  simply unavailable, question remains fully usable as text) on a
  device/browser that lacks text-to-speech support, rather than
  blocking the learner from answering.
- **FR-003**: System MUST NOT offer or require read-aloud for learners
  in grade bands 3 and above as part of this feature.
- **FR-004**: System MUST determine a learner's guardian-mediation tier
  from one of exactly four bands, keyed to their unlocked grade: 1-2
  (co-present), 3-5 (check-in), 6-8 (opt-in nudges), 9-12 (independent).
- **FR-005**: System MUST require a guardian to explicitly start every
  real learner's quiz session, for every tier -- this is not new,
  tier-specific behavior; it is this project's only existing way to
  create a real learner's quiz session, named here so the tiers below
  are read as differing only in what happens *after* start.
- **FR-005a**: For the co-present tier specifically, system MUST NOT
  issue a hand-off token when the guardian starts a quiz session --
  every subsequent question and answer in that quiz session MUST
  continue to require the guardian's own authenticated session.
- **FR-005b**: For the check-in, opt-in-nudges, and independent tiers,
  system MUST issue a hand-off token, scoped to that one
  `quiz_session_id`, when the guardian starts the quiz session, so the
  learner's device can answer the remaining questions in that quiz
  session without the guardian's own session present.
- **FR-005c**: A hand-off token MUST be rejected if presented against
  any `quiz_session_id` other than the one it was minted for, or once
  that quiz session has reached a terminal status (completed or ended
  early).
- **FR-006**: For the check-in tier, system MUST make a quiz session
  summary available for guardian review once the quiz session
  completes. This tier MUST NOT show the opt-in-nudges tier's in-app
  "new activity" indicator (FR-007) -- a summary being available is not
  the same as a badge proactively flagging it.
- **FR-007**: For the opt-in-nudges tier, system MUST show an in-app
  "new activity" indicator on the guardian's dashboard when a quiz
  session completes. This indicator is exclusive to this tier -- the
  check-in and independent tiers MUST NOT show it (FR-006, FR-008).
- **FR-007a**: System MUST trigger opt-in-nudges notifications from a
  single quiz-session-completion event, with the delivery channel
  (in-app today) implemented as a separate, swappable step -- so adding
  email as a second delivery channel later requires no change to
  tier-determination or quiz-session-completion trigger logic.
- **FR-008**: For the independent tier, system MUST NOT produce a
  summary or a notification when a quiz session completes -- including
  the opt-in-nudges tier's in-app indicator (FR-007), which MUST NOT
  appear for this tier -- guardian access otherwise stays
  read-only/viewer, exactly as it behaves today.
- **FR-009**: System MUST vary the recommended quiz session length and
  reinforcement cadence by grade band, with shorter recommended quiz
  sessions and more frequent positive reinforcement for younger bands
  and longer, uninterrupted quiz sessions for older bands. Ordinary,
  non-quiz practice is unaffected (per the session-scope Clarification
  above).
- **FR-010**: System MUST NOT change question content, difficulty
  selection, or topic ordering as part of this feature -- those remain
  governed exclusively by Milestone 15's existing grade-band content
  logic.
- **FR-011**: System MUST derive read-aloud eligibility, guardian-
  mediation tier, and quiz-session-pacing profile from the learner's
  existing grade-band state (Milestone 15), never from a second,
  independently maintained copy of grade.
- **FR-012**: System MUST log every guardian-mediation-tier
  determination as an auditable event, and every question's read-aloud
  usage (whether it was triggered at least once for that question, not
  a per-replay count) as part of the existing answer-submission event,
  consistent with the pedagogical audit log's existing explainability
  guarantee (Constitution Principle V).
- **FR-013**: System MUST leave a learner or subject with no grade-band
  data (per Milestone 15's all-or-nothing rule) entirely unaffected in
  observable/functional behavior by this feature's read-aloud,
  mediation-tier, and pacing behavior -- a new audit-log entry recording
  `tier: null` may still be written per FR-012; that alone is not a
  behavior change.
- **FR-014**: System MUST leave a demo learner's quiz session
  completely outside guardian-mediation-tier logic -- no tier is ever
  determined, no `GUARDIAN_MEDIATION_APPLIED` event is logged, and no
  hand-off token is minted for it, regardless of its assigned demo
  grade band. This is not the same as resolving to the `INDEPENDENT`
  tier, which does log an event and does mint a token.

### Key Entities

- **Guardian-Mediation Tier**: A derived classification (co-present,
  check-in, opt-in nudges, independent) computed from a learner's
  existing unlocked grade band (Milestone 15) -- not a new, separately
  stored copy of grade, per FR-011.
- **Session Pacing Profile**: The recommended quiz session length and
  reinforcement cadence associated with a learner's grade band,
  consulted at quiz session start and at natural stopping points.
- **Quiz Session Hand-off Token**: A short-lived credential scoped to
  exactly one `quiz_session_id`, minted when a guardian starts a quiz
  session for a learner in the check-in, opt-in-nudges, or independent
  tier, letting the learner's device continue that quiz session without
  the guardian's own session present. Never minted for the co-present
  tier. Stops being valid once its quiz session reaches a terminal
  status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of questions shown to a grade-1 or grade-2 learner,
  across every subject and question type, offer a read-aloud control
  for the question text and every answer choice.
- **SC-002**: A grade-1 or grade-2 learner can start, stop, and replay
  read-aloud audio without leaving the current question or losing an
  in-progress answer, on every attempt.
- **SC-003**: 100% of real learners' quiz sessions, across every tier,
  require an explicit guardian start before the first question is
  served. 0% of grade 1-2 (co-present) quiz sessions ever accept a
  hand-off token; 100% of grade 3-12 (check-in/opt-in-nudges/
  independent) quiz sessions issue exactly one hand-off token at start,
  valid only for that quiz session's remaining lifetime.
- **SC-004**: 100% of completed quiz sessions for grade 3-5 learners
  produce a guardian-reviewable summary.
- **SC-005**: 100% of completed quiz sessions for grade 6-8 learners
  produce an in-app guardian notification, with zero measured increase
  in the learner's quiz session completion time attributable to that
  notification.
- **SC-005a**: Adding email as a second opt-in-nudges delivery channel
  requires changing only the delivery step, verified by zero changes to
  tier-determination or session-completion trigger logic when that
  channel is added.
- **SC-006**: Zero change in selected question content, difficulty, or
  topic order attributable to this feature, verified against
  Milestone 15's existing regression suite passing unmodified.
- **SC-007**: Every guardian-mediation-tier determination for a real
  learner, and whether read-aloud was used for a given question (a
  per-question yes/no fact, not a per-replay count), is reconstructable
  after the fact from the audit log.
- **SC-008**: A pre-existing, ungraded subject's (e.g., `biology`)
  learner experience shows zero behavior change, measured against its
  own pre-feature baseline.
- **SC-009**: 100% of quiz sessions for an early grade band surface a
  stopping-point prompt once they reach that band's configured
  recommended-question-count; 0% of quiz sessions for a late grade band
  ever surface one. Reaching the threshold never ends the quiz session
  automatically in either case.

## Assumptions

- Read-aloud audio is English-only in v1, matching whatever language
  the learner's browser text-to-speech voice defaults to; multilingual/
  translated audio is explicitly out of scope (tracked separately in
  `roadmap.md`'s Out-of-current-roadmap ELL item).
- Browser-native text-to-speech requires no `tech-stack.md` update --
  no new external service or paid dependency is introduced by this
  feature's read-aloud capability.
- The opt-in-nudges tier's notification (FR-007) is in-app only in v1,
  reusing the guardian dashboard infrastructure Milestone 7 already
  built -- no new external dependency, no `tech-stack.md` change
  required for v1.
- Email is deliberately deferred, not rejected: FR-007a requires the
  notification-trigger and delivery-channel to be separate seams so
  that adding email later (a new transactional-email provider
  dependency, a `tech-stack.md` update, and Milestone 7's existing
  consent/verified-email flow) is additive, not a rework of tier logic.
- The read-aloud grade-band boundary (1-2) reuses the same boundary
  already decided for the co-present guardian-mediation tier, rather
  than introducing a second, independently-tuned literacy threshold.
- Guardian-mediation tiers are fixed per grade band in v1; a
  guardian-configurable per-learner override is a reasonable v2
  addition, not built here (per `roadmap.md`'s pre-spec clarification
  note).
- "Session" in this spec means Milestone 5's existing `QuizSession`
  specifically, not a new concept -- guardian-mediation (Story 2) and
  pacing (Story 3) apply only within a quiz session's lifecycle.
  Ordinary, non-quiz practice (Milestone 1's placement/next-question
  flow) has no bounded session entity today and is intentionally
  unaffected by this feature; giving it one is out of scope for v1 (see
  the 2026-09-20 plan-time Clarification).
- Positive reinforcement and stopping-point mechanics (Story 3) are
  UI/UX behaviors layered on the existing quiz session flow, not a
  change to how mastery is computed or logged.
- The hand-off token (FR-005a/b/c) is a new, real authentication
  mechanism, not merely a UI affordance -- its concrete implementation
  (format, storage/verification approach, lifetime) is a `/speckit-plan`
  decision informed by this project's existing JWT-based session
  pattern (`tech-stack.md`'s Authentication section), not specified
  here at the behavior level this document otherwise stays at.
- The hand-off token is additive to the existing guardian-session
  authorization path, not a replacement -- a guardian's own session
  remains valid for any tier's quiz session throughout, in addition to
  whatever hand-off token that session issued.

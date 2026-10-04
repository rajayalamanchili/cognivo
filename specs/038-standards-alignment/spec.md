# Feature Specification: Standards Alignment

**Feature Branch**: `038-standards-alignment`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Standards alignment (Common Core Math, NGSS) as topic-level tags on content artifacts. Today's content artifacts are self-authored topic graphs with no link to what schools actually teach; tagging against real standards would let the instructor dashboard (Milestone 7) show 'on pace with grade-level standards' instead of an abstract mastery number. Depends on Milestone 15's grade-band entity already existing as the natural place to hang a standards tag."

## Clarifications

### Session 2026-10-04

- Q: Does this feature's scope include actually tagging this project's
  existing content artifacts with real Common Core Math / NGSS codes,
  or only building the schema + dashboard capability? → A: Also tag the
  existing graded content artifacts with real, accurate standards codes
  -- this milestone includes sourcing and verifying real Common Core
  Math / NGSS codes against the actual published frameworks for every
  graded topic in this project's existing subjects, not just building
  the mechanism with illustrative placeholder tags.
- Q: When more than one topic is tagged with the same framework+code,
  is that standard "met" only once every tagged topic is `mastered`, or
  as soon as any one tagged topic is `mastered`? → A: ALL tagged topics
  must be `mastered` before the standard counts as met -- a standard
  spanning several topics isn't "on pace" until the whole span is
  mastered, matching the "on pace with grade-level standards" framing
  literally rather than the more forgiving any-one-topic reading.

### Session 2026-10-04 (second pass, `/speckit-clarify`)

- Q: How should the real Common Core Math / NGSS codes required by
  FR-010 actually get sourced and entered into the content artifacts --
  a manual/LLM-assisted research pass written directly into the
  existing content-artifact files, or an integration with an external
  standards API/dataset? → A: Manual/LLM-researched pass, written
  directly into content-artifact files as static data, matching this
  project's existing content-authoring pattern (topic graphs, skill
  definitions, difficulty calibration) -- no new external dependency or
  live integration, and no `tech-stack.md` amendment needed.
- Q: Should a guardian viewing their own enrolled child's progress also
  see that child's standards coverage, or is this feature's
  standards-coverage view instructor-only? → A: Also wire it into the
  guardian's view of their own child's progress in this same milestone,
  reusing the real, non-demo-learner ownership gate already established
  by the `require_learner_ownership_if_real()` dependency (`services/
  auth/dependencies.py`) rather than inventing a second permission
  model -- a guardian sees only their own enrolled learner's coverage,
  never a roster-wide aggregate (User Story 2 stays instructor-only).
- Q: Should the "met / in-progress / not-yet-reached" status for each
  standard be shown with a text label (not color alone), the same
  accessibility pattern this project already requires elsewhere? → A:
  Yes -- every status always pairs a color with a visible text label
  (e.g. "Met", "In progress", "Not yet reached"), matching the
  established precedent from Milestone 10's accessibility requirement
  and Milestone 23's "last practiced" indicator (spec 025's own
  `/speckit-clarify` session).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instructor or guardian sees a learner's standards coverage (Priority: P1)

An instructor opens a learner's detail view on their classroom
dashboard, or a guardian opens their own enrolled child's progress view,
and sees, for a graded subject, which grade-level curriculum standards
(e.g. a Common Core Math code, an NGSS code) that learner has met,
which are in progress, and which haven't been reached yet -- in place
of, or alongside, today's abstract per-topic mastery percentage.

**Why this priority**: This is the entire point of the feature per the
roadmap's own framing -- an instructor or guardian can answer "is this
learner on pace with what the state/district expects at their grade
level," a question an abstract mastery number cannot answer on its own.

**Independent Test**: Tag a graded subject's topics with standards
codes, have a learner answer questions until at least one topic crosses
into `mastered`, then confirm both the instructor's learner-detail view
and the owning guardian's view of that same learner show the topic's
standard as met and name the specific code -- independent of any
roster-aggregate view.

**Acceptance Scenarios**:

1. **Given** a graded-subject topic tagged with one standards code and
   a learner whose mastery band for that topic is `mastered`, **When**
   an instructor opens that learner's dashboard detail view, **Then**
   the standard's code and short title are shown as met.
2. **Given** the same topic with the learner's band at `developing`,
   **When** the instructor views the same learner, **Then** the
   standard is shown as in-progress, not met.
3. **Given** a topic the learner has never attempted, **When** the
   instructor views that learner, **Then** the topic's standard is
   shown as not-yet-reached, not as an error or omitted row.
4. **Given** a topic with zero standards tags, **When** the instructor
   views standards coverage, **Then** that topic is excluded from the
   standards list entirely (it still appears normally in the existing
   per-topic mastery view, unaffected).
5. **Given** a guardian who owns a real, non-demo learner, **When** the
   guardian views that learner's own progress, **Then** they see the
   same standards-met/in-progress/not-yet-reached information for that
   one learner, gated by the existing guardian-ownership check -- never
   another guardian's learner, and never a roster-wide aggregate.

---

### User Story 2 - Instructor sees class-wide standards coverage (Priority: P2)

An instructor opens their roster-level dashboard and sees an aggregate
view of how many enrolled learners have met each grade-level standard
for a graded subject, so they can spot a standard the whole class is
behind on without opening every learner individually.

**Why this priority**: Valuable once per-learner coverage (User Story
1) exists, but the roster aggregate is a derived convenience on top of
it, not the load-bearing capability.

**Independent Test**: With User Story 1's per-learner view already
working for multiple enrolled learners, confirm the roster view's
per-standard count matches a manual tally across those learners'
individual detail views.

**Acceptance Scenarios**:

1. **Given** a roster of learners with mixed mastery bands on a
   standard-tagged topic, **When** the instructor opens the roster
   dashboard, **Then** each standard shows a count of learners who have
   met it out of the roster's total.
2. **Given** a roster for a subject with zero standards tags anywhere
   in its content artifact, **When** the instructor opens the roster
   dashboard, **Then** the standards-coverage section does not render
   (no empty table, no error).

---

### User Story 3 - Content author tags a topic with real standards codes (Priority: P3)

A person authoring or editing a subject's content artifact adds one or
more real, verified standards codes (framework name, code, short title)
to a topic definition, the same way they already declare that topic's
skill definition and prerequisites. For this project's existing graded
subjects, this means researching and recording the actual Common Core
Math / NGSS code each existing topic corresponds to (Clarifications),
not placeholder tags.

**Why this priority**: Enables User Stories 1 and 2 but is not itself
instructor- or learner-visible; sequenced last because it's pure
authoring capability with no independent user-facing payoff.

**Independent Test**: Add a standards tag to a topic in a graded
subject's content artifact and confirm the content artifact still
passes existing load-time validation, with the new tag queryable
afterward.

**Acceptance Scenarios**:

1. **Given** a topic in a graded subject, **When** a content author adds
   a standards tag with a framework name and code, **Then** the content
   artifact validates and loads successfully.
2. **Given** a topic in an ungraded subject (no declared `grade`),
   **When** a content author attempts to add a standards tag to it,
   **Then** content-artifact validation rejects it, since an ungraded
   topic has no grade level for the tag to align against.
3. **Given** a topic with a malformed standards tag (missing framework
   or code), **When** the content artifact is loaded, **Then**
   validation fails the same way any other malformed content-artifact
   field already does today.
4. **Given** this project's existing graded subjects' topics, **When**
   this feature ships, **Then** each graded topic with a genuinely
   corresponding published standard carries that standard's real code
   (not a placeholder), and any topic genuinely without one is left
   untagged rather than assigned an inaccurate code.

---

### Edge Cases

- A single topic carries multiple standards tags across different
  frameworks (e.g. one topic satisfies both a Common Core Math code and
  an NGSS crosscutting-concept code) -- all tags must be shown, not just
  one.
- Multiple topics map to the same standard code -- the standard is
  "met" only once every topic tagged with that framework+code is
  `mastered` (Clarifications); a single tagged topic still at
  `developing` holds the whole standard at in-progress even if its
  sibling topics are already mastered.
- A subject has `GradeBand` rows for some grades but a given topic's
  grade has no standards tagged at all yet -- that topic is simply
  excluded from standards views, not treated as "not yet reached" (it
  was never claimed to map to a standard in the first place).
- A learner is enrolled in a roster for a subject that has zero
  `GradeBand` rows at all (fully ungraded) -- the standards-coverage
  section is absent for that subject, same handling as the zero-tags
  case.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The content-artifact schema MUST allow a topic to declare
  zero or more standards tags, each carrying a framework name (e.g.
  "Common Core Math", "NGSS"), a code (e.g.
  "CCSS.MATH.CONTENT.3.OA.A.1"), and a short human-readable title --
  authored content-artifact data, never engine source.
- **FR-002**: The engine (sequencing, grading, validation) MUST treat
  every framework name and code as opaque authored data. No engine code
  path may branch on a specific framework name or code value
  (Constitution Principle III).
- **FR-003**: A standards tag MUST only be declarable on a topic that
  belongs to a graded subject (i.e. the topic has a non-null `grade`,
  per Milestone 15/17's `GradeBand`/`Topic.grade`). Content-artifact
  validation MUST reject a standards tag on an ungraded topic.
- **FR-004**: The instructor dashboard's per-learner detail view, and
  the guardian-facing view of their own enrolled learner, MUST both
  show, for each standards-tagged topic in a graded subject the learner
  is enrolled in, whether that standard is met, in-progress, or
  not-yet-reached, derived only from that learner's existing
  `MasteryState` band for the tagged topic(s) -- no new mastery
  computation. When a standard's framework+code is tagged on more than
  one topic, the standard is met only when every one of those topics is
  at `mastered` for that learner (Clarifications); any one of them below
  `mastered` holds the standard at in-progress. The guardian-facing
  surface MUST reuse the existing `require_learner_ownership_if_real()`
  gate (Clarifications) -- no second permission model.
- **FR-005**: The instructor dashboard's roster-level view MUST show,
  for each standards-tagged topic in a graded subject, a count of
  enrolled learners who have met that standard (per FR-004's all-topics
  rule) out of the roster's total enrolled learners.
- **FR-006**: A topic with zero standards tags MUST be excluded from
  every standards-coverage view. It MUST continue to appear, unaffected,
  in the existing per-topic mastery view.
- **FR-007**: Every standards-coverage figure shown to an instructor
  MUST be traceable to the specific standard code(s) and topic
  mastery band(s) that produced it (Constitution Principle V) -- an
  instructor can see which exact topics/codes are and are not yet met,
  not only a rolled-up percentage.
- **FR-008**: Standards tags MUST NOT influence the Sequencing Agent's
  topic selection, the mastery model's computation, or assessment
  generation in any way. This feature is presentation-only, identical in
  category to Milestone 23's explainability UI.
- **FR-009**: Existing content artifacts with no standards tags MUST
  continue to load and function exactly as before (tags are optional
  and fully backward-compatible).
- **FR-010**: Every graded topic in this project's existing content
  artifacts (per Clarifications) MUST be tagged with the real,
  verified Common Core Math and/or NGSS code(s) that topic actually
  corresponds to -- sourced from the published frameworks via a
  manual/LLM-assisted research pass and written directly into the
  content-artifact files as static data (Clarifications), the same
  authoring pattern as every other content-artifact field. No external
  standards API or live data integration is introduced. A graded topic
  with no genuinely corresponding published standard is left untagged
  (FR-009) rather than assigned an inaccurate code.
- **FR-011**: Every standards status (met / in-progress / not-yet-
  reached) MUST be conveyed with a visible text label, never by color
  alone (Clarifications), matching the accessibility precedent set by
  Milestone 10 and Milestone 23.

### Key Entities

- **StandardsTag**: Associates a `Topic` with an external curriculum
  standard. Attributes: the owning topic, a framework name, a code, and
  a short title. A topic may have zero, one, or many tags; a given
  framework+code pair may appear on more than one topic (see
  Clarifications for how coverage is computed in that case).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An instructor can determine, for any enrolled learner in a
  graded subject, which grade-level standards are met vs. outstanding
  entirely from the dashboard, without consulting any source outside
  the platform.
- **SC-002**: Adding, editing, or removing a standards tag requires a
  content-artifact-only change; zero lines of engine source change as a
  result (verifies FR-002's subject/framework-agnostic boundary).
- **SC-003**: 100% of standards-coverage figures shown on the dashboard
  trace back to a specific topic, standard code, and mastery band --
  zero figures are fabricated or computed outside the existing mastery
  model.
- **SC-004**: Subjects and content artifacts with no standards tags show
  zero errors and zero visual regression in any existing dashboard
  section after this feature ships.
- **SC-005**: Every graded topic across this project's existing content
  artifacts that has a genuinely corresponding published Common Core
  Math or NGSS standard is tagged with that standard's real, verified
  code; zero tags are placeholder or fabricated values.

## Assumptions

- "Met" / "in-progress" / "not-yet-reached" reuse the existing
  `mastered` / `developing` / (not yet attempted or below) mastery-band
  vocabulary from Milestone 1 -- no new band or threshold is introduced
  by this feature.
- This feature's per-learner view (User Story 1) extends to both the
  instructor dashboard and the guardian's existing view of their own
  enrolled learner (Clarifications); the roster-wide aggregate (User
  Story 2) stays instructor-only. A standalone self-service view for
  the learner themselves is not in scope -- learners do not hold their
  own accounts in this product (guardians act on their behalf), so this
  is a distinct, much larger concern this feature does not touch.
- Standards tags are additive metadata on `Topic`; no new permission or
  role is introduced -- any instructor who can already view a roster's
  dashboard, or any guardian who can already view their own learner's
  data via the existing ownership gate, can see that learner's standards
  coverage.
- Per Clarifications, this feature's scope includes sourcing and
  verifying real Common Core Math / NGSS codes for every graded topic
  in this project's existing content artifacts -- not just building the
  tagging mechanism. A topic with genuinely no corresponding published
  standard (vanishingly rare for grade 1-12 math/science, but possible
  for a locally-authored enrichment topic) is tagged with zero
  standards per FR-009, not a fabricated code.

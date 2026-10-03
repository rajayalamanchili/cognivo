# Feature Specification: Learner-Facing UI Redesign

**Feature Branch**: `037-learner-ui-redesign`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "Redesign the learner-facing UI (Dashboard, Practice, Mastery, Placement, AI Tutor, Answer Result screens) to match new visual design mockups exported from Claude Design. These are reference mockups (inline-styled static HTML with hardcoded sample data) showing a refreshed visual language: a purple/lavender palette, Baloo 2 (headings) + Nunito (body) typography already in use since Milestone 8's theme system, pill-shaped nav links and buttons, 20-24px rounded cards, and specific spacing/color values per component. This is a visual/styling update only -- no new functionality, no backend/API changes, no new data being displayed beyond what each corresponding live page already renders."

## Context

Milestone 8 introduced the project's first design-token theme system (semantic light/dark color tokens, Baloo 2 + Nunito type, softened corners) across 28 components. This feature replaces those token values with a newer visual language -- produced as design mockups for the six learner-facing screens that make up the solo-learner experience -- without touching any logic, data, or agent behavior those screens render. It is scoped as a design-system update, the same category of work as Milestone 8's own theme overhaul, not a new product capability.

The six reference mockups (one static HTML file per screen: Dashboard, Practice, Mastery, Placement, AI Tutor, Answer Result) are visual references only. Their inline styles carry the exact values (colors, type sizes, spacing, radii, shapes) to replicate; their markup structure and hardcoded sample data are not meant to be copied as-is.

## Clarifications

### Session 2026-10-02

- Q: The new palette values (`--color-primary`, `--background`, `--color-border`, `--color-muted`, `--color-success`, `--color-warning`) live in `globals.css`'s global, site-wide token block -- already consumed by out-of-scope surfaces (instructor rosters/review pages, guardian pages, sign-in, auth forms), discovered mid-implementation. FR-006 (centralize shared values in the existing token system) and FR-007 (out-of-scope screens unchanged) directly conflict once that's known: a global token edit is exactly what FR-006 asks for, and exactly what FR-007 forbids. Which wins? → A: Global rebrand. The shared color tokens are a legitimate site-wide update -- the same category of change as Milestone 8's original theme system, which also restyled every component in one pass, not a scoped subset. FR-007's "unchanged" scope is amended to cover layout, component shapes, and structure only; the shared brand-color tokens were always global by design, and letting them cascade is the intended, honest behavior of a "design-token system," not a side effect to prevent. Out-of-scope pages get the new palette's colors but no new components, shapes, or layout changes.

### Session 2026-10-02 (second pass)

- Q: A faithfulness pass against the mockups found the live Dashboard and Answer Result are structurally simpler than their mockups -- Dashboard has no subject-pill toggle, "Up next" hero, refresh card, or stat-tile row (it stacks every subject's mastery/weak-area view instead); Answer Result has no mastery before→after bar. FR-002's original "no new data" line would forbid closing these gaps. Should the gap stay (restyle only what exists) or should the spec's scope grow to close it? → A: Close it, with a bias toward zero new data over inventing a feature. Audited what's already available first: `AnswerResult`/`PlacementQuestionResultEntry`/`QuizAnswerResultEntry` already carry `prior_p_mastery` in the API response -- `AnswerResultView` just never consumed it, so the before→after bar needs no new data at all. Dashboard's subject toggle, "Up next" hero (topic + why-text), and refresh card are all derivable client-side from data `DashboardSubjectSection` already fetches (`topic-priority-preview`'s `next_topic`/`is_fallback`, plus `mastery-state`'s per-topic `p_mastery`/`effective_p_mastery`) -- no new fetch either. The one true gap is "questions this week," which no existing endpoint exposes anywhere -- for that one number, FR-008 is narrowly amended (see below) to permit exactly one new minimal, read-only backend endpoint, rather than fabricating the number client-side or omitting the whole stat-tile row the mockup depicts.

### Session 2026-10-02 (third pass, user-confirmed scope)

- The user's own framing for this pass: "stay true to the mockup and add data UI if needed, update the spec if needed." Recorded here verbatim as the directive this pass's FR-002/FR-008 amendments and the new FR-009 are built against, so a future reader doesn't mistake this as unprompted scope growth.

### Session 2026-10-03 (fourth pass, user-directed: "fix all deferred items and gaps")

- Q: T007's own task note explicitly deferred two pieces of the Dashboard mockup as "new behavior, not a restyle": the "Why this question?" expand/collapse disclosure (picked-because/current-estimate/recorded-by detail), and the "Refreshed!" banner naming a topic that recently crossed back above the mastered line. A later audit also found two silent gaps nobody had flagged: the refresh card's retained/best progress bar was never built, and the stat tiles never got the mockup's sub-line (subject name, "N answered correctly", "Practice restores it"). Directed to close all four. The progress bar and stat-tile sub-lines needed zero new data (same ordering as the third pass). The other two touch the mastery model's own concepts, so each got its own scope check rather than a guess: → A1 (why-disclosure): add one new field, `next_topic_prerequisite_display_name`, to the existing `topic-priority-preview` response -- the Sequencing Agent's ranking context already builds the `prereqs_by_topic` map this needs (`agent.py`'s `_load_topic_ranking_context`), so this is a read-only lookup against data already in memory for that request, not a new query shape. → A2 (refreshed banner): add one new field, `recently_refreshed_topic_id`, to the existing `mastery-state` response, derived read-only from the `mastery_updated` audit log (Constitution Principle V) -- approximates `mastery_tool.py`'s existing `refreshed_from_bands` definition (crossed into mastered, having been mastered at some *earlier* point too, so first-time mastery is never misreported as a "refresh") as closely as the audit trail allows, since it doesn't persist the confirmation-streak count that function's exact check needs.
- Both new fields are additive and optional-shaped (`| None`/`| null`): no existing response consumer breaks, and FR-008's "no new backend surface beyond FR-009" line is amended below to name these two as the same kind of narrow, read-only exception FR-009 already established -- not a reopening of that constraint generally.
- A follow-up check against the same mockup found two more structural gaps nobody had flagged: Dashboard's content column was `max-w-3xl` (768px) against the mockup's 1180px (the hero/stat-tile/two-column grids were never going to look right that cramped), and the shared `Nav` bar had no centered max-width container at all (full-bleed) against the mockup's centered 1180px/68px header, with no avatar/name element on the right for the demo-learner bucket. Widened Dashboard's column to `max-w-[1180px]` and added the avatar+name to `Nav`, scoped to the demo-learner bucket only (Edge Cases: new layout/shape treatment stays scoped there) -- the demo learner's real `display_name` (already resolved elsewhere via `getDemoLearner()`), not the mockup's literal "Sam" sample text (Assumptions: sample copy isn't a literal content requirement). User feedback on the first version of this (Personalization Evidence/Exit Demo/Sign In rendered inline next to the avatar) was to tuck those three behind a click on the avatar/name instead, closer to the mockup (which shows no such links at all in that single static frame) -- implemented as a dismissible dropdown (closes on an outside click), not a new page or route.
- Running the app end-to-end (not just the test suite) surfaced three more real bugs, all fixed in this same pass: (1) `max-w-[1180px]` alone didn't actually widen Dashboard's column -- `mx-auto` disables flex-item stretch along the cross axis (the root layout's `<body>` is `flex flex-col`), so the column was silently shrinking to fit its own widest child's content instead of filling up to its max-width; fixed by adding `w-full` alongside `max-w-*`/`mx-auto` on all six screens' top-level wrappers (the identical pattern existed everywhere, just less visible at the narrower 672-768px targets). (2) A side-by-side pixel check against the mockup found several `DashboardSubjectSection.tsx`/`dashboard-flow.tsx` font sizes had drifted from the mockup's actual values during the original restyle (e.g. the welcome heading at 32px vs. the mockup's 40px, the stat-tile value at 28px vs. 36px, the "Where to focus next"/"Your topics" headings at 20px vs. 26px) -- corrected every one against the mockup's literal inline `font-size` values. (3) `Nav`'s `demoLearnerMode` state was read synchronously from `localStorage` in a `useState` initializer, which runs during SSR too (where `localStorage` doesn't exist, so it silently returned `false`) -- on an actual page load/navigation while already in demo-learner mode, this produced a real React hydration-mismatch error once the nav's demo-learner-bucket markup diverged structurally from its anonymous-bucket markup. Fixed by starting the state at `false` unconditionally (matching what SSR renders) and letting the existing post-mount `refresh()` effect correct it, the same pattern `accountType` already used for the identical reason.
- Q: With the mockup-matching Up Next hero/stat tiles/Your topics now in place, is `PathVisualization.tsx`'s standalone "Assessed so far"/"Up next"/"Likely coming up" block (spec 025 FR-003/FR-004, never restyled -- the original T007 note explicitly left it unstyled as out of scope) still earning its place on Dashboard? → A: No, for two of its three pieces -- "Assessed so far" is now fully redundant with "Your topics" (which already lists every topic, assessed or not, with its actual mastery % and band), and "Up next" is fully redundant with the hero's own topic name. Removed the standalone block (and the now-fully-unused `PathVisualization.tsx` component and its test) and folded its one genuinely non-redundant piece -- the "Likely coming up" upcoming-topics preview plus FR-004's "illustrative, subject to change" disclosure -- directly into the UP NEXT hero as a small line, still capped at 3 (spec 025 SC-006), still only shown via the same `topic-priority-preview` fetch this hero already consumes. The fetch's own failure-isolation guarantee (spec 025 FR-008) moved with it: `dashboard-path-slot`'s loading/"couldn't load" states now gate the hero itself rather than a separate bottom block.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A learner sees the refreshed visual design with no change in behavior (Priority: P1)

A learner using the Dashboard, Practice, Mastery, Placement, AI Tutor, or Answer Result screens sees the new purple/lavender visual language -- pill-shaped buttons and nav, rounded cards, the updated color palette and type treatment -- while every interaction (starting practice, asking the tutor, reviewing mastery, taking placement, seeing a graded result) behaves exactly as it did before the redesign.

**Why this priority**: This is the entire point of the feature. Without behavioral parity, a styling update would risk silently breaking the product's actual functionality -- the one outcome a pure design-system refresh must never cause.

**Independent Test**: Load each of the six screens before and after the redesign with the same demo-learner state and confirm identical data, navigation targets, and interactive outcomes, with only visual presentation differing.

**Acceptance Scenarios**:

1. **Given** the Dashboard, Practice, Mastery, Placement, AI Tutor, and Answer Result screens, **When** each renders, **Then** its colors, typography, spacing, corner radii, and button/nav shapes match the corresponding design mockup's values -- including Dashboard's subject-pill toggle, "Up next" hero (with its "why this question?" disclosure and prerequisite naming), refresh card (with its retained/best progress bar), stat-tile row (with each tile's sub-line), and "Refreshed!" banner, and Answer Result's mastery before→after bar, once those are built per the second and fourth Clarifications passes above.
2. **Given** a learner performs any existing action on one of the six screens (e.g. starting practice, submitting an answer, opening "why this question?", asking the tutor a question), **When** the action completes, **Then** the outcome (data shown, navigation, state change) is identical to the pre-redesign behavior.
3. **Given** a screen or component outside the six named screens (e.g. the instructor dashboard, guardian/auth flows), **When** the redesign ships, **Then** its layout, component shapes, and structure are unchanged -- except for the shared color-token rebrand covered by FR-007's amended scope below, which intentionally does cascade there.

---

### User Story 2 - Accessibility and demo-data safeguards survive the restyle (Priority: P1)

The persistent "DEMO ACCOUNT" badge and every non-color accessibility cue already shipped on these screens (e.g. the text label accompanying the "last practiced" color warming, required image alt text) continue to appear, in the new visual style, after the redesign.

**Why this priority**: Constitution Principle VIII requires demo accounts to always be visibly flagged, and prior milestones (10, 23) deliberately added non-color cues so information isn't carried by color alone. A visual refresh that drops either while chasing the new look would silently regress two already-settled requirements.

**Independent Test**: Compare each safeguard's pre-redesign acceptance scenario (badge visibility, non-color cue presence) against its post-redesign rendering and confirm it still holds.

**Acceptance Scenarios**:

1. **Given** a demo-learner session on any of the six redesigned screens, **When** the page renders, **Then** the persistent demo-account badge is visible, styled to match the new design system.
2. **Given** a topic whose "last practiced" indicator has a warm color cue, **When** it renders post-redesign, **Then** the elapsed-time text label is still present alongside the color, not color alone.
3. **Given** an image-bearing question, **When** it renders post-redesign, **Then** its alt text is still present and non-empty.

---

### User Story 3 - Shared design values live in one place, not scattered per component (Priority: P2)

The colors, type scale, spacing, and radius values the new design introduces are defined once, in the project's shared styling system, and consumed by the six screens and their shared components -- rather than each screen hardcoding its own copies of the same values.

**Why this priority**: Milestone 8 established token-based theming specifically so a future visual update would be a values change, not a per-component rewrite. Scattering the new values as one-off literals in each component would quietly undo that and make the next redesign harder, but this is a secondary, maintainability-driven priority -- the product works correctly either way.

**Independent Test**: Change one shared value (e.g. the primary purple) in the central token definition and confirm it propagates to every one of the six screens without editing each screen individually.

**Acceptance Scenarios**:

1. **Given** the new palette's primary color value, **When** it is defined once in the shared token system, **Then** every component using "primary" styling across the six screens reflects it.
2. **Given** a new component added later that reuses an existing semantic token (e.g. "card radius," "primary button"), **When** it renders, **Then** it automatically matches the new design without needing its own hardcoded values.

---

### Edge Cases

- What happens on a screen that mixes redesigned and not-yet-redesigned shared components (e.g. a shared nav bar used by both learner and instructor routes)? The shared component's new color tokens cascade there (Clarifications, Session 2026-10-02), but any new layout/shape treatment (e.g. pill-shaped nav links) stays scoped to the demo-learner bucket only -- the non-learner surface must not visually break or gain new structure it didn't have before.
- How does the system handle a learner on a screen state the mockups didn't depict (e.g. an empty state, an error state, a loading state)? These states must still render using the new design tokens even though no mockup explicitly covers them.
- What happens to in-flight interactive states the mockups show statically (e.g. the "Why this question?" expanded/collapsed disclosure, hover/focus states on pill buttons)? These must remain fully functional and keyboard-accessible in the new style, not just visually present in one state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Dashboard, Practice, Mastery, Placement, AI Tutor, and Answer Result screens MUST visually match the provided design mockups' color palette, typography, spacing, corner radii, and component shapes (pill-shaped buttons and nav, rounded cards).
- **FR-002**: The redesign MUST NOT alter grading, mastery-model, or sequencing logic, nor any navigation target, on any of the six screens. Display-level data composition MAY change where needed to match the mockups (Clarifications, second pass) -- prefer consuming a value already returned by an existing API response over fetching something new, and prefer a new client-side derivation from already-fetched data over a new network call, in that order.
- **FR-003**: Every already-shipped learner-facing behavior on these screens -- including the "why this question?" selection-reason disclosure, decay-aware mastery display, refreshed/recovery acknowledgment, per-criterion grading detail, mastery-over-time sparkline, and softened weak-area report -- MUST continue to function identically after the redesign.
- **FR-004**: The persistent demo-account badge MUST remain present and visually prominent, in the new style, on every redesigned demo-learner surface.
- **FR-005**: Non-color accessibility cues already established on these screens (elapsed-time text labels, required image alt text) MUST be preserved.
- **FR-006**: Shared visual values (color, type scale, spacing, radii) introduced by the redesign MUST be defined in the project's existing shared design-token system, not duplicated as one-off literal values per component.
- **FR-007**: Screens and components outside the six named screens (instructor dashboard, guardian/auth flows, non-learner nav buckets) are out of scope for layout, component-shape, and structural changes, which MUST NOT change as a side effect of this redesign. The shared color tokens (FR-006) are the one exception, by design: they are global, and their new values MUST cascade to out-of-scope surfaces rather than being duplicated into a second, scoped-only color system (Clarifications, Session 2026-10-02).
- **FR-008**: The redesign MUST introduce no new database table, column, or migration, and no new backend/API endpoint beyond the narrow exceptions FR-009/FR-010/FR-011/FR-012 permit.
- **FR-009**: Dashboard's "questions this week" stat tile MAY be backed by exactly one new, read-only backend endpoint (a count of this subject's `answer_submitted` events in the trailing 7 days for this learner) -- justified because no existing endpoint or already-fetched response exposes this number. That same endpoint's response MAY also carry a correct-answer count for the stat tile's sub-line ("N answered correctly"), computed from the same query.
- **FR-010**: Dashboard's "why this question?" disclosure MAY name the next topic's immediate prerequisite by adding one new field to the existing `topic-priority-preview` response (Clarifications, fourth pass) -- a read-only lookup against the Sequencing Agent's own already-loaded prerequisite graph for that request, not a new query shape or table.
- **FR-011**: Dashboard's "Refreshed!" banner MAY name a topic that recently crossed back above the mastered line by adding one new field to the existing `mastery-state` response (Clarifications, fourth pass) -- a read-only derivation over the existing `mastery_updated` audit log, approximating (not replaying exactly) `mastery_tool.py`'s existing `refreshed_from_bands` definition of "refreshed."
- **FR-012**: No other new backend surface beyond FR-009/FR-010/FR-011 is permitted under this feature.

### Key Entities

*(none -- this feature introduces no new persisted data or entity. FR-009's endpoint and FR-010/FR-011's additive response fields are all read-only queries/lookups over existing data (the `AssessmentEvent` audit log, the Sequencing Agent's prerequisite graph, `MasteryState`), not a new entity.)*

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the six redesigned screens, reviewed side by side against its mockup, matches the mockup's color, typography, spacing, radius, and shape values with zero unintentional deviations.
- **SC-002**: 100% of the existing frontend automated test suite passes unchanged after the redesign, with no test requiring a behavioral (non-visual-selector) change to keep passing.
- **SC-003**: The demo-account badge is present and visible on 100% of redesigned demo-learner screens.
- **SC-004**: Every non-color accessibility cue verified by an existing acceptance scenario in a prior spec (e.g. the "last practiced" text label, image alt text) still passes that same scenario after the redesign.
- **SC-005**: A learner completes each of the five core flows (start practicing, ask the tutor, view mastery, take placement, view an answer result) with identical functional outcomes before and after the redesign -- only the visual presentation differs.

## Assumptions

- The six exported design files (one per screen: Dashboard, Practice, Mastery, Placement, AI Tutor, Answer Result) are reference mockups: static HTML with hardcoded illustrative sample data. Their exact sample copy and numbers are not literal content requirements -- only their visual values (color, type, spacing, radii, shapes) are.
- Baloo 2 and Nunito are already the project's typography since Milestone 8; this feature does not introduce a new font or any new third-party dependency, so `tech-stack.md` needs no amendment.
- The instructor dashboard, guardian/auth flows, and the demo entry point are out of scope for this feature; only the six named learner-facing screens and the shared components they depend on are restyled.
- This is a visual-design-system update, not a new product milestone -- it does not add an entry to `roadmap.md`'s milestone sequence, consistent with how Milestone 8's own theme overhaul was handled as bundled work rather than a dedicated milestone.
- No real learner data is affected or newly displayed; synthetic demo-learner data continues to be the only data shown, per Constitution Principle VIII.
- FR-009's new endpoint reuses the existing `AssessmentEvent` audit-log table (Constitution Principle V) read-only -- no new table, no write path, no change to what's logged or why.
- FR-010's prerequisite-naming field and FR-011's recently-refreshed field are likewise read-only: no new table, no write path, no change to what's logged or why. FR-011's derivation is an approximation of `refreshed_from_bands`'s exact confirmation-streak-aware definition of "refreshed" -- the audit log doesn't persist `consecutive_mastered_observations` per event, so this can't replay that function exactly. This is accepted as good enough for a dashboard banner, not treated as a reason to add a new persisted field just to make the approximation exact.

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

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A learner sees the refreshed visual design with no change in behavior (Priority: P1)

A learner using the Dashboard, Practice, Mastery, Placement, AI Tutor, or Answer Result screens sees the new purple/lavender visual language -- pill-shaped buttons and nav, rounded cards, the updated color palette and type treatment -- while every interaction (starting practice, asking the tutor, reviewing mastery, taking placement, seeing a graded result) behaves exactly as it did before the redesign.

**Why this priority**: This is the entire point of the feature. Without behavioral parity, a styling update would risk silently breaking the product's actual functionality -- the one outcome a pure design-system refresh must never cause.

**Independent Test**: Load each of the six screens before and after the redesign with the same demo-learner state and confirm identical data, navigation targets, and interactive outcomes, with only visual presentation differing.

**Acceptance Scenarios**:

1. **Given** the Dashboard, Practice, Mastery, Placement, AI Tutor, and Answer Result screens, **When** each renders, **Then** its colors, typography, spacing, corner radii, and button/nav shapes match the corresponding design mockup's values.
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
- **FR-002**: The redesign MUST NOT alter the underlying data, business logic, navigation structure, or API calls made by any of the six screens.
- **FR-003**: Every already-shipped learner-facing behavior on these screens -- including the "why this question?" selection-reason disclosure, decay-aware mastery display, refreshed/recovery acknowledgment, per-criterion grading detail, mastery-over-time sparkline, and softened weak-area report -- MUST continue to function identically after the redesign.
- **FR-004**: The persistent demo-account badge MUST remain present and visually prominent, in the new style, on every redesigned demo-learner surface.
- **FR-005**: Non-color accessibility cues already established on these screens (elapsed-time text labels, required image alt text) MUST be preserved.
- **FR-006**: Shared visual values (color, type scale, spacing, radii) introduced by the redesign MUST be defined in the project's existing shared design-token system, not duplicated as one-off literal values per component.
- **FR-007**: Screens and components outside the six named screens (instructor dashboard, guardian/auth flows, non-learner nav buckets) are out of scope for layout, component-shape, and structural changes, which MUST NOT change as a side effect of this redesign. The shared color tokens (FR-006) are the one exception, by design: they are global, and their new values MUST cascade to out-of-scope surfaces rather than being duplicated into a second, scoped-only color system (Clarifications, Session 2026-10-02).
- **FR-008**: The redesign MUST introduce no new backend/API endpoint, response field, or database change.

### Key Entities

*(none -- this feature introduces no new data; it restyles the display of data that already exists)*

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

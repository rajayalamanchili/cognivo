# Phase 0 Research: Learner-Facing UI Redesign

No `NEEDS CLARIFICATION` markers exist in this feature's Technical Context --
every dependency, testing tool, and platform choice is already locked in
`tech-stack.md`. The research below covers the two real open questions:
how the new design values map onto the existing styling system, and how to
verify the restyle introduced no behavioral regression.

## 1. Where the new design values land

**Decision**: Extend `frontend/src/app/globals.css`'s existing `:root` /
`@theme inline` token block with the new mockups' color values (replacing
the current lilac/amber palette's hex values with the new purple/lavender
ones), and apply Tailwind's built-in radius/spacing utility classes
(`rounded-full` for pills, `rounded-3xl`/`rounded-[24px]` for cards) directly
in each component -- no new token category for radius.

**Rationale**: `globals.css`'s header comment states the system's own intent:
"changing the look later means editing this file, not every component" --
this feature is exactly that intended use. A grep of existing components
(`DashboardSubjectSection.tsx`, `MasteryView.tsx`, `QuestionCard.tsx`, etc.)
confirms they already consume semantic Tailwind classes (`bg-primary`,
`text-error`, `rounded-*`) rather than hardcoded hex values, so a palette
swap is a token-file edit plus a pass over each component's existing
`rounded-*`/spacing utility classes to match the new mockups' values -- not a
rewrite of each component's markup or logic.

**Alternatives considered**:
- *A new CSS-in-JS or styled-components layer*: rejected -- introduces a new
  dependency and pattern inconsistent with the Tailwind-v4-only approach
  locked since Milestone 1, for no benefit the existing token file doesn't
  already provide.
- *A new semantic radius token set (`--radius-pill`, `--radius-card`, etc.)
  in `globals.css`*: considered, since the mockups do use a small, consistent
  set of radius values (`999px` pills, `20-24px` cards, `12-16px` smaller
  elements). Left as an implementation-time judgment call for `/speckit-tasks`
  rather than locked here -- it's a maintainability nicety (spec's User Story
  3), not a correctness requirement, and Tailwind's existing arbitrary-value
  syntax (`rounded-[24px]`) already satisfies FR-001/FR-006 without it.

## 2. Verifying no behavioral regression

**Decision**: Reuse the existing Vitest + React Testing Library suite as the
regression gate (SC-002) -- tests that assert on visual classes/inline styles
may need literal updates (expected), but tests asserting on data, navigation,
or interaction outcomes must pass unchanged. Visual match against the
mockups (SC-001) is verified by manual side-by-side comparison, since no
visual-regression-screenshot tool is part of the locked `tech-stack.md`
testing stack and introducing one is disproportionate to a six-screen, one-
time restyle.

**Rationale**: Matches this project's existing testing philosophy (`tech-
stack.md`'s Testing & evaluation table) of using the already-locked tool for
each kind of check rather than adding a new one per feature. A pixel-perfect
automated visual-diff tool would be the first of its kind in this codebase
and isn't justified by a single redesign feature.

**Alternatives considered**:
- *Playwright visual-regression snapshots*: rejected for this feature --
  Playwright is already locked for deployment smoke tests/E2E, but adding
  snapshot-based visual assertions is a testing-strategy expansion beyond
  this feature's scope, better justified (if ever) by a dedicated spec once
  the design system is expected to change frequently.

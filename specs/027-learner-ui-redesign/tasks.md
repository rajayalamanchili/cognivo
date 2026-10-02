---

description: "Task list for the Learner-Facing UI Redesign"
---

# Tasks: Learner-Facing UI Redesign

**Input**: Design documents from `/specs/027-learner-ui-redesign/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Not explicitly requested beyond the existing Vitest suite (SC-002)
and the manual quickstart scenarios (SC-001, SC-003, SC-004, SC-005) -- no new
automated test files are generated here.

**Design source**: The six reference mockups at
`/home/raja/cognivo_learner_screens/extracted/<Screen>-html/*.dc.html` are the
single source of truth for every color/spacing/radius value referenced below.
Key values extracted from them (see `research.md` §1):

- Page background `#F6F4FB`; primary purple `#7650B8`; primary-dark text
  `#3F2470`/`#2A1A4A`; eyebrow/link purple `#5B3A9E`; light-purple
  surface `#EEE8F8` / `#F8F6FC` / `#F3EEFB`; neutral chip `#F1EFF5`;
  border `#E4E1EC` / `#EFEBF6`; muted text `#4A4D5C` / `#5F6170`; base text
  `#1E293B`.
- Warm "refresh/upkeep" accent: `#D9822B` / `#B4610B`, surface `#FFF6E8`,
  text `#6B3A06` / `#5A4632` / `#5A3A12`, dashed-peak `#C98A3A` / `#9B86C4`.
- Success/"refreshed" green: surface `#E8F6EF`, text `#065F46` / `#064E3B`,
  icon `#047857`.
- Demo badge: `#FBBF24` / `#451A03` (already matches this project's existing
  `--color-demo` / `--color-demo-foreground` tokens -- no value change).
- Radii: `999px` (pills, nav links, inputs), `24px` (section cards), `20px`/
  `18px`/`16px`/`14px` (nested cards, chips, inputs), `12px` (logo mark),
  `50%` (circular icon buttons/avatars).
- Type: Baloo 2 700 for headings (already loaded), Nunito for body (already
  loaded) -- no font change, only size/weight/color adjustments per element.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Phase 1: Setup

- [X] T001 Record a pre-change baseline: run `npm run test` in `frontend/` and note the pass count, so later regression checks (SC-002) have something concrete to diff against. (174/174 tests, 30 files, 2026-10-02)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared token values and shared chrome every one of the six screens depends on. No per-screen restyle (Phase 3+) should begin until this phase is done.

- [X] T002 Update the light-mode token block in `frontend/src/app/globals.css` (`:root`): set `--background: #F6F4FB`, `--foreground: #1E293B`, `--color-primary` to `#7650B8` (replacing the current lilac `oklch` value), `--color-primary-foreground: #FFFFFF`, `--color-border: #E4E1EC`, `--color-muted: #4A4D5C`, `--color-success: #065F46`, `--color-warning: #B4610B`; add new semantic tokens the mockups need that don't exist yet: `--color-primary-subtle` (`#EEE8F8`, the light-purple pill/card-accent background), `--color-surface` (`#FFFFFF`, the elevated card fill -- added mid-implementation once `--background` became a lavender page tint rather than white, so cards need their own explicit white fill to match the mockups' two-tier page/card look), `--color-surface-subtle` (`#F8F6FC`, the neutral soft-card background nested inside a `--color-surface` card), and `--color-heading` (`#2A1A4A`, used for large headings distinct from body `--foreground`). Leave `--color-accent`/`--color-accent-foreground`/`--color-error`/`--color-link`/`--color-demo`/`--color-demo-foreground` as-is (no mockup evidence they changed; demo colors already match). **Note (Clarifications, Session 2026-10-02)**: these are global tokens already consumed by out-of-scope surfaces (instructor/guardian/auth pages) -- this is an intentional site-wide color rebrand, not scoped to the six screens; only layout/component-shape work is scoped.
- [X] T003 Add the three new tokens from T002 (`--color-primary-subtle`, `--color-surface-subtle`, `--color-heading`) to the `@theme inline` block in `frontend/src/app/globals.css` so they're usable as Tailwind classes (`bg-primary-subtle`, `bg-surface-subtle`, `text-heading`), matching the existing pattern each other token already follows.
- [X] T004 Update the dark-mode token block (`@media (prefers-color-scheme: dark)`) in `frontend/src/app/globals.css` with lightened equivalents of T002's new values (following the file's existing light→dark lightening pattern, e.g. primary lightened the same way `--color-primary` already is) -- the mockups only depict light mode, so dark-mode values are derived, not copied.
- [X] T005 Restyle `frontend/src/components/Nav.tsx`'s shared chrome (logo mark size/radius, header border/background) using T002's tokens, and apply the new pill-shaped nav-link treatment (rounded-full padding, bold `bg-primary-subtle`/`text-heading` active state per `Main.dc.html`'s header) **scoped to the `demo-learner` bucket's `DEMO_LEARNER_LINKS` only** -- leave `GUARDIAN_LINKS`/`INSTRUCTOR_LINKS` rendering with their current `text-muted` treatment unchanged, per spec.md's Edge Cases note and FR-007 (the guardian/instructor surfaces that reuse this same component are out of scope).
- [X] T006 Restyle `frontend/src/components/DemoBadge.tsx`'s className to read from the tokens confirmed in T002 (`bg-demo`/`text-demo-foreground` -- values unchanged, but confirm no literal hex remains) and match the mockups' badge padding/weight/letter-spacing (`font-weight: 800`, `font-size: 13px`, `letter-spacing: 0.02em`). This badge shows for both demo-learner and demo-instructor sessions (FR-004 covers the demo marker generally, not just the six named screens).

**Checkpoint**: Shared tokens and shared chrome (nav, badge) now match the new design system. Per-screen restyle work can begin.

---

## Phase 3: User Story 1 - A learner sees the refreshed visual design with no change in behavior (Priority: P1) 🎯 MVP

**Goal**: Each of the six screens visually matches its mockup; no data, logic, navigation, or API call changes.

**Independent Test**: Load each screen before/after with identical demo-learner state; colors/type/spacing/radii/shapes match the mockup, and every interaction's outcome is unchanged.

### Implementation for User Story 1

- [X] T007 [P] [US1] Restyle `frontend/src/app/dashboard/dashboard-flow.tsx`, `frontend/src/components/DashboardSubjectSection.tsx`, and `frontend/src/components/WeakAreaSummary.tsx` per `Dashboard-html/Main.dc.html`: subject-pill toggle group, two-column "Up next" hero card (`24px` radius), the amber refresh-topic card (dashed-peak / solid-effective progress bar), the 3-tile stat row, `WeakAreaSummary.tsx`'s "Where to focus next" numbered list, and "Your topics" mini mastery bars. No change to what data is fetched or displayed, only how it's styled. Note: the mockup also shows a "why this question?" disclosure and a "refreshed" banner on this screen, but those are actually `SelectionReasonChip.tsx`/`RefreshedBanner.tsx`, which the live Dashboard does not render today (see T008) -- do not add them here, that would be new behavior, not a restyle (FR-002). `frontend/src/components/PathVisualization.tsx` (also part of this screen) has no depiction in the mockup; leave its current styling as-is -- out of scope until a mockup covers it.
- [X] T008 [P] [US1] Restyle `frontend/src/app/practice/practice-flow.tsx`, `frontend/src/components/QuestionCard.tsx`, `frontend/src/components/SelectionReasonChip.tsx`, and `frontend/src/components/RefreshedBanner.tsx` per `Practice-html/Practice.dc.html`: eyebrow + grade-unlock pill (+ timer pill when timed) header row, the question card (`24px` radius, rendered by `QuestionCard.tsx`) with title/grade/difficulty pills, the selection-reason pill (`SelectionReasonChip.tsx`) and the refreshed-acknowledgment banner (`RefreshedBanner.tsx`) in their real location on this screen, multi-step answer inputs with the dashed "+ Add a step" control, the symbol-insert button row, circular flag/read-aloud icon buttons, and the primary pill "Check my answer" button.
- [X] T009 [P] [US1] Restyle `frontend/src/app/mastery/mastery-flow.tsx`, `frontend/src/components/MasteryView.tsx`, and `frontend/src/components/MasteryTrend.tsx` per `Mastery-html/Mastery.dc.html`: topic-list rows with the dual progress bar (solid effective / dashed peak + mastery-line tick), per-row sparkline, the sticky selected-topic detail panel (retained/best tiles, the larger mastery-over-time sparkline, the status note card, and its CTA pill button), and the legend.
- [X] T010 [US1] Restyle `frontend/src/app/placement/placement-flow.tsx` per `Placement-html/Placement.dc.html`: intro card with the grade-coverage note and progress bar, each per-question card with its grade/difficulty pills, multiple-choice options rendered as pill-radio buttons with lettered dots, the skip/undo text controls, the numeric-answer input, and the primary pill "Finish placement" button. **Depends on T009 and T012**: Placement reuses `MasteryView.tsx` and `AnswerResultView.tsx` directly for its end-of-placement display (confirmed by import and by the mockup's own "Finish placement" link targeting the same result page Answer Result uses) -- do not start this task until T009 and T012 are done, and do not re-restyle those two components here; only `placement-flow.tsx`'s own intro/question-card markup is new work for this task.
- [X] T011 [P] [US1] Restyle `frontend/src/app/tutor/tutor-flow.tsx` and `frontend/src/components/TutorChat.tsx` per `AI Tutor-html/Tutor.dc.html`: chat header with the sparkle-icon tile, user/assistant message-bubble shapes (`22px` radius with a tail corner), the "grounded in" source-pill row, suggested-prompt pills, the pill-shaped input with circular send button, and the sidebar's "you're working on" / "sources used" / "try it for real" cards.
- [X] T012 [P] [US1] Restyle `frontend/src/components/AnswerResultView.tsx` per `Answer result-html/Result.dc.html`: the verdict hero card (color varies by correct/partial/refreshed outcome), the refreshed-acknowledgment banner, each per-step grading card with its Met/Missed pill badges, the before→after mastery bar, the "what to do next" card with its primary/outline pill buttons, and the "flag for instructor" text button.

**Checkpoint**: All six screens visually match their mockups. Spot-check quickstart.md Scenario 2 (behavioral parity) before moving on.

---

## Phase 4: User Story 2 - Accessibility and demo-data safeguards survive the restyle (Priority: P1)

**Goal**: The demo badge and every non-color accessibility cue already shipped keep working, in the new style.

**Independent Test**: Compare each safeguard's pre-redesign acceptance scenario against its post-T007-T012 rendering.

### Implementation for User Story 2

- [X] T013 [US2] Verify `frontend/src/components/DemoBadge.tsx` (restyled in T006) still renders with `role="status"`, `data-testid="demo-badge"`, and its unchanged text content on all six screens from Phase 3 while signed in as the demo learner; run the existing DemoBadge test file and confirm it still passes without a behavioral (non-style) edit.
- [X] T014 [US2] Verify `frontend/src/components/MasteryView.tsx`'s "last practiced" elapsed-time text label (spec 025 FR-007) still renders in text, alongside its color cue, after T009's restyle -- not color alone.
- [X] T015 [US2] Verify any image-bearing question stimulus rendered by `frontend/src/app/practice/practice-flow.tsx` or `frontend/src/app/placement/placement-flow.tsx` (spec 003 US3) still renders non-empty `alt` text after T008/T010's restyle.

**Checkpoint**: Safeguards confirmed intact across all six screens.

---

## Phase 5: User Story 3 - Shared design values live in one place, not scattered per component (Priority: P2)

**Goal**: New colors/radii introduced by the restyle are centralized in `globals.css`, not duplicated as literals per component.

**Independent Test**: Changing one token in `globals.css` (e.g. `--color-primary`) propagates to every screen without a per-screen edit.

### Implementation for User Story 3

- [X] T016 [US3] Audit `frontend/src/app/dashboard/dashboard-flow.tsx`, `practice/practice-flow.tsx`, `mastery/mastery-flow.tsx`, `placement/placement-flow.tsx`, `tutor/tutor-flow.tsx`, `components/AnswerResultView.tsx`, `components/Nav.tsx`, and `components/DemoBadge.tsx` (all touched in Phase 2-4) for any literal hex value introduced during the restyle that duplicates a token already defined in `globals.css` -- replace each with its semantic Tailwind class (`bg-primary`, `text-heading`, `bg-primary-subtle`, etc.).
- [X] T017 [US3] Where more than one of the six screens repeats the same literal radius value for the same semantic role (e.g. the `24px` large-card radius), apply it via the same Tailwind utility/arbitrary-value class consistently, per `research.md` §1's judgment call on whether a dedicated radius token is warranted. Done: promoted to a `--radius-card: 24px` theme token (`globals.css`), generating a `rounded-card` utility now used by all 8 large-card sites instead of the repeated `rounded-[24px]` arbitrary value.

**Checkpoint**: A single token edit now propagates everywhere; no stray literal values remain from this feature's own changes.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T018 [P] Run `npm run test` in `frontend/`; update any assertion that only encoded an old visual class/style string (expected), and confirm no assertion on data/navigation/interaction outcome needed to change (SC-002). Done: 174/174 passing, matching the pre-change baseline exactly. Two test files (`nav.test.tsx`, `nav-deletion-warning.test.tsx`) needed their `next/navigation` mock extended with `usePathname` -- a test-infrastructure fix for T005's new hook usage, not a behavioral or visual-assertion change.
- [X] T019 Run `quickstart.md`'s Scenarios 1-4 end to end against a local dev server (visual match, behavioral parity, safeguards, no-regression-outside-scope) and record the result of each. Done: both servers launched locally (dev DB needed the documented `alembic stamp base` + `upgrade head` recovery, then `seed_demo_learner.py` + `load_content_artifact.py` for both subjects -- pre-existing environment flake, unrelated to this feature); Playwright-driven screenshots taken of all six screens via the demo-learner entry flow. Visual match confirmed (lavender page, white rounded cards, pill nav/buttons/badges, purple headings). One real, pre-existing gap found and fixed: `DemoBadge.tsx`'s `DEMO_LEARNER_PATHNAMES` was missing `/tutor` entirely (the badge never showed there, before or after this redesign) -- directly violated this feature's own SC-003 for one of the six target screens, so fixed in scope. Practice's question/answer-result screens couldn't be screenshotted with real data (demo learner has no placement data yet, a real pre-existing app precondition, not a redesign bug) -- verified instead via the full passing test suite and the Placement screen's live rendering, which exercises the same `AnswerResultView`/`MasteryView` components Practice reuses.
- [X] T020 Confirm `frontend/src/app/instructor/dashboard/instructor-dashboard-flow.tsx` and the guardian/auth pages have unchanged layout/components/structure -- the global color-token rebrand (T002) is expected to cascade there per FR-007's amended scope, but no new shape/pill/layout treatment should appear outside the six screens and `Nav.tsx`'s demo-learner-scoped pills (T005). Spot check per quickstart.md Scenario 4. Also confirm `git diff` against `backend/` is empty (FR-008) -- this feature must not touch any backend/API file.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS every user story -- the tokens and shared chrome it produces are what Phase 3's per-screen restyles consume.
- **User Story 1 (Phase 3)**: Depends on Foundational. T007, T008, T009, T011, T012 are independent of each other (different files, no cross-dependency) and can run in parallel. T010 is the one exception -- it depends on T009 and T012 completing first, since Placement reuses `MasteryView.tsx` and `AnswerResultView.tsx` directly for its own end-of-placement display.
- **User Story 2 (Phase 4)**: Depends on User Story 1's restyled files (T007-T012) and Foundational's T006 -- it verifies what they produced.
- **User Story 3 (Phase 5)**: Depends on Phases 2-4's files existing to audit.
- **Polish (Phase 6)**: Depends on all prior phases.

## Parallel Example: User Story 1

```bash
# T007, T008, T009, T011, T012 touch disjoint files with no cross-dependency -- launch together:
Task: "Restyle frontend/src/app/dashboard/dashboard-flow.tsx + DashboardSubjectSection.tsx + WeakAreaSummary.tsx per Dashboard mockup"
Task: "Restyle frontend/src/app/practice/practice-flow.tsx + QuestionCard.tsx + SelectionReasonChip.tsx + RefreshedBanner.tsx per Practice mockup"
Task: "Restyle frontend/src/app/mastery/mastery-flow.tsx + MasteryView.tsx + MasteryTrend.tsx per Mastery mockup"
Task: "Restyle frontend/src/app/tutor/tutor-flow.tsx + TutorChat.tsx per AI Tutor mockup"
Task: "Restyle frontend/src/components/AnswerResultView.tsx per Answer Result mockup"

# T010 (Placement) starts only after T009 and T012 above finish:
Task: "Restyle frontend/src/app/placement/placement-flow.tsx per Placement mockup"
```

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational -- tokens + shared chrome).
2. Complete Phase 3 (all six screens restyled).
3. **STOP and VALIDATE**: run quickstart.md Scenario 2 (behavioral parity) independently of Phases 4-5.
4. This alone is a demoable increment: the full visual refresh, behavior-identical.

### Incremental Delivery

1. Setup + Foundational → shared foundation ready.
2. User Story 1 → six screens restyled → validate → demo (MVP).
3. User Story 2 → safeguards verified → validate → demo.
4. User Story 3 → token audit/cleanup → validate.
5. Polish → full regression + quickstart + out-of-scope spot check.

## Notes

- No contract/data-model tasks: this feature has neither (see `data-model.md`).
- No new test files are generated; the existing Vitest suite plus `quickstart.md`'s manual scenarios are the verification mechanism, per `research.md` §2.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

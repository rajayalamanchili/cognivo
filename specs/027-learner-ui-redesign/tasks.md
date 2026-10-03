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
- [X] T009 [P] [US1] Restyle `frontend/src/app/mastery/mastery-flow.tsx`, `frontend/src/components/MasteryView.tsx`, and `frontend/src/components/MasteryTrend.tsx` per `Mastery-html/Mastery.dc.html`: topic-list rows with the dual progress bar (solid effective / dashed peak + mastery-line tick), per-row sparkline, the sticky selected-topic detail panel (retained/best tiles, the larger mastery-over-time sparkline, the status note card, and its CTA pill button), and the legend. **Correction (Phase 9)**: this pass only shipped the token/shape restyle of the flat list; the master-detail layout, legend, mastery-line tick, and detail panel were never actually built then (a `<select>`-driven trend stood in for all of it) -- closed for real in T037-T040.
- [X] T010 [US1] Restyle `frontend/src/app/placement/placement-flow.tsx` per `Placement-html/Placement.dc.html`: intro card with the grade-coverage note and progress bar, each per-question card with its grade/difficulty pills, multiple-choice options rendered as pill-radio buttons with lettered dots, the skip/undo text controls, the numeric-answer input, and the primary pill "Finish placement" button. **Depends on T009 and T012**: Placement reuses `MasteryView.tsx` and `AnswerResultView.tsx` directly for its end-of-placement display (confirmed by import and by the mockup's own "Finish placement" link targeting the same result page Answer Result uses) -- do not start this task until T009 and T012 are done, and do not re-restyle those two components here; only `placement-flow.tsx`'s own intro/question-card markup is new work for this task.
- [X] T011 [P] [US1] Restyle `frontend/src/app/tutor/tutor-flow.tsx` and `frontend/src/components/TutorChat.tsx` per `AI Tutor-html/Tutor.dc.html`: chat header with the sparkle-icon tile, user/assistant message-bubble shapes (`22px` radius with a tail corner), the "grounded in" source-pill row, suggested-prompt pills, the pill-shaped input with circular send button, and the sidebar's "you're working on" / "sources used" / "try it for real" cards. **Correction (gap-closing pass, 2026-10-03)**: this pass only shipped the message-bubble shapes; the header card, suggested-prompt pills, pill input/circular send button, and "try it for real" sidebar card were closed for real in a follow-up gap-closing pass the same day. The remaining three -- "grounded in" pills, "sources used in this chat", "you're working on" -- needed real data this spec's "visual restyle only, no new data" constraint put out of scope for a pure restyle; closed in a second follow-up pass the same day, user-directed ("fix the remaining gaps, make backend changes if needed"), with small scoped backend changes: `_authorize_exchange_inspection` (`backend/src/api/routes/tutor.py`) now carves out the demo learner (mirrors `_authorize_learner`'s existing FR-001 no-auth path) so the Tutor page can call the pre-existing `GET /api/tutor/exchanges/{id}` for its own session's citations -- no new endpoint needed there. "You're working on" needed no backend change at all: reuses the existing `GET /api/learners/{id}/topic-priority-preview` endpoint (the same Sequencing Agent pick Dashboard's "up next" card already shows). "New chat" needed one new endpoint, `POST /api/tutor/sessions/{id}/end` (`backend/src/services/tutor/session.py`'s `end_session`), since `openTutorSession` is get-or-create (FR-014) and previously had no way to stop resuming the same session.
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
- [X] T020 Confirm `frontend/src/app/instructor/dashboard/instructor-dashboard-flow.tsx` and the guardian/auth pages have unchanged layout/components/structure -- the global color-token rebrand (T002) is expected to cascade there per FR-007's amended scope, but no new shape/pill/layout treatment should appear outside the six screens and `Nav.tsx`'s demo-learner-scoped pills (T005). Spot check per quickstart.md Scenario 4. **Superseded by the second pass below**: `git diff` against `backend/` is no longer expected to be empty -- FR-009 permits exactly one new endpoint (T021). Confirmed `git diff --stat -- backend/` touches only `src/api/main.py` (router registration) and the new `src/api/routes/activity_summary.py` -- no model, migration, or existing route changed.

---

## Phase 7: Mockup-Fidelity Pass (second pass, user-directed: "stay true to the mockup and add data UI if needed, update the spec if needed")

**Purpose**: Close the two gaps the original Polish pass disclosed as simplifications -- Dashboard's missing subject-toggle/Up-next-hero/refresh-card/stat-tiles, and Answer Result's missing mastery before→after bar -- per spec.md's second and third Clarifications sessions.

- [X] T021 Add `backend/src/api/routes/activity_summary.py` (`GET /api/learners/{id}/activity-summary?subject_id=`), the one new endpoint FR-009 permits -- a read-only count of `answer_submitted` events in the trailing 7 days, following `sequencing_preview.py`'s exact pattern (same auth dependency, same response-model shape). Registered in `backend/src/api/main.py`. No new table, no migration.
- [X] T022 Add `prior_p_mastery` to `AnswerResultView.tsx`'s `AnswerResultViewData` Pick (already present on every source response type -- `AnswerResult`, `PlacementQuestionResultEntry`, `QuizAnswerResultEntry` -- just never consumed) and render a real before→after mastery bar in a new "YOUR MASTERY" card, shown only when `prior_p_mastery` is non-null (a learner's very first answer on a topic has no "before" to show). Zero new data fetched.
- [X] T023 Restructure `dashboard-flow.tsx` with a subject-pill toggle (one subject shown at a time, switching via existing `subjects` data) and rebuild `DashboardSubjectSection.tsx` with an "Up next" hero (topic + why-text, derived from already-fetched `topic-priority-preview`'s `next_topic`/`is_fallback` plus `mastery-state`'s per-topic `p_mastery`/`effective_p_mastery` -- reusing `SelectionReasonChip.tsx`'s exact decay-detection logic, duplicated locally per `explainabilityCopy.ts`'s own stated precedent against shared abstractions here), a refresh card (same decay derivation, reused from `MasteryView.tsx`'s existing `effective < peak` check), and a 3-tile stat row (topics mastered + ready-to-refresh derived client-side; questions-this-week from T021's new endpoint). Preserved the exact `dashboard-weak-area-slot`/`dashboard-path-slot` failure-isolation contract `dashboard-failure-isolation.test.tsx` depends on.
- [X] T024 Add `backend/tests/integration/test_activity_summary.py` (3 tests: counts only within the trailing week, zero-events returns 0 not 404, other event types not counted) -- all passing.
- [X] T025 Re-ran the full regression (`frontend` 175/175, `backend` 786/786, production build clean) and re-verified live: completed a real placement, confirmed Dashboard's Up-next/stat-tiles/mastery list render real derived values (including a live `questions_this_week: 5` from T021's endpoint), confirmed Placement's first-ever-answer results correctly omit the mastery bar (no `prior_p_mastery` yet), and confirmed a second real Practice answer renders the mastery bar correctly (45% → 77%, matching the actual BKT update).

---

## Phase 8: Dashboard Mockup-Fidelity Pass, Round 2 (user-directed: "fix all deferred items and gaps")

**Purpose**: Close the two gaps T007's own note explicitly deferred as "new behavior, not a restyle" (the why-disclosure panel, the "Refreshed!" banner), plus two silent gaps an audit found (the refresh card's progress bar, the stat tiles' sub-lines) -- per spec.md's fourth Clarifications session.

- [X] T026 Add `questions_correct_this_week` to `backend/src/api/routes/activity_summary.py`'s `ActivitySummaryResponse` (FR-009 amendment) -- same query as T021's, filtered in Python against the JSON `payload` column (`misconception/classify.py`'s existing precedent). Updated `test_activity_summary.py`.
- [X] T027 Add `next_topic_prerequisite_display_name` to `TopicPriorityPreview` (`agents/sequencing/agent.py`) and `TopicPriorityPreviewOut` (`api/routes/sequencing_preview.py`), FR-010 -- a direct (non-recursive) lookup against `_load_topic_ranking_context`'s already-loaded `prereqs_by_topic` map for the chosen `next_topic`, `None` for a fallback pick or a topic with no prerequisite. Added two cases to `test_topic_priority_preview.py`.
- [X] T028 Add `backend/src/services/mastery/recently_refreshed.py` (`find_recently_refreshed_topic`), FR-011 -- read-only derivation over `mastery_updated` events, approximating `mastery_tool.py`'s `refreshed_from_bands`. Wired into `mastery.py`'s `MasteryStateResponse` as `recently_refreshed_topic_id`. Added `test_recently_refreshed_topic.py` (5 cases: genuine recovery, first-time-mastery exclusion, outside-window exclusion, currently-not-mastered exclusion, no-events case).
- [X] T029 `DashboardSubjectSection.tsx`: refresh card's dashed-peak/solid-effective progress bar with "Retained X% / Your best Y%" labels (from already-fetched `p_mastery`/`effective_p_mastery`, zero new data); each stat tile's sub-line (subject name, "N answered correctly" from T026, static "Practice restores it"); "Why this question?" expand/collapse disclosure (collapsed by default, `aria-expanded`) rendering picked-because/current-estimate/recorded-by rows from T027's new field plus already-fetched mastery values; "Refreshed!" banner from T028's new field. Per-card `displayName` heading changed from visible `<h2>` to `sr-only` (mockup has no visible per-card heading once the subject-pill toggle exists; kept for accessibility when there's only one subject and no pills render).
- [X] T030 `dashboard-flow.tsx`: header copy changed from static "Your Dashboard" to "Welcome back, {learner's real display name}" plus a generic (non-data-fabricating) subtitle line, matching the mockup's two-line header structure.
- [X] T031 Added `tests/unit/dashboard-mockup-fidelity.test.tsx` (6 cases covering the disclosure's collapsed/expanded states and keyboard-reachable toggle, the progress bar, both stat sub-lines, and the refreshed banner's presence/absence) and updated every existing `TopicPriorityPreview`/`MasteryStateResponse` test fixture for the two new required fields. Full regression: `frontend` 181/181, `backend` pytest full suite green.
- [X] T032 Widened `dashboard-flow.tsx`'s content column from `max-w-3xl` (768px) to `max-w-[1180px]`, matching the mockup -- the UP NEXT hero's two-column grid, the 3-tile stat row, and the focus/topics two-column grid were all collapsing to their mobile/stacked layout at the old width since their `md:`/`sm:` breakpoints never had room to trigger.
- [X] T033 `Nav.tsx`: added a centered `max-w-[1180px]`/`h-[68px]` header container and an avatar-bubble-plus-name element for the demo-learner bucket only (Edge Cases: new layout/shape treatment stays scoped there, same as T006's existing pill-link scoping), fetching the real seeded demo learner's `display_name` via the already-existing `getDemoLearner()`. User feedback on the first pass (Personalization Evidence/Exit Demo/Sign In rendered as inline text next to the avatar) was to tuck those three behind a click on the avatar/name instead -- rebuilt as a dismissible dropdown (`role="menu"`, closes on outside click) triggered by that one button, closer to the mockup's single clean header row. Updated `tests/unit/nav.test.tsx` for the new menu-gated assertions; added one new case for the avatar/name and the dropdown's open/close behavior. Full regression: `frontend` 182/182, `backend` 793/793.
- [X] T034 Ran the app end-to-end locally (backend + frontend, demo-learner flow through a real placement) rather than relying on the test suite alone, and fixed three real bugs it surfaced: (1) added `w-full` alongside `max-w-*`/`mx-auto` on all six screens' top-level content wrappers (`dashboard-flow.tsx`, `practice-flow.tsx` x4, `mastery-flow.tsx`, `placement-flow.tsx` x2, `tutor-flow.tsx` x2) -- `mx-auto` alone disables flex-item cross-axis stretch inside the root layout's `flex flex-col` `<body>`, so every one of these columns was silently shrinking to its content's natural width instead of actually reaching its intended `max-w-*`; (2) corrected every drifted font size in `DashboardSubjectSection.tsx`/`dashboard-flow.tsx` against the mockup's literal inline values (welcome heading 32px→40px, UP NEXT topic heading 26px→32px, stat-tile value 28px→36px, section headings 20px→26px, several smaller 14/15/16/17px drifts) -- a pixel-level check the original restyle pass hadn't caught; (3) fixed a real React hydration-mismatch in `Nav.tsx` (`demoLearnerMode` read `localStorage` synchronously in a `useState` initializer, differing between SSR and the client's first render) by starting it at `false` and correcting it in the existing post-mount effect, same pattern `accountType` already used. Full regression after all three fixes: `frontend` 182/182 (TypeScript clean), zero browser console errors on a real demo-learner Dashboard load before and after a real placement.
- [X] T035 Removed `PathVisualization.tsx`'s standalone "Assessed so far"/"Up next"/"Likely coming up" block from Dashboard, per spec.md's fifth Clarifications session -- "Assessed so far" and "Up next" were fully redundant with "Your topics" and the hero respectively; folded the one non-redundant piece ("Likely coming up" + FR-004's illustrative disclosure) directly into the UP NEXT hero. Deleted `src/components/PathVisualization.tsx` and `tests/unit/path-visualization.test.tsx` (now fully unused -- Dashboard was its only consumer). Moved the `dashboard-path-slot` loading/error states to gate the hero itself. Updated `dashboard-failure-isolation.test.tsx`'s FR-008 test (now asserts the hero/"UP NEXT" label is absent on failure, not a deleted `path-visualization` testid) and added two cases to `dashboard-mockup-fidelity.test.tsx` for the "Likely coming up" line (capped at 3, omitted when empty). Full regression: `frontend` 180/180 (net -2 after removing 4 PathVisualization-only tests and adding 2 new ones), TypeScript clean, zero browser console errors.
- [X] T036 `MasteryView.tsx`'s per-topic status bar only rendered at all for assessed topics -- a not-yet-assessed topic showed just its pill with no bar beneath, while both the Dashboard and Mastery mockups always show every row's empty (unfilled) track for visual consistency down the list. `MasteryBar` now always renders its track; the dashed-peak and colored-fill overlays stay conditional on actually having `p_mastery`/`band` data. Shared component (Dashboard, Mastery screen, Placement's end-of-placement display all use it), so this fix applies everywhere it's rendered, matching all three mockups' identical track-always-visible pattern. Added `data-testid="mastery-bar"`/`"mastery-bar-fill"` and two new `mastery-view.test.tsx` cases (track-without-fill for unassessed, track-with-fill for assessed). Full regression: `frontend` 182/182.

---

## Phase 9: Mastery Mockup-Fidelity Pass (user-directed: "check and fix if mastery mockup and mastery page in app doesn't match")

**Purpose**: T009 was checked off during the original User Story 1 pass, but only the flat topic list and a `<select>`-driven trend were ever built -- the mockup's master-detail layout (clickable topic rows + a sticky detail panel defaulting to the first assessed topic), legend, mastery-line tick, and status-driven note/CTA were never closed. Same class of gap as Phase 7/8's Dashboard/Answer-Result passes, just never caught for this screen until now.

- [X] T037 `MasteryView.tsx`: added optional `selectedTopicId`/`onSelectTopic`/`showMasteryLine` props. When `onSelectTopic` is passed, each row renders as a selectable `<button aria-pressed>` instead of a static `<li>`; `MasteryBar` gained a `showMasteryLine` tick at the same 0.7 cutoff `AnswerResultView` already mirrors (`MASTERED_THRESHOLD_PCT`). Omitted everywhere the prop isn't passed (Dashboard's mini list, Placement's end-of-placement summary), so their existing non-interactive rendering is byte-for-byte unchanged.
- [X] T038 `MasteryTrend.tsx`: added a `size` prop (`"sm"` default, unchanged 160x40; `"lg"` 320x100 for the Mastery screen's detail panel) and a `showMasteryLine` option that draws the same dashed threshold reference the mockup's big chart shows, plus static "First answer"/"Today" captions at `size="lg"`.
- [X] T039 Rebuilt `mastery-flow.tsx` as the mockup's two-column master-detail layout: eyebrow ("{SUBJECT} · N TOPICS", subject display name from the already-available `getSubjects()`), 40px heading, subtitle copy, and the Retained-now/Your-best/Mastery-line legend; left column is the now-interactive `MasteryView`; right column is a sticky detail panel (stat tiles, the enlarged trend chart, a status note, a static "how this number is worked out" explainer, and a CTA) that defaults to the first assessed topic (first topic overall if none are assessed yet) and updates on row click. The topic's status note/CTA/pill (`not-started` / `refresh-due` / `mastered` / `in-progress`) is derived entirely from fields the mastery-state response already carries (`status`, `p_mastery` vs `effective_p_mastery` against the same 0.7 cutoff) -- no new fetch. CTA always targets the existing `/practice?subject=X` link (same target Dashboard already uses) rather than inventing per-topic practice routing, since none exists; amber for `refresh-due` (`--color-warning`, same token the mockup uses for that state), purple otherwise. Removed the old `<select>`-driven trend picker.
- [X] T040 Initially deferred the mockup's per-row sparkline (eagerly fetching every topic's history is exactly what FR-012's "fetched on demand... a learner may never look at most of them" design note was written to avoid) -- user-directed follow-up ("implement per-row sparklines as well") overrode that. Implemented as a bounded fan-out instead of a new batch endpoint: `mastery-flow.tsx` fetches every *assessed* topic's history in parallel (`Promise.all`, skipping `"unknown"` topics -- they have no history) once topics load, keyed into a `historyByTopic` map; the detail panel's own big chart now reads from this same map instead of its own separate per-selection fetch, so this is net one fewer distinct fetch path, not two. A subject has at most a handful of topics, so this is a small bounded read-only fan-out, not an N+1 that scales badly. `MasteryView` takes an optional `historyByTopic` prop (omitted everywhere but the Mastery screen, so Dashboard/Placement never render a sparkline their own mockups don't show) and renders a `MasteryTrend` alongside each row's bar at a new `size="row"` (120x36, matching the mockup exactly); a topic with 0-1 recorded points renders no sparkline rather than the detail-panel's "not enough history yet" text, which doesn't fit in 120px.
- [X] T041 Added `tests/unit/mastery-flow.test.tsx` (6 cases: eyebrow/heading/legend render; detail panel defaults to the first assessed topic with decay correctly flagged as "Refresh due"; clicking a different row swaps the detail panel; an unassessed topic shows the not-started note/CTA; a topic with recorded history shows a per-row sparkline, one without does not) plus new cases in `mastery-view.test.tsx` (mastery-line tick opt-in, per-row sparkline scoped to each topic's own history, row selection/`aria-pressed`) and `mastery-trend.test.tsx` (`size="row"` renders a line for 2+ points, renders nothing rather than the sm/lg text fallback for exactly 1 point). Full regression: `frontend` 202/202, TypeScript clean, zero ESLint errors (fixed one `react-hooks/set-state-in-effect` by deriving the default selection instead of seeding it via `useEffect` + `setState`).
- [X] T042 Verified live against the running dev servers (backend + frontend already up, real seeded demo-learner data for `algebra-1` covering mastered/developing/struggling/not-yet-assessed topics): screenshotted the master-detail layout, the "In progress" and "Not started" detail-panel states via row clicks, zero browser console errors. The seeded demo data has no currently-decayed topic, so the "Refresh due" panel/amber-CTA path was verified via T041's unit test rather than a live screenshot. Re-verified after T040's sparkline follow-up: screenshotted the full topic list, confirming a sparkline renders for each topic with 2+ recorded mastery points and none for not-yet-assessed/insufficient-history topics, zero console errors.

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

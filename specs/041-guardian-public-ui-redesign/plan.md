# Implementation Plan: Guardian & Public-Facing UI Redesign

**Branch**: `041-guardian-public-ui-redesign` | **Date**: 2026-10-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/041-guardian-public-ui-redesign/spec.md`

## Summary

Restyle Home, Sign-in, Try the demo, Guardian · My learners, Assigned quiz,
and Settings to the same purple/lavender visual language spec 027 already
established for the solo-learner screens, updating the existing
`globals.css` design-token system and Tailwind classes -- no new dependency.
Bundled with that restyle, four real functional gaps found during
`/speckit-clarify` get closed: (1) a genuinely new, persisted guardian
Settings page (account edit, change password, accessibility/notification
preferences, deletion wiring), (2) real-learner access to Dashboard,
Practice, Mastery, and AI Tutor -- extending the exact session pattern
`LearnerAssignments.tsx` already proved for assigned quizzes to four more
existing pages plus `Nav`/`DemoBadge`, (3) a guardian-facing, instructor
opt-in class directory so joining a class no longer strictly requires a
shared code, and (4) the identity-safety guard (FR-022) those first two
require. Zero new third-party dependency; eleven new/changed database
columns across four existing tables (no new table); several new or
extended backend routes, all following this codebase's existing
FastAPI route-per-concern pattern.

## Technical Context

**Language/Version**: TypeScript (Next.js 16 / React 19) for frontend, Python (FastAPI) for backend -- both already locked, `tech-stack.md` Frontend/Backend rows

**Primary Dependencies**: Tailwind CSS v4 token system (`frontend/src/app/globals.css`), `next/font/google` (Baloo 2 + Nunito, already loaded) for the restyle; `argon2-cffi` (`services/auth/passwords.py`) + `pyjwt` (`services/auth/tokens.py`) for the Settings account/password work -- all already-locked dependencies, no new one added

**Storage**: PostgreSQL via Neon (existing). Eleven new columns across four existing tables (`real_guardian_accounts`, `real_instructor_accounts`, `learner_profiles`, `classroom_rosters`) -- zero new tables, per the spec's FR-015 constraint and this codebase's existing "flat columns on the owning entity" precedent (`LearnerProfile.career_connections_enabled`)

**Testing**: `pytest` (backend), `Vitest` + React Testing Library (frontend) -- existing suites extended, no new tooling

**Target Platform**: Web, deployed via Vercel (existing target, unchanged)

**Project Type**: Web application -- both `frontend/` and `backend/` touched (unlike spec 027, which was frontend-only)

**Performance Goals**: N/A for the restyle itself. The four gap-closing additions reuse already-ownership-gated, already-performant endpoints (mastery-state, activity-summary, recommendations, next-question) -- no new performance budget needed beyond what those endpoints already meet.

**Constraints**: Zero grading/mastery/sequencing-logic change (FR-002); zero new backend surface beyond FR-009/FR-011/FR-012 (Settings), FR-017/FR-019 (directory), FR-023 (guardian learner listing), and FR-016 (real-learner session, which is itself zero-new-backend) (FR-015); closed rosters never listed (FR-021); demo badge never shown during a real-learner session, and never hidden for the actual demo learner (FR-022); a real-learner session must be cleared on sign-out, not just on an explicit "exit" action (FR-022); a changed guardian password must invalidate prior session tokens, not just the stored hash (Edge Cases, Assumptions)

**Scale/Scope**: 6 restyled page-level components/routes + their shared sub-components, plus: 1 new guardian Settings page, 4 existing flow components (`dashboard-flow.tsx`, `practice-flow.tsx`, `mastery-flow.tsx`, `tutor-flow.tsx`) made real-learner-aware, 2 shared components (`Nav.tsx`, `DemoBadge.tsx`) extended, 1 instructor-side screen (`rosters-flow.tsx`) gaining one toggle plus an inline display-name prompt where that toggle needs it, ~7 new/changed backend routes, 1 new migration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Personalization Is a Model, Not a Guess** -- PASS. No mastery-model or sequencing logic touched anywhere in this feature. The real-learner session (FR-016) changes *which learner's data* a page fetches, never how that data is computed; the directory (FR-019) and Settings (FR-009-FR-012) touch no personalization logic at all.
- **II. Generated Content Graded Against a Rubric** -- N/A. No grading logic touched; the Assigned-quiz summary's before→after mastery (FR-007) is a read-only client-side aggregation of already-graded, already-rubric-scored results.
- **III. One Engine, Many Subjects** -- PASS. No subject-specific conditional introduced anywhere in this feature's six screens, the directory, or Settings.
- **IV. Agent Boundaries Reflect Real Responsibility** -- N/A. No agent code touched.
- **V. Every Decision Is Logged and Explainable** -- PASS (preserving). Real-learner Dashboard/Mastery (FR-016) surfaces the same already-logged mastery/sequencing explanations spec 025 built, just for a different learner_id. No new logging behavior introduced or removed by this feature.
- **VI. Agent Boundaries Match Deployment Boundaries** -- N/A. No A2A service touched.
- **VII. Spec Before Code, Milestone-Gated** -- PASS. This plan follows an approved `spec.md` with all clarifications resolved; `/speckit-tasks` and `/speckit-analyze` follow before implementation.
- **VIII. No Real Learner Data Until Privacy/Retention Specified** -- PASS. Privacy/retention was specified at spec 009/Milestone 7; this feature only extends *which already-authorized real learners* can reach already-existing real-data endpoints (their own guardian's own learners, via the existing `require_learner_ownership_if_real` gate) -- no new category of data is collected, and the demo-account flag/badge discipline (FR-022) is preserved, not loosened.
- **IX. Deployable and Demoable From the Start** -- PASS. All changes are within the existing Next.js/FastAPI/Vercel architecture; the new migration runs through the existing `alembic upgrade head` per-environment step (`tech-stack.md`'s Migrations row); no new Vercel configuration needed.
- **X. Staged Release Discipline** -- PASS. Branch `041-guardian-public-ui-redesign` was cut from `origin/staging`; will PR into `staging` first, same as every other feature.

No violations. Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/041-guardian-public-ui-redesign/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── api-changes.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── real_guardian_account.py     # + name, read_aloud_default, larger_text,
│   │   │                                 #   reduce_motion, theme, quiz_finished_email_enabled,
│   │   │                                 #   weekly_summary_enabled, password_changed_at
│   │   ├── real_instructor_account.py   # + display_name (nullable, set via PATCH only --
│   │   │                                 #   never collected at registration, FR-017)
│   │   ├── learner_profile.py           # + practice_reminders_enabled
│   │   └── classroom_roster.py          # + is_listed
│   ├── services/
│   │   ├── roster/enrollment.py          # + is_listed mutual-exclusion check (closed-roster
│   │   │                                  #   AND missing-display_name rejection) alongside
│   │   │                                  #   update_roster_enrollment_mode
│   │   └── auth/
│   │       ├── tokens.py                 # + SessionClaims.issued_at; verify_token passes
│   │       │                              #   the JWT's own `iat` through
│   │       └── dependencies.py           # + current_guardian rejects a token issued before
│   │                                      #   RealGuardianAccount.password_changed_at
│   └── api/routes/
│       ├── auth.py                       # + PATCH /api/auth/guardian/me,
│       │                                  #   POST /api/auth/guardian/change-password (also
│       │                                  #   sets password_changed_at),
│       │                                  #   PATCH /api/auth/instructor/me,
│       │                                  #   whoami extended with guardian preferences
│       ├── learners.py                   # + GET /api/learners/mine (FR-023)
│       └── rosters.py                    # + GET /api/rosters/directory,
│                                          #   UpdateRosterIn gains is_listed
└── alembic/versions/
    └── <new>_guardian_settings_and_roster_listing.py

frontend/
├── src/
│   ├── lib/
│   │   └── visitor-state.ts              # + real-learner-session (enter/exit/get), same
│   │                                      #   localStorage + notifySessionChanged pattern as
│   │                                      #   demo-learner-mode
│   ├── components/
│   │   ├── Nav.tsx                       # + "real-learner" bucket, REAL_LEARNER_LINKS,
│   │   │                                  #   identity display + exit action; handleSignOut
│   │   │                                  #   also clears the real-learner session (FR-022)
│   │   └── DemoBadge.tsx                 # + suppressed during a real-learner session
│   └── app/
│       ├── page.tsx                      # Home restyle + content additions
│       ├── sign-in/page.tsx              # restyled into single two-tab page
│       ├── demo/page.tsx                 # restyle only
│       ├── (auth)/guardian/
│       │   ├── learners/page.tsx         # restyle + stat tiles + "open dashboard" action
│       │   │                              #   + directory browse UI
│       │   └── settings/                 # NEW -- guardian Settings page
│       │       └── page.tsx
│       ├── instructor/rosters/
│       │   └── rosters-flow.tsx          # + "List in directory" toggle, plus an inline
│       │                                  #   "set your display name" prompt (shown only
│       │                                  #   when the toggle is used and display_name is
│       │                                  #   unset, FR-017)
│       ├── dashboard/dashboard-flow.tsx  # + real-learner-session-aware learner resolution
│       ├── practice/practice-flow.tsx    # + real-learner-session-aware learner resolution
│       ├── mastery/mastery-flow.tsx      # + real-learner-session-aware learner resolution
│       ├── tutor/tutor-flow.tsx          # + real-learner-session-aware learner resolution
│       └── quiz/ (LearnerAssignments.tsx,
│                  QuizSummary.tsx)       # mastery before→after aggregation (FR-007)
└── tests/                                # existing Vitest suite, extended for new behavior
```

**Structure Decision**: A web application change touching both `frontend/`
and `backend/`, unlike spec 027's frontend-only restyle. The restyle itself
(Home, Sign-in, Demo, Guardian · My learners' layout, Assigned-quiz) follows
027's exact token/Tailwind-class pattern. The four gap-closing additions
each follow an existing in-codebase precedent rather than introducing a new
pattern: Settings' account/password routes mirror `auth.py`'s existing
register/login shape; the real-learner session reuses `visitor-state.ts`'s
existing demo-learner-mode mechanism; the directory extends `rosters.py`'s
existing list/join pattern; `is_listed` mirrors `ClassroomRoster`'s existing
flat-boolean-column style. See `contracts/api-changes.md` for the full
route-level detail (this codebase uses no dedicated `contracts/` schema
format beyond that, same as spec 027's plan.md notes).

## Complexity Tracking

*No Constitution Check violations -- table not needed.*

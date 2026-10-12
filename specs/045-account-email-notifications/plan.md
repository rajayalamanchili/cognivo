# Implementation Plan: Account Email Notifications

**Branch**: `045-account-email-notifications` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/045-account-email-notifications/spec.md`

## Summary

Guardians and instructors who forget their password today have no
recovery path short of support intervention -- US1 adds a by-email
password-reset flow (request link -> follow link -> set new password ->
signed in). The same underlying "send a real guardian/instructor an
email" capability also powers two lower-priority notifications (US2:
registration confirmation, US3: deletion-request-accepted confirmation).
Technical approach: Resend as the outbound email provider (one `httpx`
REST call, research.md §1), two new tables (`password_reset_tokens`,
`notification_log_entries`), and a small `services/notifications/`
module that every trigger point calls into after its own existing
commit succeeds -- so a failed send never blocks the action that
triggered it (FR-012).

## Technical Context

**Language/Version**: Python 3.12 (backend, existing), TypeScript / Next.js (frontend, existing)

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic (all existing,
unchanged). `httpx` promoted from the `dev` dependency group to main
`dependencies` (research.md §1) -- no new package added to `uv.lock`.

**Storage**: PostgreSQL via Neon (existing) -- two new tables,
`password_reset_tokens` and `notification_log_entries` (data-model.md).

**Testing**: `pytest` (backend contract/integration/unit, existing
pattern -- `tests/integration/test_auth_*.py` siblings for the four new
auth endpoints, a `tests/integration/test_notifications_*.py` for the
registration/deletion-confirmation side effects and the demo-account
guard). `Vitest` only if the four new frontend pages warrant a
component test beyond what Playwright's existing smoke coverage implies
-- no new testing framework either way.

**Target Platform**: Vercel (existing) -- backend Python Function,
Next.js frontend, same `services` split as every prior feature.

**Project Type**: Web application (existing `backend/` + `frontend/`
split, Option 2 below).

**Performance Goals**: The new outbound Resend call adds at most ~10s
(its own explicit timeout, research.md §7) to three already sub-second
request paths (register, forgot-password, submit-deletion-request) --
well inside the backend's existing `maxDuration: 30`. No new
performance goal beyond "doesn't meaningfully regress these three
endpoints' existing latency."

**Constraints**: No new agent/A2A boundary (this is a third-party REST
call, not an agent capability -- Constitution Principle VI doesn't
apply). No in-memory state (Vercel statelessness, Principle IX) -- rate
limiting and token validity are both DB-backed, not process-local.
Demo accounts (Principle VIII) must never receive any of the three
email types -- enforced inside the shared `notify_*` functions
themselves (research.md §5), not left to each call site's own
discipline. The forgot-password response must carry no
account-enumeration signal (SC-003) -- identical response whether or
not the email matches a real, non-demo account.

**Scale/Scope**: Exactly three trigger points (password reset,
registration, deletion-request-accepted) -- no general-purpose
notification/template system (spec.md Assumptions, explicitly out of
scope).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization is a model | N/A -- no mastery/sequencing logic touched | PASS |
| II. Generated content graded against a rubric | N/A -- no generated assessment content | PASS |
| III. One engine, many subjects | N/A -- account-level infra, no subject-specific branching | PASS |
| IV. Agent boundaries reflect real responsibility | No new agent introduced -- `services/notifications/` is a plain service module, same shape as `services/deletion/` | PASS |
| V. Personalization/grading decisions logged and explainable | N/A for Langfuse tracing (no agent/LLM call added); FR-013's own notification-log requirement is this feature's equivalent audit obligation, satisfied by `NotificationLogEntry` | PASS |
| VI. Agent boundaries match deployment boundaries (A2A) | N/A -- Resend is a third-party REST API call, not an A2A agent boundary; no inbound-authentication requirement applies to an *outbound* call this project makes | PASS |
| VII. Spec before code | This `plan.md` follows an approved `spec.md`; `tasks.md` follows this plan | PASS |
| VIII. No real learner data until privacy/retention specified | Demo accounts (guardian, instructor, demo-learner-owning guardian) are hard-excluded from every notification type via `notify_*`'s required `is_demo` guard (research.md §5, FR-011) | PASS |
| IX. Deployable and demoable from the start | New Resend call is bounded (10s timeout) well under the existing `maxDuration: 30`; no persistent/background process introduced (the only async-feeling part, inactivity-sweep notifications, already runs inside the existing Vercel Cron job) | PASS |
| X. Staged release discipline | Lands via a feature branch PR into `staging` per normal workflow; no change to branch/CI model itself | PASS |

**Technology Constraints gate** (tech-stack.md): no email provider was
previously locked, so this feature *amends* tech-stack.md (new
"Transactional email" row + changelog entry, version 2.6.0 -> 2.7.0) at
`/speckit-plan` time rather than deviating from an existing locked
choice -- consistent with how every prior feature that needed a new
cross-feature technology decision (Tutor Agent's embedding model,
Misconception classifier's `scikit-learn` choice, etc.) handled it.

No violations. Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/045-account-email-notifications/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── api.md           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── password_reset_token.py        # NEW (data-model.md)
│   │   ├── notification_log_entry.py      # NEW (data-model.md)
│   │   └── enums.py                        # EDIT: + NotificationType, NotificationStatus
│   ├── services/
│   │   ├── auth/
│   │   │   └── reset_tokens.py             # NEW: issue/hash/verify/invalidate helpers
│   │   ├── notifications/
│   │   │   ├── mailer.py                   # NEW: Resend REST call (research.md §1/§5)
│   │   │   └── notify.py                   # NEW: notify_registration/notify_password_reset/notify_deletion_request
│   │   └── deletion/
│   │       └── inactivity.py               # EDIT: per-record notify call (research.md §5)
│   └── api/
│       └── routes/
│           ├── auth.py                     # EDIT: 4 new endpoints (contracts/api.md)
│           └── deletion.py                 # EDIT: notify call after commit
├── alembic/versions/
│   └── <rev>_password_reset_and_notification_log.py  # NEW migration
├── .env.example                            # EDIT: + RESEND_API_KEY, EMAIL_FROM_ADDRESS, FRONTEND_BASE_URL
├── pyproject.toml                          # EDIT: httpx -> main dependencies
└── tests/
    ├── integration/
    │   ├── test_auth_guardian_password_reset.py    # NEW
    │   ├── test_auth_instructor_password_reset.py  # NEW
    │   └── test_notifications.py                   # NEW: registration/deletion-confirmation/demo-guard
    └── unit/
        └── test_reset_tokens.py                    # NEW: hash/expiry/invalidation logic

frontend/
└── src/app/(auth)/
    ├── guardian/
    │   ├── sign-in/page.tsx                # EDIT: + "Forgot password?" link
    │   ├── forgot-password/page.tsx        # NEW
    │   └── reset-password/page.tsx         # NEW
    └── instructor/
        ├── sign-in/page.tsx                # EDIT: + "Forgot password?" link
        ├── forgot-password/page.tsx        # NEW
        └── reset-password/page.tsx         # NEW
```

**Structure Decision**: Option 2 (web application, `backend/` +
`frontend/`), the structure every prior feature in this repo already
uses -- this feature adds no new top-level project, only new
files/edits inside the existing two.

## Complexity Tracking

*No Constitution Check violations -- table intentionally left empty.*

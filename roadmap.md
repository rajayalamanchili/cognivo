# Roadmap

**Project**: Cognivo
**Governing rule**: per the constitution's Development Workflow section,
a milestone does not begin until the previous milestone's `spec.md`
Success Criteria are met.

**Cross-cutting from Milestone 1 onward**: per Constitution Principle X,
the `staging`/`main` branch model and the automated PR review gate
(`anthropics/claude-code-action@v1`, see `tech-stack.md`) are
repository-level infrastructure, not a milestone's feature scope -- they
must exist before Milestone 1's own work is considered done, and every
milestone from here forward is expected to use them, not just the ones
that happen to mention them explicitly.

---

## Milestone 1: Domain-Agnostic Core -- Content Schema, Structured Assessment, Mastery Model
**Spec**: `specs/001-domain-agnostic-core/spec.md`
**Status**: Complete (2026-08-16). All Definition of Done items below
are met and verified against a live Vercel deployment, not only local
development -- see `specs/001-domain-agnostic-core/tasks.md`'s Phase 6
notes for the verification record.

**Scope**: Subject-agnostic content-artifact schema; Diagnostic Agent
(placement) and Sequencing Agent (explicit, deterministic mastery model
+ next-topic selection) as local ADK sub-agents; Assessment-Generation
Agent producing structured (multiple-choice/numeric) questions with
validated answer keys; deterministic grading of structured answers; a
second subject's content artifact proving the engine is genuinely
subject-agnostic from day one; Langfuse tracing on every agent
invocation; one or more clearly-flagged demo learner profiles so the
live deployment has something to show a visitor; a live Vercel
deployment of the whole flow, per Constitution Principles V, VIII, and
IX.

**Definition of done**:
- All acceptance scenarios in `spec.md` pass.
- SC-001 (mastery determinism), SC-003 (question validation), and SC-004
  (extensibility, zero engine-file changes for a second subject) are all
  hard gates with automated checks, not verified by inspection -- built
  from the start rather than promised now and added later.
- SC-005 (degenerate answer pattern doesn't fake mastery) has a specific
  test, not just a plausible-sounding claim.
- The full placement-through-first-question flow works end to end on the
  live Vercel deployment, not only in local development -- verified by
  the deployment smoke test defined in `tech-stack.md`.
- The `staging`/`main` branch structure and the automated PR review gate
  (Constitution Principle X) are in place and enforced by branch
  protection before this milestone's own work is merged -- this is
  infrastructure the whole project depends on, not a nice-to-have added
  after the fact.
- At least one demo learner profile is seeded, marked with the explicit
  `is_demo` flag and the persistent UI badge defined in `tech-stack.md`,
  and is what the live Vercel deployment shows a first-time visitor --
  not an empty state.

**Explicitly not included**: free-text grading, the Grading Agent, any
A2A remote service, instructor/classroom features, real learner data,
the Tutor Agent, dashboards, quizzes.

---

## Milestone 2: Recommendation Agent -- Weak-Area Flagging and Next Steps
**Spec**: `specs/002-recommendation-agent/spec.md`
**Status**: Implemented and merged (PR #10) -- 26/27 tasks complete;
the sole remaining item (`tasks.md` T027, live-deployment quickstart
validation) is explicitly deferred to a maintainer running it against a
real Vercel URL, not a code gap. (This status line, and `spec.md`'s own
header, were left stale after merge -- corrected here alongside the
Milestone 3 promotion that surfaced the discrepancy.)

**Scope**: A Recommendation Agent that analyzes a learner's mastery
state and assessment-event history to flag weak areas (each with cited
evidence, never a bare claim) and suggest concrete, prerequisite-aware
next steps -- the direct implementation of the original product
requirement to "analyze performance data to flag weak areas and suggest
next steps." Deliberately proven as a distinct responsibility from the
Sequencing Agent, with its own independent test suite, per Constitution
Principle IV.

**Why this comes before free-text grading**: This agent only needs
Milestone 1's mastery-state and assessment-event data model to exist --
it doesn't depend on free-text grading, A2A, or classroom features. It's
also a more central piece of the original product's value proposition
than grading nuance, so it's sequenced earlier.

**Definition of done**:
- All acceptance scenarios in `specs/002-recommendation-agent/spec.md`
  pass.
- SC-002 (every weak-area flag cites real evidence) and SC-005 (this
  agent's test suite is independent of Sequencing's) are hard gates --
  the first because an unsupported "weak area" claim is exactly the kind
  of ungrounded AI output this project's constitution exists to prevent,
  the second because it's the concrete proof that this agent's boundary
  is real, not decorative.
- Milestone 1's full acceptance-scenario suite still passes (regression
  check).

**Explicitly not included**: instructor/classroom aggregation across a
roster (Milestone 7 consumes this agent's output rather than
duplicating its logic); external-resource recommendation.

---

## Milestone 3: Real Personalization Signal -- Does Sequencing Actually Help?
**Spec**: `specs/006-personalization-eval/spec.md`
**Status**: Implemented (harness + report page); real population-scale
validation of the DoD's core claim (below) still outstanding -- see PR
#11 and that spec's `tasks.md` T031/T032.

**Sequencing note**: M3's original PR review flagged an apparent
sequencing violation ("do not begin until Milestone 2 DoD is met"),
based on this file's Milestone 2 entry, which at the time still read
"Spec drafted, pending `/speckit-clarify` and `/speckit-plan`." That
status line was stale, not current: Milestone 2 (PR #10) had already
been fully implemented and merged into `staging` before Milestone 3's
branch was created -- `spec.md`'s own status header just hadn't been
updated after that merge either (both corrected 2026-08-18, during the
`staging` -> `main` promotion that surfaced the discrepancy). So there
was no actual sequencing violation; the concern was an artifact of two
stale status lines, not a real out-of-order implementation. Left here
as a reminder to update a milestone's roadmap/spec status line in the
same PR that completes it, not after.

**Scope**: An evaluation harness that simulates synthetic learner
populations (with known, simulated true mastery) and measures whether
the Sequencing Agent's chosen order reaches target mastery faster than a
random or fixed-order baseline. This is the milestone that makes
"personalizes based on what you know" a measured claim instead of an
assumed one.

**Definition of done**:
- The simulated-learner evaluation harness shows the Sequencing Agent's
  ordering reaching target mastery in fewer questions than a random
  baseline, across multiple synthetic learner profiles (not cherry-picked
  ones), at `specs/006-personalization-eval/research.md` §10's full
  population scale (30 learners x 4 profiles x 2 subjects) -- **not yet
  demonstrated**; only small-scale (n=1-3) live spot checks and scripted
  unit fixtures exist so far (`tasks.md` T031/T032).
- Milestones 1 and 2's full acceptance-scenario suites still pass
  (regression check) -- both were already merged before Milestone 3
  began (see Sequencing note above).

---

## Milestone 4: Learner Dashboard
**Spec**: `specs/004-learner-dashboard/spec.md`
**Status**: Complete (2026-08-18). All 31 tasks across 4 user stories
implemented and merged to `staging` (PR #14), then promoted to `main`
(PR #15). `specs/004-learner-dashboard/tasks.md`'s Phase 7 records
`quickstart.md`'s 10 validation scenarios run end to end against a
freshly migrated and seeded dev database, not only local development.

**Scope**: A learner-facing dashboard surfacing per-topic mastery, the
Recommendation Agent's freshly-generated weak-area report and next-step
suggestions, and an illustrative (explicitly not-a-fixed-plan) path
visualization showing topics completed, current focus, and likely
upcoming topics.

**Why this comes after the personalization-eval milestone**: Surfacing
a "personalized path" to a learner is more honest to ship once
Milestone 3 has actually measured that the personalization works, not
before.

**Definition of done**:
- All acceptance scenarios in `specs/004-learner-dashboard/spec.md`
  pass.
- SC-003 (weak-area section matches a direct Recommendation Agent call)
  and SC-004 (100% of "upcoming topics" sections carry the
  illustrative/subject-to-change disclosure) are hard gates -- the first
  because a dashboard silently drifting from the agent it's supposed to
  reflect is worse than no dashboard, the second because presenting an
  adaptive system's one-decision-at-a-time reality as a fixed plan would
  misrepresent how the product actually works.
- Milestones 1-3's full suites still pass.

---

## Milestone 5: Adaptive Difficulty Quiz
**Spec**: `specs/005-adaptive-quiz/spec.md`
**Status**: `/speckit-implement` complete (35/35 tasks). All 10
`quickstart.md` validation scenarios (T035) verified against the live
dev DB with real Claude generation calls, 40/40 quiz tests plus the
full 177-test backend suite passing with no regressions (2026-08-18).

**Scope**: A bounded, named quiz session (learner-chosen topic(s) and
question count) where difficulty adapts within the session based on
in-quiz performance, reaching a defined completion state with a score --
and feeding every answered question back into the learner's persistent
mastery state via the exact same mechanism as a regular question, so a
quiz is never a disconnected side activity.

**Why this is sequenced here**: Only depends on Milestone 1
(Assessment-Generation Agent, difficulty bands) -- placed alongside the
Learner Dashboard to complete a full, compelling solo-learner experience
before the platform's scope broadens into grading depth (Milestone 6)
and multi-tenancy (Milestone 7).

**Definition of done** (draft, to be formalized in its own `spec.md`):
- All acceptance scenarios in `specs/005-adaptive-quiz/spec.md` pass.
- SC-001 (deterministic difficulty progression and score) and SC-002
  (100% of in-quiz questions verified to also update persistent mastery
  state) are hard gates -- the first is Constitution Principle I applied
  to a new session type, not an exception to it; the second is what
  keeps a quiz from becoming a second, inconsistent source of truth
  about what a learner knows.
- Milestones 1-4's full suites still pass.

**Explicitly not included**: instructor-configured or instructor-
assigned quizzes (built in Milestone 8, once Milestone 7's roster/auth
exists).

---

## Milestone 6: Free-Text Grading via a Real A2A Service
**Spec**: `specs/007-grading-agent/spec.md`
**Status**: `/speckit-implement` complete, all 6 phases (2026-08-22)
(setup; foundational schema/content/agent-skeleton; User Story 1 --
free-text questions are generated, guarded, graded via a real A2A call
to the Grading Agent, and update mastery state, including inside a quiz
session; User Story 2 -- learners see which rubric criteria their answer
met/missed; User Story 3's infrastructure -- the grading-agent/backend
test-independence check and the ground-truth eval gate are both written
and wired into a new CI workflow; Phase 6 Polish -- regression suites,
`check_no_subject_conditionals.py`, live deployment, and live
validation). `grading-agent/`'s Vercel deployment (T044) is done for
both `staging` and `main` (external action, performed by the user
2026-08-21). SC-005's live demonstration (T045) is done (2026-08-22) --
reaching a live grading response required three sequential fixes only
discoverable once real cross-service traffic was attempted for the
first time (Vercel Deployment Protection bypass, PR #22; the content
loader's Topic-row FK violation on reload, PR #23; `to_a2a()`'s
AgentCard advertising `localhost:8000` instead of the real Vercel URL,
PR #24). `quickstart.md`'s 13 validation scenarios (T046) all ran
against staging (2026-08-22) -- see `tasks.md`'s T045/T046 for full
detail on both.

**Scope**: The Grading Agent, built as an independently deployable A2A
service per Constitution Principle VI's justification (independent
rubric versioning and evaluation without redeploying the rest of the
system). Free-text answers are graded against the same
generated-alongside-the-question rubric pattern established in
Milestone 1 for structured answers (Constitution Principle II), not
freeform LLM judgment.

**Definition of done** (draft):
- Grading accuracy/consistency is measured against a hand-labeled
  ground-truth set of (question, learner answer, expected grade) triples
  -- eval results are a merge gate, not a nice-to-have.
- The Grading Agent's A2A boundary is demonstrated to actually deliver
  its stated justification: a rubric change can be deployed to Grading
  alone, verified not to require touching any other agent's deployment.
- Milestones 1-5's full suites still pass.

**Explicitly not included**: instructor/classroom features, the Tutor
Agent's full A2A delegation (Milestone 9).

---

## Milestone 7: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review, Real Learner Data Gate
**Spec**: `specs/009-privacy-retention/spec.md` covers this milestone's
privacy/retention prerequisite (Constitution Principle VIII, approved
and merged); `specs/010-instructor-classroom/spec.md` is the
auth/rosters/dashboard/content-review spec proper, gated on 009.
**Status**: `/speckit-implement` complete, all 8 phases (2026-08-23).
The privacy/retention gate (`009-privacy-retention`, 2026-08-22) --
`check_no_real_account_path.py` CI-enforced, a written data
classification, and the forward-looking account/roster data model --
was the approved prerequisite `010-instructor-classroom` built against.
Phase-by-phase: Setup + Foundational (migration creating 8 new tables
plus the `demo_learner_profiles` -> `learner_profiles` rename, all 8
new models, Argon2id/JWT auth utilities); User Story 1 (guardian/
instructor register-login-logout, guardian add-a-learner); User Story 2
(roster creation, open/closed enrollment, guardian join-by-code,
instructor approve/decline, unenrollment from either side); User
Story 3 (the instructor dashboard, aggregating Milestone 2's
Recommendation Agent output per learner, verified byte-for-byte
identical to that agent's own endpoint -- no new weak-area logic);
User Story 4 (content-review queue, scoped via an `Enrollment` join at
query time rather than a denormalized snapshot, reactivate/reject
resolution with its own audited event type); User Story 5 (seeded demo
instructor, extended during `/speckit-implement` `/speckit-clarify`
past its original identity-only contract to a fully navigable session --
see Corrections below); Polish (regression + gate re-checks, demo-data
reset wired to Vercel Cron, E2E spec written).

**Corrections made during implementation** (each documented in
`specs/010-instructor-classroom/data-model.md`/`contracts/api.md` with
full reasoning): a closed roster's `join_code` needed generating (not
staying null) since `POST /api/rosters/join` has no other field to
target a roster by; `GET /api/rosters/{roster_id}/enrollments` was
added (not in the original contract) since nothing else listed a
roster's enrolled learners for the management page; the demo
instructor's session was extended from identity-only to fully
navigable, which required relaxing `classroom_rosters.instructor_id`
from a hard FK to `real_instructor_accounts` down to an
application-enforced value (migration `7e686faa5e6d`) -- same
"could point at more than one table" shape `RetentionRecord.account_id`/
`DeletionRequest.target_id` already had.

**Known gaps, found during Polish** (none blocking, none silently
worked around; status as of the gaps themselves, updated below with
what later closed them):
- `DemoBadge` (`frontend/src/components/DemoBadge.tsx`) originally
  rendered unconditionally in the root layout -- accurate for the
  demo-learner-exclusive pages (`/practice`, `/mastery`, `/quiz`,
  `/dashboard`, `/placement`), but also showed "DEMO ACCOUNT" on the
  real guardian/instructor pages this spec added, regardless of
  whether the signed-in session was real or demo. **Resolved
  2026-08-23** on the Milestone 8 branch, before that branch's PR
  (`f096eac`, `9f52d32`): `GET /api/auth/whoami` now exists as the
  session-introspection endpoint this gap was waiting on, `DemoBadge`
  is conditional on session/route (demo-instructor session or
  demo-territory page only), and real guardian/instructor sessions get
  an identity readout in `Nav.tsx` instead of the badge.
- T057 (Playwright E2E, `frontend/tests/e2e/instructor-classroom-round-
  trip.spec.ts`) was written and verified to parse/list correctly, but
  never executed against a live deployment -- this sandbox has neither
  `PLAYWRIGHT_BASE_URL` nor a reachable Postgres. Its module comment
  also documented a real scope boundary: "flag and resolve a question"
  wasn't achievable at all yet, live deployment or not, since every
  question-generating endpoint resolved the seeded demo learner
  internally rather than accepting an arbitrary `learner_id`, so a
  guardian-created real learner had no path to ever generate a
  question. **Partially resolved**: Milestone 8's guardian-mediated
  assigned-quiz attempt flow (a guardian can start/complete a quiz on a
  targeted real learner's behalf) closes the "no path to generate a
  question" half. The spec itself still has not been executed against
  a live deployment -- only updated for the Nav overhaul's selector
  changes (`f096eac`) -- so this gap is not fully closed.
- T056's regression check ran clean for everything this sandbox could
  execute (118 passed, 0 failed, every DB-dependent test skipping for
  lack of a reachable `DATABASE_URL`), but that wasn't the same as
  having actually run the full suite against a real database.
  **Resolved 2026-08-23**: Milestone 8's DoD validation ran the full
  backend suite, Milestones 1-8 included, against a real, freshly
  migrated dev database (287/288 passing; see Milestone 8's status
  above for the one pre-existing, unrelated failure).

**Scope**: Instructor-facing classroom features -- roster management;
an instructor dashboard aggregating the Recommendation Agent's
per-learner weak-area output across a class (built by aggregating
Milestone 2's agent output per learner, not by re-implementing weak-area
detection); a content-authoring and review workflow giving an
instructor ownership of the flagged-question mechanism already
established in Milestone 1 (FR-011), which currently has no defined
owner; seeded demo accounts (one instructor, at least one student),
explicitly flagged and visibly distinguishable from real accounts per
Constitution Principle VIII, reachable via a dedicated demo entry point
separate from real sign-up -- and, as a hard prerequisite per
Constitution Principle VIII, the dedicated privacy/retention spec that
must exist and be approved before any real (non-synthetic) learner data
is permitted anywhere in the system.

**Why this comes late, deliberately**: This axis is the one most
orthogonal to the AI-engineering substance of the project (auth,
multi-tenancy, roster CRUD are standard SaaS-building work, not
AI-specific) and the one most likely to balloon into generic
product-building if front-loaded. Deliberately kept to auth, rosters,
dashboard, content review, and the privacy gate only -- instructor-
assigned quizzes are pulled out into their own Milestone 8 specifically
so this milestone doesn't absorb yet another axis on top of the five it
already carries.

**Definition of done** (draft):
- The privacy/retention spec is approved before this milestone's other
  work begins -- not written in parallel with feature work, and not
  retrofitted after real data is already flowing.
- The instructor dashboard is verified to aggregate, not duplicate,
  Milestone 2's Recommendation Agent logic -- no separate weak-area
  detection code path.
- Seeded demo instructor and student accounts exist, carry the explicit
  `is_demo` flag and persistent UI badge, are reachable only via the
  dedicated demo entry point (never indistinguishable from a real
  sign-up), and reset to a known-good state on the schedule defined in
  `tech-stack.md` -- verified by an automated check that no account
  reachable via the real sign-up flow can ever have `is_demo` set to
  true.
- Milestones 1-6's full suites still pass.

---

## Milestone 8: Instructor-Assigned Quizzes
**Spec**: `specs/011-instructor-assigned-quizzes/spec.md`
**Status**: `/speckit-specify` complete (2026-08-23). Milestone 7's DoD
is met (see that milestone's entry above), so this milestone's spec was
written against it. Two clarifications were resolved during
`/speckit-specify` itself, both surfaced by inspecting the actual
Milestone 7 auth code rather than assumed: no real-learner-facing login
exists yet (only guardian and instructor sessions), so a targeted
learner's assigned-quiz attempt is guardian-mediated, not a new
learner-login surface; and attempts are capped at one per learner per
assignment, hard-blocked from starting after the due date (an
in-progress attempt may still finish). Requirements-quality checklist
passed with no outstanding items. `/speckit-plan` complete (2026-08-23):
two new tables (`quiz_assignments`, `quiz_assignment_targets`) as a
pure join layer on top of Milestone 5/6's entirely-unmodified quiz/
grading mechanism; the two existing quiz-continuation routes gain a
conditional guardian-ownership check that only applies to
assignment-linked sessions, leaving the non-assignment quiz path
behaviorally untouched. Constitution Check passed with no violations.
`/speckit-tasks` complete (2026-08-23): 37 tasks across Setup,
Foundational, and three user-story phases. `/speckit-implement`
complete (2026-08-23), all 37 tasks (T001-T037) -- an instructor can
create, list, and cancel a quiz assignment against a chosen subset (or
all) of a roster; a targeted learner's own guardian can start and
complete that attempt end to end with grading/mastery-update/
difficulty-adaptation behavior verified identical to a non-assigned
quiz (SC-002); and the instructor sees each targeted learner's
individual status/score in a per-assignment report, not a class-wide
aggregate (SC-003). Milestone DoD confirmed against a real, freshly
migrated dev database (all 12 Alembic migrations applied cleanly from
base, including this milestone's two): the full backend suite passes
(287/288, the sole failure a pre-existing, unrelated Milestone-1 test
confirmed flaky under Neon/PgBouncer connection-pooled type-OID churn,
not a regression -- passes in isolation), `check_no_subject_
conditionals.py` clean, and a Playwright E2E spec
(`instructor-assigned-quiz-round-trip.spec.ts`) covers the full
assign -> guardian-completes -> instructor-views-result round trip.
Also fixed, while validating against the real database, three
test-authoring bugs that a DB-less sandbox run had never been able to
exercise: two files re-registering an already-registered instructor
email instead of logging back in, and a `patch_generation` stems list
reused across two separate mocked-generation calls that falsely
triggered dedup-exhaustion.

**Also on this branch, after M8's own DoD was confirmed** (not part of
M8's scope proper, but shipped in the same PR): a session-aware nav
overhaul -- `GET /api/auth/whoami`, and `Nav.tsx` replacing the old
flat, always-visible link list with anonymous/demo-learner/guardian/
instructor buckets -- together with a conditional `DemoBadge`, closing
Milestone 7's "DemoBadge always renders" known gap (see that
milestone's entry above); and a kid-friendly design-token theme system
(semantic light/dark color tokens, Baloo 2 + Nunito type, softened
corners) applied across the 28 components/pages that had hardcoded
colors. Neither touches grading, mastery, or the quiz-assignment
mechanism itself. Merged to `staging` via PR #30 (2026-08-23).

**Scope**: Extends the Adaptive Difficulty Quiz (Milestone 5) so an
instructor can configure and assign a specific quiz (topic(s), question
count, optionally a due date) to some or all of their roster, rather
than only the learner-initiated quizzes Milestone 5 covers. Assigned-quiz
results appear broken out per student in the instructor dashboard
established in Milestone 7.

**Why this is its own milestone, not folded into Milestone 5 or 7**:
It strictly depends on both Milestone 5 (the quiz mechanism itself) and
Milestone 7 (roster/auth) existing -- it cannot be built before either.
Giving it a separate milestone, rather than adding it to Milestone 7's
already-substantial scope, keeps that milestone from absorbing a sixth
axis on top of auth, rosters, dashboard, content review, demo accounts,
and the privacy gate it already carries.

**Definition of done** (draft, to be formalized in its own `spec.md`):
- An instructor can assign a quiz (topic(s), question count) to a chosen
  subset of their roster, and assigned-quiz results appear per student
  in the instructor dashboard, not only as an aggregate number.
- Assigned-quiz grading and mastery-update behavior are verified
  unchanged from Milestone 5 and Milestone 6's existing mechanisms --
  this milestone introduces no new grading logic, only assignment and
  reporting.
- Milestones 1-7's full suites still pass.

**Explicitly not included**: quiz templates or reuse across terms/
semesters (a plausible future idea, not required to prove
instructor-assigned quizzes work at all).

---

## Milestone 9: Tutor Agent -- Full A2A Delegation, Vector-Grounded Retrieval, and Streaming Responses
**Spec**: `specs/012-tutor-agent/spec.md`
**Status**: `/speckit-specify` complete (2026-08-23), branched
`012-tutor-agent` from `origin/staging` (Milestone 8's DoD is met, so
this milestone's spec was written against it). Three clarifications
resolved interactively during `/speckit-specify` itself: (1) "Full A2A
Delegation" means the Tutor Agent alone becomes a new standalone A2A
service, mirroring the Grading Agent's pattern -- Sequencing and
Recommendation stay local ADK sub-agents, reached through the
backend's existing APIs, since neither has an independent-versioning/
evaluation need justifying an A2A split (Constitution Principle IV/VI);
(2) Tutor Agent access is guardian-mediated for a real learner plus the
seeded demo learner, matching Milestone 8's precedent -- no new
real-learner login surface; (3) the retrieval-grounding success
threshold is 90% of a defined test-question set. Requirements-quality
checklist passed clean. `/speckit-plan` complete (2026-08-23): the
`backend` is the sole orchestrator of a tutoring turn (runs `pgvector`
retrieval, gathers Sequencing/Recommendation context in-process, calls
Grading only via the already-existing backend-to-Grading-Agent path
when needed) and calls a new standalone `tutor-agent/` A2A service --
built identically to `grading-agent/`, including its shared-secret
auth and Vercel host/port derivation -- that streams back a grounded
answer from exactly the context it's given, holding no database
credentials or state of its own; this avoids a new reverse-
authentication path (Tutor Agent calling back into the backend) that
the codebase doesn't otherwise need. `tech-stack.md` amended with six
new locked rows: embedding model (Voyage `voyage-3` via LiteLLM),
passage granularity (one embedded passage per content-artifact field,
no chunking algorithm), the orchestration split above, the A2A
streaming transport (`a2a-sdk`'s native `message/stream`), and a 60s
`maxDuration` (vs. Grading Agent's 30s). Constitution Check passed with
no violations. `/speckit-clarify` then run against `spec.md` (2026-08-23,
after this plan pass -- four more clarifications the plan's own
research/data-model work had surfaced but hadn't yet been written back
into the spec): SC-001's latency target formalized at 3s p95; three new
requirements added -- FR-013 (per-learner rate limit on the Tutor
Agent endpoint, reusing the Grading Agent's existing DB-query-based
window), FR-014 (at most one active Tutoring Session per learner per
subject, get-or-create), FR-015 (a new question is rejected, not
interleaved or queued, while the previous one is still streaming).
`research.md`/`data-model.md`/`contracts/api.md` then refreshed to
match (a new research.md §8, a partial-unique-index constraint, a new
`409`/`429` response pair). `/speckit-tasks` complete (2026-08-23):
36 tasks across Setup, Foundational, and three user-story phases.
`/speckit-analyze` then run (2026-08-23) and found 5 issues -- 1
CRITICAL, 2 HIGH, 2 MEDIUM -- all fixed the same day, revising the
task count to 38: **C1** (CRITICAL, Constitution Principle VIII) --
the two new real-learner-linked tables weren't yet reflected in
`specs/009-privacy-retention/data-classification.md`, which is a
living document FR-002 requires stay current; fixed directly in that
document, which in turn surfaced a bigger, pre-existing gap (not
introduced by this milestone) now tracked in this file's own new
"Known gap" section above: Milestone 7's FR-004/FR-005 deletion-
execution pathway was deferred at spec-writing time and never actually
implemented, only its `DeletionRequest` model. **H1** (SC-002 had no
test-question fixture to measure its 90% grounding threshold against)
-- added T036. **H2** (FR-015's original `answer_text IS NULL`
in-flight marker had no way to distinguish "still streaming" from "died
mid-stream," which would have permanently blocked a session after any
interrupted stream) -- added `tutor_exchanges.failed_at`, splitting the
original single orchestration task into T021/T022. **M1** (spec.md's
"Delegation Call" entity wanted per-call inputs/outputs, but
`delegation_context` was designed as a single merged summary) --
restructured to an array of `{agent, request, response}` records.
**M2** (the pre-split orchestration task bundled 7 requirements into
one unit) -- resolved by the same H2 split. Foundational (T004-T015)
covers the data layer (3 new tables + `pgvector` extension + new
`AssessmentEventType` value), the content-artifact loader's
embedding-generation extension, and the standalone `tutor-agent/` A2A
service itself (agent, guardrails, tracing) plus the backend's client
for it -- all three user stories depend on this. User Story 1
(T016-T027, the MVP) builds the full open-session -> ask ->
grounded-streamed-answer loop, including FR-013/014/015's rate-limit/
session-uniqueness/in-flight guardrails and the H2 failure-recovery
path (deliberately scoped as US1 tasks, not Foundational, since
they're behavior of the two endpoints US1 itself builds). User Story 2
(T028-T030) adds real mastery/weak-area context to the same
orchestration. User Story 3 (T031-T032) adds the inspection endpoint.
Polish (T033-T038) covers the E2E round trip, full-suite regression
against a real database, the subject-conditional gate, the H1 fixture,
and live verification of SC-001/002/004. `/speckit-implement` run
phase-by-phase starting 2026-08-24: Setup (T001-T003) and Foundational
(T004-T015) both complete -- the latter's migration and `pgvector`
retrieval verified end-to-end against a real, freshly-migrated dev
database (`de54cd54219e`), not just unit-tested. User Story 1
(T016-T027, the MVP) also complete: the full open-session ->
ask -> grounded-streamed-answer loop, FR-013/014/015's guardrails, and
the H2 failure-recovery path all pass their integration tests against
that same real database (15 new tests), plus the frontend chat page/
component (11 new Vitest tests, ESLint/Prettier/`next build` clean).
Full backend regression re-confirmed at 308/308 passing after this
phase (293 prior + 15 new -- SC-005 holds). User Story 2 (T028-T030)
complete: a deterministic keyword check (not an LLM guess, Constitution
Principle I) routes performance-dependent questions to a real in-process
Recommendation Agent call, and `tutor-agent/`'s instruction was
strengthened to use that data verbatim, including the honest
insufficient-data case -- 3 new tests. User Story 3 (T031-T032)
complete: `GET /api/tutor/exchanges/{id}` with guardian/enrolled-
instructor/demo-instructor auth mirroring `content_review`'s pattern
-- 8 new tests. Polish: T034-T036 complete -- the full backend suite
re-confirmed at **321/321** passing against a freshly-migrated real
database (SC-005 holds through every phase), the subject-conditional
gate passes, and a 30-question grounding fixture is checked in at
`specs/012-tutor-agent/eval/grounding-test-questions.md` (closing
`/speckit-analyze` finding H1). T033's Playwright spec is written
(lint/format/`tsc --noEmit` clean) but not yet run live -- writing it
surfaced a real gap (nothing exposed an exchange's id to any client at
all, making User Story 3's own endpoint undiscoverable), fixed by
adding `exchange_id` to the SSE stream's final `done` event and a
`data-exchange-id` DOM attribute on `TutorChat.tsx`. **Known gap**:
T033/T037/T038 all require a live stack (backend + `tutor-agent/` +
migrated DB + real `ANTHROPIC_API_KEY`/`VOYAGE_API_KEY`, or an actual
Vercel deployment) this environment doesn't have -- not attempted
without checking first, since running them spends real API credits.

**T037 live verification (2026-08-26, `014-tutor-agent-live-verification`
branch)**: a Vercel Production deployment now existed, so T037/T038/T033
were attempted for real. Getting there required a chain of environment
fixes outside this repo's own files (all applied by the user, not
tracked here per this project's no-deployment-posture-in-repo
convention): the migration had never been run against the production
database, several env vars (`TUTOR_AGENT_SHARED_SECRET`,
`TUTOR_AGENT_URL`, the Vercel deployment-protection bypass secret) were
unset or stale, and `content_passage_embeddings` had never been
populated in production. Once unblocked, live testing surfaced and
fixed two real bugs neither the test suite nor `/speckit-analyze` had
caught:
- **A second finding-H2 gap** (`backend/src/services/tutor/session.py`'s
  `prepare_message`): the `anext(stream)` call opening the Tutor
  Agent's A2A stream only caught `TutorUnavailableError`, not an
  arbitrary exception -- confirmed live (a misconfigured deployment
  raised something else while opening the stream), which left two of
  the demo learner's exchanges permanently `answer_text IS NULL AND
  failed_at IS NULL`, blocking their sessions. Fixed by broadening the
  `except` to match `stream_message_response`'s own breadth
  (`CancelledError`, `GeneratorExit`, `Exception`); regression test
  added.
- **SC-004 (incremental streaming) was silently never working**:
  `tutor-agent/src/agent.py`'s `to_a2a()` call left `RunConfig` at
  google-adk's own default (`streaming_mode=StreamingMode.NONE`), so
  the Claude call itself was never asked to stream -- fixed via the one
  hook ADK exposes (`agent_executor_factory` ->
  `A2aAgentExecutorConfig.request_converter`, forcing `StreamingMode
  .SSE`). That alone wasn't sufficient: `AgentCardBuilder`'s own
  default `AgentCapabilities()` also has `streaming=False`, and
  `to_a2a()` never overrides it without an explicit `agent_card` -- so
  the served agent card advertised "doesn't support streaming," and
  the `a2a-sdk` client correctly (per A2A protocol) fell back to the
  blocking `message/send` RPC instead of `message/stream`, no matter
  how genuinely incremental the server-side generation was. Root-caused
  by temporarily instrumenting the A2A executor's one official
  `ExecuteInterceptor.after_event` hook and reading Vercel's runtime
  logs, which proved ADK really was producing multiple partial events
  server-side (11 events over ~6s) despite the client still seeing one
  buffered response -- narrowing the gap to agent-card capability
  negotiation, not event generation. Fixed by building the card
  ourselves via the same `AgentCardBuilder` `to_a2a()` uses internally,
  with `streaming=True`, passed back in via `agent_card`. Confirmed live
  against the fix's preview deployment: a real question now arrives as
  13 incremental `delta` events over ~14s (previously always exactly 1
  buffered event) -- **SC-004 now holds**.

Both fixes merged to `staging` (PR #36) then promoted to `main` (PR
#37) the same day, closing two more `/speckit-analyze`-style review
rounds along the way (`_streaming_request_converter` now uses
`run_config.model_copy(update=...)` instead of rebuilding `RunConfig`
from scratch, so a future `google-adk` version populating any field
besides `custom_metadata` in its default conversion won't be silently
dropped; `prepare_message`'s broadened `except` now reuses
`_persist_failed_exchange` instead of an inlined copy, so a future DB
operation added before the `anext()` call stays protected the same way
`stream_message_response`'s own call sites already are; a regression
test now asserts `_agent_card.capabilities.streaming is True`, the more
load-bearing of the two SC-004 fixes, which previously had no test
coverage of its own).

**T037 (SC-001/SC-004), run against production post-merge, full
30-question fixture**: p95 first-token latency **4.82s** (n=30, max
6.66s, min 3.22s) -- **SC-001 (3s target) does not hold**, a real
latency finding for this pipeline (guardrails + retrieval + A2A +
Claude), not addressed in this pass. **SC-004 holds cleanly: 30/30
responses arrived as multiple incremental chunks** (previously always
exactly 1 buffered chunk before this session's fixes). Also notable:
every transient `500`/`429` encountered during this real 30-question
run recovered cleanly via retry with zero orphaned exchanges -- the H2
stream-open fix held under repeated real-world failures, not just the
one scripted test case that originally found it.

**T038 (SC-002 grounding rate), same 30-question run**: **0/30
grounded** -- every exchange's `grounded` is `false` and
`retrieved_passage_ids` is empty, confirmed via a direct DB read (the
demo learner's exchanges have no owning guardian or enrolled
instructor, so `GET /api/tutor/exchanges/{id}` itself isn't reachable
for them -- a separate, minor demo-data gap, not investigated further
here). This is **not** the empty-embeddings-table failure mode
`grounding-test-questions.md` warns about -- a direct count confirmed
`content_passage_embeddings` holds 32 rows each for `biology` and
`algebra-1` (matching research.md §5's 4-passages-per-topic design).
The Tutor Agent's own answer text corroborates this isn't a marker-
parsing bug either: asked about photosynthesis (a real, embedded
`biology` topic), it said outright "I don't have material on
photosynthesis in this course's content yet" -- consistent with
`search_passages()` (`backend/src/services/retrieval/passage_search.py`)
or the query-embedding call within it returning zero results despite
the table being populated, not with passages being offered but never
cited. **Known gap, not investigated further this session**: root
cause is somewhere in the retrieval path itself (a genuinely separate
code path from both bugs fixed above, untouched by PRs #36/#37) --
candidates include a query-embedding-model mismatch against what the
loader used, or a silent failure inside `search_passages()`. Needs
dedicated follow-up before SC-002 can be re-measured.

**T033 (Playwright E2E)**: still not run against a live deployment --
out of scope for this already-long live-verification pass; left for a
dedicated follow-up alongside T038's grounding investigation.

**T038 follow-up (2026-08-26, `015-tutor-agent-verification-status`
branch): the T038 investigation itself was blocked before it could
finish, and the blocker -- not SC-002 -- is what got fixed this
session.** Traced one exchange from the 30-question run by matching
question text + rough timestamp between the DB and a Langfuse trace:
that trace showed retrieval working correctly (5 relevant passages,
4 of them exactly the `photosynthesis` topic the question asked about)
and the model's raw output citing 2 of them in a well-formed grounding
footer -- directly contradicting the DB row it was matched against,
which had `grounded=false`/`retrieved_passage_ids=[]`. Confirmed via a
direct audit-log cross-check (`assessment_events.payload` for that
exact `exchange_id`, written in the same transaction as `tutor_exchanges`)
that the empty result really was what got computed at persist-time --
not a parsing bug (independently verified: `_parse_grounded_ids` given
that exact footer text correctly returns both IDs). The only way both
of those can be true is that **the trace and the DB row were never the
same request** -- `tutor_agent_client/client.py`'s A2A calls to
`tutor-agent/` carried no correlation ID at all (only the shared secret
and Vercel bypass headers), so `tutor-agent/`'s own Langfuse trace has
no reliable link back to a `TutorExchange` row; question-text-plus-
timestamp matching in a tight sequential 30-question batch isn't
trustworthy enough to root-cause one specific failing exchange. This is
a real gap against Constitution Principle V ("why was this marked
wrong" must have a real, traceable answer) -- for the Tutor Agent
specifically, that question was previously unanswerable.

Fixed by propagating `exchange_id`/`session_id` as new
`X-Tutor-Exchange-Id`/`X-Tutor-Session-Id` headers (no auth role, purely
for correlation) from `tutor_agent_client/client.py`, read back on the
`tutor-agent/` side by a new `_TraceCorrelationMiddleware`
(`agent.py`) that wraps them as Langfuse trace metadata via a new
`tracing.traced_exchange()`, mirroring the backend's own
`traced_request()`/`propagate_attributes(metadata=...)` pattern
exactly (same `metadata=` vs. native `session_id=`/`user_id=` kwargs
reasoning: `GoogleADKInstrumentor` sets its own `session.id`/`user.id`
span attributes from the ADK `Runner`'s own arguments, which would
silently win over the native kwargs). Grading Agent had the identical
gap (`grading_client/client.py` sent no correlation header either) and
was fixed the same way in the same session -- `X-Grading-Question-Id`/
`X-Grading-Learner-Id` headers, a matching `_TraceCorrelationMiddleware`
in `grading-agent/src/agent.py`, `question_id`/`learner_id` metadata via
`tracing.traced_exchange()` there. Backend's own in-process agents
(Diagnostic/Sequencing/Assessment-Generation/Recommendation) were never
affected -- `traced_request()` already links those correctly since
they run in the same process with no A2A hop involved. 8 new unit/
integration tests across all three projects (header-building, header-
extraction middleware, and a real in-memory-`LangfuseSpanProcessor`
proof that the metadata actually lands on every span, mirroring
`backend/tests/integration/test_tracing_metadata_propagation.py`'s
existing harness for both new copies) -- full regression re-confirmed
green in all three: backend 328/328 (real dev DB), tutor-agent 21/21,
grading-agent 22/22.

**T038 (SC-002 grounding rate) itself is still not re-measured** -- this
session closed the observability gap that was blocking root-causing it,
not the grounding rate question itself. Next step: re-run the
30-question fixture against a real deployment with these fixes in
place, then pull each exchange's now-correctly-linked trace directly by
`exchange_id` to see what actually happened for any exchange that ends
up ungrounded.

PR #38 review addressed two non-blocking findings (both flagged as
low-severity: only reachable if `TUTOR_AGENT_SHARED_SECRET`/
`GRADING_AGENT_SHARED_SECRET` itself leaks, since
`_SharedSecretAuthMiddleware` gates everything ahead of the new
middleware either way) -- an unvalidated correlation-header value could
otherwise let a leaked secret inject arbitrary text into Langfuse trace
metadata (log/trace injection). Both `_TraceCorrelationMiddleware`s now
re-parse the header value as a UUID via a new `_parse_uuid_header()`
helper, dropping anything that doesn't round-trip cleanly rather than
passing it through verbatim; 2 new tests per project cover a malformed
header value resolving to `None`. Also added `.github/workflows/
tutor-agent-tests.yml` (mirrors `grading-agent-tests.yml`'s pattern:
`tutor-agent/`'s own pytest suite had no CI coverage of its own until
now, only ever run locally) -- no ground-truth-eval-gate or test-
independence-check step included, since spec 012 has no equivalent
requirement to spec 007's FR-008/SC-003 ground-truth eval gate.

**T038 re-run attempt (2026-08-27, `016-tutor-retrieval-resilience`
branch): found the real root cause, and a real reliability gap along
the way.** With PR #38's trace-correlation fix live on `main`, ran the
30-question fixture for real against production -- through a disposable
test guardian+learner (not the demo learner: `GET /api/tutor/
exchanges/{id}` requires an owning guardian or enrolled instructor,
which the demo learner has neither, so the documented fixture procedure
can't actually verify grounding through it -- a separate, still-open
minor gap). **26 of 30 requests failed with a fast (~1s) unhandled `500
{"detail":"Internal server error"}`**; the 3 that succeeded came back
`grounded: false` with zero retrieved passages. Pulled the actual Vercel
function log for one failure: `search_passages()`'s embedding call was
throwing `litellm.exceptions.APIConnectionError` wrapping a Voyage `429`
-- **the Voyage AI account has no payment method on file, capping it at
3 requests/minute** (Voyage's own error message states this outright).
This is almost certainly the real root cause behind the original T038
"0/30 grounded" finding too, not a code defect in retrieval itself: the
one fully-correct trace found during that investigation (5 relevant
passages, 2 correctly cited) was very likely the one request that
happened to land inside the 3-RPM window.

That failure mode also exposed a genuine gap, fixed the same session:
`search_passages()` (`backend/src/services/retrieval/passage_search.py`)
had no retry and `services/tutor/session.py`'s `prepare_message` created
the `TutorExchange` row *after* calling it -- so an embedding-provider
failure propagated as a raw unhandled 500 with **no `TutorExchange` row,
no audit-log event, no trace of any kind**, worse than finding H2's
original deadlock (which at least left a row behind to notice). Fixed
by: (1) `_embed_query` now retries once with backoff (`MAX_ATTEMPTS`/
`RETRY_BACKOFF_SECONDS`, same shape as `tutor_agent_client`/
`grading_client`'s existing retry constants) before raising a new
`EmbeddingUnavailableError`; (2) `prepare_message` now creates the
exchange row *before* retrieval runs, catches any retrieval failure the
same broad way it already catches an A2A-stream-open failure, persists
it via the existing `_persist_failed_exchange`, and raises the same
`TutorUnavailableError` (503) contracts/api.md already defines for "the
Tutor Agent couldn't be reached" -- retrieval failing before the A2A
call is even attempted is just an earlier instance of that same case.
`contracts/api.md`'s `503` section updated to match. 2 new tests
(`test_embed_query_retry.py`'s retry/exhaustion behavior, plus an
integration test mirroring the existing A2A-unavailable-then-recovers
test but for the retrieval path) -- full regression: backend 331/332
(the 1 failure is `test_submit_placement_response_shape_and_unknown_
topics`, a known enum-OID-cache flake unrelated to this change,
confirmed passing in isolation), tutor-agent 22/22.

**Still not done**: SC-002 itself remains unmeasured -- the account is
staying on Voyage's free tier rather than adding a payment method, so
the actual re-run needs to pace all 30 requests well under 3 RPM (one
question roughly every 20-25s at minimum, plus real per-question
latency on top -- a ~15-20 minute run), not fire them back-to-back like
this attempt did. Also created (and not yet cleaned up -- no self-serve
account deletion exists yet, a known gap) 3 disposable test guardian
accounts in production during this investigation
(`tutor-eval-*@cognivo-test.invalid`), needing direct DB removal
whenever convenient.

**Scope**: The conversational Tutor Agent, answering plain-English
questions and delegating to the Sequencing Agent ("what does this
learner already struggle with?"), the Recommendation Agent, and
potentially the Grading Agent via A2A, tying the multi-agent system
together end to end -- plus two capabilities that only make sense once
this agent exists at all:
- **Vector-grounded retrieval**: the Tutor Agent retrieves relevant
  content-artifact material (via pgvector, see `tech-stack.md`) before
  answering, so its answers are grounded in the subject's actual content
  rather than freeform generation with no retrieval step -- directly
  reducing hallucination risk in exactly the agent where that risk is
  highest.
- **Streaming responses**: the Tutor Agent's answers stream
  token-by-token to the learner rather than waiting for a full response,
  using Vercel/Next.js's native streaming support.

**Why retrieval and streaming are part of this milestone, not their
own**: Both are properties of the Tutor Agent's response generation --
neither is a capability that exists independently of this agent, so
splitting them into separate milestones would create an artificial
dependency chain (a "vector DB milestone" that produces nothing usable
until the Tutor Agent that consumes it also exists).

**Definition of done** (draft, to be formalized in its own `spec.md`):
- The Tutor Agent's delegation to other agents is demonstrated to be
  inspectable, not a black box -- the actual intermediate calls and
  responses are visible, not only the final answer.
- For a defined percentage of test questions, the Tutor Agent's answer
  is verified to cite or ground in specific retrieved content-artifact
  passages, not only plausible-sounding freeform generation -- the
  retrieval step must be shown to matter, not just exist.
- Streaming is verified to render incrementally against the live Vercel
  deployment, not only in local development.
- Milestones 1-8's full suites still pass.

**Explicitly not included**: vector-grounded retrieval for any other
agent (Assessment-Generation, Grading, and Recommendation all operate
directly on structured content-artifact data and don't need it).

---

## Milestone 10: Multimodal Question Stimuli -- Image-Based Questions
**Spec**: `specs/003-multimodal-question-stimuli/spec.md`
**Status**: Spec drafted, pending `/speckit-clarify` and `/speckit-plan`.

**Scope**: Content artifacts can bundle images as question context
(with required alt-text for accessibility); the Assessment-Generation
Agent can produce structured questions that display a bundled image;
grading remains the exact same deterministic answer-key comparison
established in Milestone 1 -- this milestone introduces no new grading
logic. Images work correctly on the live Vercel deployment.

**Why this comes here, deliberately**: This milestone's only real
dependency is Milestone 1 -- it doesn't need any of Milestones 2-9. It's
sequenced this late anyway because it extends the platform's *capability
breadth* rather than deepening the core personalization thesis
Milestones 1-9 establish. Scoped deliberately narrow (image stimuli
only, not audio, video, or learner-submitted images) for the same
reason every other milestone in this roadmap avoids stacking multiple
hard axes at once.

**Definition of done**:
- All acceptance scenarios in
  `specs/003-multimodal-question-stimuli/spec.md` pass.
- SC-002 (100% of image questions have alt text) and SC-003 (missing/
  oversized images fail at content-artifact load time, not at
  question-display time) are hard gates -- the former for accessibility,
  the latter because a validation gap here would surface as a broken
  question in front of a learner instead of a caught error during
  content authoring.
- Milestones 1-9's full suites still pass (regression check).

**Explicitly not included**: audio or video stimuli, learner-submitted
images as answers, AI-generated (rather than pre-supplied) images,
shared/deduplicated image asset libraries across subjects.

---

## Milestone 11: Fine-Tuned Misconception Classifier
**Spec**: not yet written -- do not begin until Milestone 10 DoD is met.
**Status**: Not started.

**Scope**: Using the (question, learner free-text answer, expected
grade) data accumulated since Milestone 6, fine-tune a lightweight
classifier to detect specific, named misconception patterns -- not just
right/wrong, but e.g. "this learner consistently confuses X with Y" --
feeding richer signal into the Recommendation Agent's next-step
suggestions than a bare correctness count can provide.

**Why this is sequenced here**: Strictly depends on Milestone 6 having
accumulated real graded data -- attempting this earlier would mean
fine-tuning on too little or unrepresentative data. Positioned after
Milestone 10 because, like multimodal support, this is engineering
depth rather than a gap in the core product's completeness.

**Definition of done** (draft, to be formalized in its own `spec.md`):
- The fine-tuned classifier's misconception-detection accuracy is
  measured against a hand-labeled validation set and compared against a
  prompted-only baseline -- reported honestly even if the fine-tuned
  model does not outperform the baseline, since that would itself be a
  legitimate, useful finding, not a failure to hide.
- The classifier's output is consumed by the Recommendation Agent
  (Milestone 2) as an optional enrichment -- the Recommendation Agent
  MUST continue to function correctly if the classifier is unavailable
  or not yet trained, i.e. graceful degradation, not a new hard
  dependency on a fine-tuned model existing.
- Milestones 1-10's full suites still pass.

**Explicitly not included**: fine-tuning any other model in the system
(question generation, grading itself, sequencing) -- scoped narrowly to
this one misconception classifier, consumed only by Recommendation.

---

## Milestone 12: Prompt Versioning and Regression Testing
**Spec**: not yet written -- do not begin until Milestone 11 DoD is met.
**Status**: Not started.

**Scope**: Every prompt used by every agent (Assessment-Generation,
Grading, Recommendation, Tutor) is stored as a versioned artifact --
never an inline string literal scattered through code -- with a
regression-test harness that runs each agent's existing eval suite
(Milestone 3's personalization eval, Milestone 6's grading-accuracy
eval) against a candidate prompt change before it can be promoted. Ties
directly into the `staging`/`main` and CI review gate already
established by Constitution Principle X: a prompt change is just another
PR that must pass its relevant eval gate, not a special case that
bypasses it.

**Why this is sequenced here**: Most valuable once most agents and their
prompts already exist (specifically, after the Tutor Agent in Milestone
9) -- versioning a system that's still substantially changing shape
provides less value than versioning a comparatively stable one.

**Definition of done** (draft, to be formalized in its own `spec.md`):
- 100% of agent prompts are stored as versioned artifacts, verified by
  an automated check scanning for inline prompt string literals in
  engine source.
- A deliberately regressed test prompt (scripted to make grading or
  generation quality measurably worse) is verified to be caught by the
  CI gate before merge -- not merely by manual review.
- Milestones 1-11's full suites still pass.

**Explicitly not included**: automatic prompt optimization or
auto-tuning -- a distinct, much larger capability not implied by
"versioning," and not built here.

---

## Milestone 13: Semantic Caching
**Spec**: not yet written -- do not begin until Milestone 12 DoD is met.
**Status**: Not started.

**Scope**: Near-duplicate or semantically similar LLM requests
(question-generation requests for the same topic/difficulty within a
short window, grading of very similar free-text answers) are served
from a cache rather than re-invoking the model, reducing cost and
latency -- extending the near-duplicate-avoidance logic already
established in Milestone 1's FR-008, now applied as a caching strategy
rather than only a "don't show the same thing twice" rule.

**Why this is sequenced last**: Most valuable once call volume is high
enough to matter -- after Grading (Milestone 6) and the Tutor Agent
(Milestone 9) both exist and meaningfully increase LLM call volume
beyond Milestone 1's much lower baseline. Sequenced after prompt
versioning (Milestone 12) since a cache keyed on a specific prompt
version needs that versioning to already exist, or cache entries would
silently survive a prompt change they were never validated against.

**Definition of done** (draft, to be formalized in its own `spec.md`):
- A defined cache-hit-rate target is measured against a synthetic load
  test.
- Cache entries are verified to be invalidated on content-artifact
  version changes -- a cached response must never be served against a
  content artifact it was not generated for.
- Caching is verified not to weaken Constitution Principle I's
  determinism guarantee: a cache hit and a cache miss for the same
  input must be indistinguishable in output, differing only in latency.
- Milestones 1-12's full suites still pass.

**Explicitly not included**: caching that crosses per-learner
near-duplicate history -- caching applies to the underlying generation
call, not to what's ultimately shown to a specific learner, so a cached
question can still be excluded from a specific learner's next question
if they've already seen it recently.

---

## Known gap: real-account deletion pathway is unimplemented (Constitution Principle VIII)

Surfaced 2026-08-23 during `012-tutor-agent`'s `/speckit-analyze` pass,
while checking whether Milestone 9's two new real-learner-linked
tables (`tutoring_sessions`, `tutor_exchanges`) were covered by
Milestone 7's deletion guarantee. They now are, on paper
(`specs/009-privacy-retention/data-classification.md`, updated the
same day) -- but tracing that guarantee back to actual code found that
FR-004/FR-005 (`specs/009-privacy-retention/spec.md`'s "a real
learner's or instructor's data can be deleted on request") were
**deliberately deferred, not implemented**: spec 009's own tasks.md
says outright "No tasks in this spec... Milestone 7 proper's own
tasks.md is where they become implementation tasks." Checking
`010-instructor-classroom/tasks.md` shows only T011, which creates the
`DeletionRequest` *model* -- no endpoint or service ever executes an
actual deletion. `grep`-ing `backend/src/` for any deletion-execution
logic confirms this: nothing found beyond the model.

This is not a Milestone 9 regression -- it predates this milestone and
was not caught by Milestone 7's own DoD checks or "Known gaps" notes.
It **is** a live Constitution Principle VIII gap: every real
guardian/learner/instructor account created since Milestone 7 shipped
has no working right-to-erasure path despite the constitution
requiring one exist before real data is ingested at all. Needs its own
prioritized fix -- implementing `DELETE /api/account` (or equivalent)
against the already-modeled `DeletionRequest`/`RetentionRecord`
entities and the now-complete `data-classification.md` -- rather than
being rediscovered again at the next milestone that touches real
learner data.

**Correction, 2026-08-25** (code review on the Milestone 9 staging->main
promotion PR): this section's own "now are, on paper" framing above was
accurate, but `data-classification.md`'s two cascade-deletion rows
(mastery/assessment/questions, and Milestone 9's tutoring transcripts)
stated "Same as `display_name` (FR-005's cascade)" as if a working
mechanism already existed, rather than a specified-but-unimplemented
policy -- exactly the false-confidence risk this gap warns about,
just restated as settled fact in a different document. Both rows
reworded to explicitly say "not yet implemented" and point back here,
rather than asserting parity with a mechanism that doesn't exist for
any table yet.

---

## Out of current roadmap (not planned, not rejected)
- A second, cross-language A2A agent purely to demonstrate
  interoperability (e.g. a Go-based Grading service) -- Milestone 6
  leaves the Grading Agent's language undecided rather than defaulting
  to a cross-language choice for its own sake, per Constitution
  Principle VI. Worth revisiting once Milestone 6 is underway and
  there's a concrete reason (team skill, performance) to pick a specific
  language.
- Deployment platforms other than Vercel (e.g. a Kubernetes-based setup
  for the Grading Agent if it later needs resources Vercel Functions
  can't provide) -- not needed unless Milestone 6 planning surfaces a
  concrete constraint Vercel genuinely can't meet.
- Multimodal input beyond image stimuli -- Milestone 10 covers images
  displayed as question context only. Audio or video stimuli,
  learner-submitted images as answers (which would require real
  vision-based grading, not the deterministic comparison Milestone 10
  keeps unchanged), and AI-generated (rather than pre-supplied) images
  are all still deferred, each named explicitly in Milestone 10's own
  Assumptions rather than left ambiguous.
- External-resource recommendation (linking to specific third-party
  videos, articles, or content outside this platform) -- explicitly
  deferred from the Recommendation Agent's scope (Milestone 2) per that
  feature's own Assumptions, since evaluating third-party content
  quality is a distinct problem from evaluating this platform's own
  generated content.
- Quiz templates or reuse across terms/semesters -- explicitly deferred
  from Milestone 8's instructor-assigned quizzes scope, a plausible
  future idea rather than something required to prove the core
  capability works.
- Fine-tuning any model other than the Milestone 11 misconception
  classifier (question generation, grading, or sequencing themselves) --
  explicitly out of that milestone's scope; would need its own spec and
  its own justification if pursued later.
- Automatic prompt optimization/auto-tuning -- explicitly deferred from
  Milestone 12's prompt-versioning scope, a distinct and much larger
  capability.
- Schema-drift detection as a required CI check (not auto-applied
  migrations) -- surfaced 2026-08-22 when production's DB turned out to
  be several Alembic migrations behind (Milestone 5's `quiz_sessions`
  onward), causing a live `500` on placement start rather than a caught
  PR-time failure. Chosen direction when this is picked up: a CI job on
  promotion PRs that connects to the target environment's DB and
  compares `alembic current` against `alembic heads`, failing the check
  (not applying anything) if they diverge -- lower blast radius than
  auto-migrating in CI or in Vercel's build step (see the discussion in
  this session: both have real ordering/concurrency issues against
  Vercel's independent git-triggered deploys), and consistent with this
  project's existing pattern of deliberate manual infra steps (T044's
  Vercel provisioning, the Deployment Protection bypass secret) rather
  than new deploy automation. Needs `STAGING_DATABASE_URL`/
  `PRODUCTION_DATABASE_URL` as GitHub Actions secrets (distinct from
  their Vercel-env-var copies) before it can be built.
- Grade-banded curriculum scoping (grades 1-12) per subject, with an
  initial placement quiz that also assesses a starting grade level (not
  just per-topic mastery as Milestone 1 does today), placement questions
  labeled with the grade they represent, a skip option for a question
  too far above the learner's current assessed level, and progressive
  grade-level unlocking -- a learner only sees next-grade questions
  after mastering the current grade's content. Raised 2026-08-22 after
  live testing surfaced some generated questions as too hard for their
  intended level. Real open design question for whoever scopes this:
  how "grade" relates to the existing Topic/mastery-state model --
  likely a new content-artifact-owned dimension (per Constitution
  Principle III, never an engine-side conditional), but whether it's a
  property of each topic, a grouping above topics, or a per-question
  attribute needs its own `/speckit-clarify` before a spec is written,
  given how directly it touches the mastery model's structure
  (Principle I).
- Content-curation policy differing by classroom type (an "open"
  classroom's content is LLM-curated; a "closed" classroom's content is
  human-created or LLM-generated-then-human-approved). Raised
  2026-08-22 during `/speckit-clarify` on `specs/009-privacy-retention/
  spec.md`, where the "open vs. closed" distinction itself was scoped
  down to enrollment-gating only (who may join a classroom) -- this
  content-curation half is a distinct, different-feature concern
  (Milestone 1's flagged-question review mechanism, FR-011, and
  Milestone 7's content-review workflow ownership), not a privacy/
  retention matter. Needs its own scoping pass whenever Milestone 7
  proper or the content-review workflow is picked up.

Keeping this section explicit documents what was considered and
deliberately deferred, rather than leaving it ambiguous whether it was
forgotten.

**Version**: 3.1.0 -- 2026-08-16, Milestone 1 marked complete (deployed
and verified live on Vercel); 3.0.0 (2026-08-15, added Milestones 8
(Instructor-Assigned Quizzes), 11 (Fine-Tuned Misconception Classifier),
12 (Prompt Versioning and Regression Testing), and 13 (Semantic
Caching); extended Milestone 9 (Tutor Agent) with vector-grounded
retrieval and streaming responses; renumbered former Milestones 8-9 to
9-10 accordingly)

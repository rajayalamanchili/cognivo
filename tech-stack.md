# Tech Stack

**Project**: Cognivo
**Status**: Locked for Milestone 1
**Last amended**: 2026-08-16

## Purpose

Cross-feature technology decisions live here, once, so every feature's
`plan.md` treats this file as authoritative rather than re-deciding
these choices. A `plan.md` that deviates from this file without first
amending it fails the Constitution Check.

## Deployment target: Vercel (locked from Milestone 1)

Per Constitution Principle IX, this product must be live-deployable and
demoable at every milestone, not just locally runnable. This is a
constraint that shapes several choices below, not an afterthought:

- **Vercel Functions run as stateless, ephemeral serverless functions**
  with bounded execution time (default limits on the Hobby tier; longer
  durations available via Fluid Compute on paid tiers). No persistent,
  long-running background process is available.
- **Consequence for agent state**: any session or mastery state an agent
  needs across requests MUST be persisted to the database, never held
  in an agent framework's default in-memory session store. This is
  enforced explicitly in the ADK section below.
- **Consequence for agent execution time**: any single agent call
  (especially a multi-step reasoning loop) must complete within the
  active function's execution window. Assessment-generation and grading
  calls are expected to fit comfortably within default limits; if a
  future milestone's agent loop risks exceeding it, that milestone's
  `plan.md` must explicitly address it (e.g. via Fluid Compute, or by
  breaking the loop into resumable steps), not discover it at deploy
  time.
  - **Milestone 6 hit this condition**: `answer_question` awaits
    length/rate-limit/moderation checks, the Grading Agent's A2A call
    (with retries), and the mastery-state write, all synchronously in
    one request. CI's ground-truth eval gate measured ~3.3s average per
    grading call in-process alone (no network hop) -- a real production
    call adds an A2A round-trip and Vercel cold start on top. The root
    `vercel.json` now sets an explicit `maxDuration: 30` on the backend
    function (previously unset, meaning an unstated platform default) so
    a slow worst-case path fails as a clean `grading_unavailable`
    response instead of a hard platform-level kill. **Live-verified
    2026-08-21**: a top-level `functions` key isn't valid alongside
    `services` -- Vercel rejects the deploy ("the owning service is
    ambiguous"), confirmed via a real PR build failure. `functions` MUST
    be nested under the specific service's own object in a Services
    `vercel.json` (`services.backend.functions`), not top-level; fixed,
    pending redeploy confirmation. Whether 30s itself is within the
    deployed plan's tier still isn't independently confirmed (the deploy
    succeeding only proves the config is syntactically valid, not that
    a 30s-duration invocation has actually been exercised) -- revisit if
    a real request approaches that ceiling. Resolved via `/speckit-clarify`
    on 2026-08-21: SC-006 now covers the full request path (not just the
    grading call) at a 10-second, 95th-percentile target grounded in
    this measured data, and the retry bound
    (`services/grading_client/client.py`) dropped from 2 retries to 1 so
    worst-case latency stays comfortably under the 30s ceiling --
    see spec 007's `spec.md` Clarifications (Session 2026-08-21) and
    `research.md` §7.
- **Frontend and backend deploy together** using Vercel's support for
  running a Python backend and a Next.js frontend in one project
  (Vercel "Services"), so the whole product -- not just the frontend --
  is one deployable, demoable unit.

## Observability

| Concern | Choice | Rationale |
|---|---|---|
| Tracing backend | Langfuse | Has a current, officially documented ADK integration via OpenTelemetry (`GoogleADKInstrumentor` from the `openinference` package) -- a three-line instrumentation call traces every agent invocation, tool call, token cost, and latency with no per-agent custom wiring. Framework-agnostic (also functions as a generic OTel backend), so it covers any future non-ADK code path too. |
| Instrumentation mechanism | `openinference.instrumentation.google_adk.GoogleADKInstrumentor().instrument()`, called once at application startup | This is the documented, current integration path as of this stack's decision date -- verify it's still current at `/speckit-plan` time, since this ecosystem moves quickly. |
| Serverless compatibility | Spans MUST be explicitly flushed before a Vercel Function returns | OTel span export is normally batched/async, which does not survive a serverless function suspending after response -- an explicit flush call is required at the end of every request handler, not an optional nicety. This is exactly the kind of interaction between two "locked" decisions (Langfuse + Vercel) that must be handled deliberately, not discovered as a bug later. |
| Relationship to the pedagogical audit log | Separate and complementary, not a replacement | Per Constitution Principle V -- Langfuse traces answer "what happened inside this model call"; the audit log (Postgres, per Milestone 1) answers "why was this pedagogical decision made." Both are required. |

## Branching, CI, and release workflow

Per Constitution Principle X.

| Concern | Choice | Rationale |
|---|---|---|
| Branch model | Two long-lived branches: `staging` and `main` | `main` is what Constitution Principle IX's live deployment reflects; `staging` is where every change is validated first. |
| Feature branches | `NNN-feature-name` (matches Spec Kit's own branch-naming convention), PR'd into `staging` | Keeps the existing Spec Kit workflow (`create-new-feature.sh`) as the source of branch names -- no separate naming scheme to maintain. |
| Promotion `staging` → `main` | A dedicated pull request, never a direct push or fast-forward merge | Makes promotion a reviewable, auditable event, not an implicit side effect of merging a feature branch. |
| Vercel environment mapping | `staging` branch deploys to a Vercel preview/staging environment; `main` deploys to production | Vercel's native branch-deployment support maps directly onto the two-branch model -- no extra infrastructure needed to get a live staging URL distinct from the production one. |
| Automated PR review | `anthropics/claude-code-action@v1`, configured in automation mode (no `@claude` trigger required) so it runs on every PR automatically | Anthropic's own first-party, currently GA GitHub Action for this exact purpose -- runs the full Claude Code runtime against the PR diff and posts findings, rather than a thin wrapper around a single API call. |
| Merge gate | Branch protection on both `staging` and `main` requiring the automated review check (and, once they exist, the relevant `check:*` scripts for whichever milestone the PR touches) to pass before merge is allowed | Operationalizes Constitution Principle X's "necessary but not sufficient" requirement -- a human approval alone cannot bypass the automated check. |

## Demo account strategy

Per Constitution Principle VIII's requirement that demo accounts be
explicitly flagged and visibly distinguishable, not merely assumed
obvious.

| Concern | Choice | Rationale |
|---|---|---|
| Data-level marking | An explicit, non-nullable `is_demo` boolean on every account/profile record, set at creation time -- never inferred from a naming pattern or absence of activity | An inferred signal ("no real name set" or similar) is exactly the kind of ambiguity Principle VIII exists to rule out; an explicit flag can't be silently wrong. |
| UI-level marking | A persistent, visible "DEMO ACCOUNT" badge shown on every screen while a demo account is active -- not a one-time login-page notice a user can miss or forget | The badge must be genuinely unmissable, not merely present somewhere in the markup -- this is a demo-safety requirement, not a cosmetic one. |
| Entry point | A dedicated "View Demo" path that logs into a seeded demo account directly, separate from the real sign-up/login flow -- a visitor should never be able to mistake creating a real account for entering the demo | Keeps the demo experience from ever colliding with real account creation, and keeps `is_demo` assignment deterministic (set once, at seed time, never as a side effect of a real signup flow). |
| Demo account reset | Seeded demo accounts (one instructor, at least one student, per Milestone 7) are reset to a known-good seeded state on a schedule (e.g. daily) | A public demo that drifts into a confusing state over time (a demo student with a chaotic, half-finished mastery history from many strangers' clicks) undermines the demo's own purpose -- a scheduled reset keeps it representative. |
| Milestone 1's lighter version | Before real auth exists (Milestone 7), Milestone 1 seeds one or more clearly-labeled demo learner profiles (same `is_demo` flag, same UI badge) so the live Vercel deployment has something to show a visitor rather than an empty state | Constitution Principle IX requires the product be demoable from Milestone 1 -- an empty, dataless demo doesn't satisfy that in spirit, even if it satisfies it technically. |

## Tutor Agent grounding and delivery (Milestone 9)

| Concern | Choice | Rationale |
|---|---|---|
| Vector storage | `pgvector` extension on the existing Postgres/Neon database | No new infrastructure -- the database already chosen for mastery state, sessions, and audit logs gains vector search capability as an extension rather than requiring a separate vector database service. |
| Retrieval scope | Content-artifact material only, not third-party sources | Consistent with the Recommendation Agent's own boundary (Milestone 2) against external-resource recommendation -- retrieval stays grounded in content this platform actually owns and can vouch for. |
| Response delivery | Token-by-token streaming via Vercel/Next.js's native `Response` streaming support (Route Handlers) | No additional service or library needed -- this is a capability of the already-locked Vercel/Next.js stack, not a new dependency. |

## Agent orchestration

| Concern | Choice | Rationale |
|---|---|---|
| Agent framework | Google ADK (Python) | Purpose-built for specialized sub-agents sharing state via `ToolContext.state`, and the natural home for the mastery model as a tool the Sequencing Agent calls. |
| ADK session/state backing | Database-backed session service (Postgres), not the framework's default in-memory store | Required by the Vercel deployment constraint above -- a stateless function cannot rely on in-process memory surviving between requests. |
| Cross-agent protocol | A2A, applied selectively per Constitution Principle VI | Not every agent boundary in Milestone 1 uses A2A -- Diagnostic, Sequencing, and Assessment-Generation start as local ADK sub-agents (fast, in-process, no justification yet for a network boundary). The Grading Agent is the anticipated first real A2A service, once free-text grading exists (Milestone 6), because independent versioning of grading rubrics without redeploying the whole system is a concrete, stated need. |
| Language for a future remote agent | Deferred | If/when the Grading Agent becomes a remote A2A service, its language and whether it deploys as a separate Vercel project (for true independent deployment) or a route within the same project is a Milestone-3-planning decision. |
| A2A inbound authentication | A shared-secret header (`X-<Agent>-Secret`, e.g. `GRADING_AGENT_SHARED_SECRET`), checked via `hmac.compare_digest` by each A2A service's own ASGI middleware before a request ever reaches the agent/model. Fails closed if the expected secret isn't configured. Each A2A service gets its own distinct secret -- never one secret shared across services. | Locked by Constitution Principle VI's v1.5.0 amendment: a network-reachable A2A service MUST authenticate inbound requests before this project's backend-owned guardrails (rate limit, moderation, length caps) can be assumed to apply. Closes the gap found in the Grading Agent's original public, unauthenticated endpoint (spec 007, PR #18) -- none of those guardrails ran inside the agent itself, so an unauthenticated endpoint let anyone bypass all of them. Per-service secrets, not a shared one, contain blast radius if a single secret leaks. |
| A2A secret rotation | Each service's middleware MUST accept either a `CURRENT` or an optional `NEXT` secret env var (e.g. `GRADING_AGENT_SHARED_SECRET` / `GRADING_AGENT_SHARED_SECRET_NEXT`), so rotation is set-next -> confirm the caller sends it successfully -> promote next to current -> remove the old value, never a single cutover requiring the backend and the agent's independently-deployed Vercel project to redeploy in the same instant. A rotation *tool* (automated secret generation/deployment via Vercel's API) is explicitly out of scope for now. | Decided at Milestone 6, not deferred to Milestone 9, specifically because the Tutor Agent is already a second confirmed A2A service in `roadmap.md` -- building the rotation seam into the pattern once is cheaper than retrofitting it onto two already-live single-secret services later. No rotation *tooling* yet because nothing here rotates on a schedule -- a documented manual runbook is sufficient at two services; revisit if a third A2A service or an actual rotation cadence emerges. |
| A2A leaked-secret compensating control | Each A2A service MUST re-check a total request-length cap and re-run content moderation on the raw inbound request text itself (e.g. `grading-agent/src/guardrails.py`'s `before_model_guardrail`, wired via ADK's `before_model_callback` so it runs before the model call), in addition to the shared-secret auth above. Deliberately does NOT include a duplicated rate limiter -- that would require the A2A service to hold shared state across invocations, reversing its stateless-pure-function design (research.md §3), so it's out of scope until an actual abuse pattern is observed. | Authentication alone assumes the secret never leaks; it can. If it does, the backend's own length/rate/moderation guardrails (Principle IV table, backend-only) are bypassed entirely along with it. These two checks are cheap, stateless, and bound the worst case of that scenario: a length cap bounds token cost per request, moderation stops disallowed content from reaching the model. Not a duplication of the backend's per-request guardrails for legitimate traffic (which already passed them before ever reaching this service) -- a compensating control for the one failure mode (secret compromise) that auth alone can't cover. |
| A2A deployment: Vercel Deployment Protection bypass | Vercel's own Vercel Authentication (SSO) protects non-production deployments by default -- discovered live 2026-08-21 as a `401 "Protected deployment"` from Vercel itself, in front of `_SharedSecretAuthMiddleware`, not from it. Where the A2A service's deployment target has this enabled, the caller MUST also send Vercel's "Protection Bypass for Automation" secret as `x-vercel-protection-bypass` (e.g. `GRADING_AGENT_VERCEL_BYPASS_SECRET`, optional -- only sent if configured, since not every deployment target has this protection on). | This is a Vercel platform-level gate neither this project's shared-secret auth nor its compensating guardrails have any visibility into -- a request can fail here before any of this repo's own A2A security code ever runs. Locked as a pattern (not just a one-off env var) so a future A2A service's plan.md doesn't have to rediscover this the same way: check Deployment Protection settings before assuming the shared secret alone is sufficient. |

## Mastery model

| Concern | Choice | Rationale |
|---|---|---|
| Approach | Bayesian Knowledge Tracing (BKT), locked at Milestone 1 `/speckit-plan` time (see `specs/001-domain-agnostic-core/research.md` §1) | Constitution Principle I requires determinism and explainability; an LLM "impression" of mastery cannot satisfy either. |
| Parameters | Fixed global constants, not per-topic-fitted: `p(L0)=0.3`, `p(T)=0.1`, `p(S)=0.1`, `p(G)=0.25` (multiple-choice) / `0.05` (numeric) | Per-topic EM-fitting needs a volume of real learner response data that must not exist pre-Milestone-7 (Constitution Principle VIII); global constants keep the model fully deterministic without overfitting synthetic seed data. Revisit once Milestone 6's real grading data exists. |
| Mastery bands | Three bands: "struggling" (< 0.4), "developing" (0.4-0.7), "mastered" (>= 0.7); a topic with no answer yet is "unknown," not a stored value on this scale | Locked via `specs/001-domain-agnostic-core/spec.md` Clarifications (2026-08-15); only struggling/developing topics are eligible for next-topic selection. |
| Implementation | Python, called as an ADK tool by the Sequencing Agent, reading/writing mastery state from Postgres on every call | Stateless-function-compatible by construction -- no in-memory model state assumed to persist between requests. |

## Content schema

| Concern | Choice | Rationale |
|---|---|---|
| Format | Versioned YAML/JSON per subject, under a `content/<subject>/` convention, bundled with the deployed function or loaded from the database at request time | Keeps subject-specific knowledge entirely out of engine code, and avoids relying on local filesystem writes, which are not reliably persistent across serverless invocations. |
| Validation | A load-time schema + graph-integrity check (no cycles, no unreachable topics) | Per spec.md FR-002 -- must fail at artifact-load time, not mid-session. |

## Backend / API

| Concern | Choice | Rationale |
|---|---|---|
| API framework | FastAPI, deployed as a Vercel Python Function (ASGI) | FastAPI has first-class, officially documented support as a Vercel-deployed backend framework, and pairs cleanly with ADK's Python-first design. |
| Question/assessment generation | Structured-output calls to an LLM, called through ADK's `LiteLlm` model wrapper so the provider stays a runtime config value rather than hardcoded; default provider/model is Anthropic Claude (Sonnet), set via env var. Locked at Milestone 1 `/speckit-plan` time (see `specs/001-domain-agnostic-core/research.md` §2). Output validated against the content artifact before display (FR-007). | The validation step, not the model choice, is what carries the correctness guarantee. LiteLLM keeps the provider swappable without a code change; Claude was chosen as the default for consistency with this project's existing Anthropic-centric tooling (`claude-code-action`) and strong structured-output reliability. |
| Near-duplicate question detection | In-process text similarity (TF-IDF cosine or `difflib.SequenceMatcher`) over the last 5 generated questions per learner+topic -- no vector database or embeddings API (FR-008) | Locked at Milestone 1 `/speckit-plan` time (research.md §3). Deliberately does not pull `pgvector` forward from its Milestone 9 Tutor Agent scope -- a 5-question window doesn't justify that infrastructure yet. |

## Frontend

| Concern | Choice | Rationale |
|---|---|---|
| Framework | Next.js + TypeScript | Vercel's native framework, zero deployment friction, and pairs with the FastAPI backend via Vercel Services in one project. |
| Scope for Milestone 1 | Solo-learner flow only (placement, next-question, answer submission, mastery view) | Instructor/classroom UI is explicitly deferred (Milestone 7 per roadmap.md), consistent with spec.md 001's Assumptions. |

## Data layer

| Concern | Choice | Rationale |
|---|---|---|
| Database | PostgreSQL via Neon, provisioned through Vercel's integration marketplace | Serverless-friendly connection handling (no long-lived connection pool assumptions) is required to work correctly from ephemeral Vercel Functions; stores mastery state, ADK session state, assessment events, and content-artifact metadata. Locked over Supabase: this project owns its backend (FastAPI + ADK) rather than building on a client SDK/auto-REST/RLS layer, so Supabase's bundled Auth/Storage/Realtime add no value here, while Neon's branching model (below) directly fits the serverless, git-branch-shaped deployment model Principle IX and the Branching table above already commit to. |
| Environment provisioning | One Neon project, not three separate ones. Two persistent branches -- `production` (root) and `staging` (branched from `production`) -- map 1:1 onto the Branching table's `main`/`staging` Vercel environments. Local development and per-PR preview deploys use ephemeral, on-demand Neon branches (created via Neon's Vercel-native integration, which auto-creates/destroys a branch per Vercel preview deployment) rather than a third shared persistent branch. | Neon branches are copy-on-write and near-instant/free to create or destroy, so branch-per-environment (and branch-per-preview) gives every environment full data/schema isolation without the drift, cost, and manually-triplicated migration runs three separate Neon projects would require. This reuses the two-branch git model already locked above instead of inventing an uncoordinated third environment axis. |
| Migrations per environment | `alembic upgrade head` runs against the target branch's own `DATABASE_URL` as an explicit step of that environment's deploy (a Vercel build/deploy hook for `staging`/`main`; a manual or Neon-integration-triggered step for ephemeral preview/dev branches) -- never a shared migration run assumed to cover more than one branch. | Branches share schema history via copy-on-write only at the moment they're created; each diverges immediately once either side migrates. Without an explicit per-branch migration step, a `staging` → `main` promotion PR could silently ship against a `main` schema nobody has actually migrated yet. |
| Learner data | Synthetic only for Milestone 1 | Per Constitution Principle VIII -- no real learner data until a dedicated privacy/retention spec exists (anticipated around Milestone 7). |

## Testing & evaluation

| Concern | Choice | Rationale |
|---|---|---|
| Backend unit/integration tests | `pytest` | De facto standard for FastAPI/Python; integrates cleanly with ADK's Python-first design. Locked at Milestone 1 `/speckit-plan` time (research.md §4). |
| Frontend component tests | `Vitest` + React Testing Library | Standard modern pairing for Next.js, faster iteration than Jest with no material tradeoff for a fresh project. |
| Deployment smoke test / E2E | `Playwright`, run against the live Vercel URL | Drives a real browser against the actual deployed app -- the most faithful check of Constitution Principle IX's "deployable and demoable," not just that the API responds. |
| Determinism check (SC-001) | Automated script re-running identical placement answers and diffing mastery output | Runs in CI against the same database-backed state model used in production, not an in-memory shortcut that wouldn't catch a serverless-state bug. |
| Extensibility check (SC-004) | Automated script scanning engine source for subject-id-keyed conditionals | Enforces Constitution Principle III mechanically rather than by code review alone. |
| Agent-test-independence check (spec 002's SC-005) | Automated script (`backend/scripts/check_no_shared_recommendation_sequencing_fixtures.py`) failing CI if the Recommendation Agent's and Sequencing Agent's test modules import each other's scripted-scenario fixtures | Same rationale as the SC-004 row above -- SC-005 exists to prove Constitution Principle IV's agent-boundary requirement is real, not decorative, so its "verified by inspection" language is operationalized as an actual CI check rather than left to manual review. Locked at spec 002's `/speckit-plan` time (see `specs/002-recommendation-agent/research.md` §6). |
| Question-quality check (SC-003) | Automated validation step run against every generated question before display, plus an offline batch-eval script for regression testing | Distinct from the display-time validation (FR-007) -- this is the automated *test* that the validation logic itself keeps working. |
| Deployment smoke test | An automated check that the live Vercel deployment's placement-through-first-question flow works end to end, run after every deploy | Directly verifies Constitution Principle IX -- "deployable" is claimed only once this passes, not merely once `vercel deploy` exits successfully. |

## Explicitly not yet decided (do not pre-select)

- The Grading Agent's language and deployment shape -- Milestone 6 decision, once free-text grading's concrete needs are clear.
- Instructor auth/identity approach -- Milestone 7 decision, tied to the privacy/retention spec required by Constitution Principle VIII.
- Fine-tuning approach and base model for the misconception classifier -- Milestone 11 decision, made once Milestone 6's accumulated grading data is actually available to inspect.
- Prompt-versioning storage mechanism (a dedicated table, a file-based store, or a third-party prompt-management tool) -- Milestone 12 decision.
- Semantic-caching layer (in-database via Postgres, or a dedicated cache like Redis/Upstash) -- Milestone 13 decision, made once Milestone 9's actual call volume is known well enough to size the cache correctly.
- Whether Fluid Compute (for longer execution windows) is needed -- revisit if any agent call's typical latency approaches the default execution limit.

**Version**: 1.7.0 -- Amended 2026-08-15 (Milestone 1 `/speckit-plan`:
locked BKT parameters and three-band mastery model, LLM provider
(LiteLLM + Claude Sonnet default) and near-duplicate detection approach
for question generation, and backend/frontend/E2E testing frameworks;
see `specs/001-domain-agnostic-core/research.md`); 1.7.0 (Milestone 1
`/speckit-implement` Phase 6 prep: locked Neon over Supabase, and locked
the dev/staging/prod provisioning strategy as one Neon project with
`production`/`staging` persistent branches plus ephemeral per-preview/
per-developer branches, rather than three separate Neon projects); 1.8.0
-- Amended 2026-08-16 (Milestone 2 `/speckit-plan`: locked an automated
CI check as the enforcement mechanism for spec 002's SC-005
agent-test-independence requirement, matching the existing SC-004
extensibility-check precedent; see
`specs/002-recommendation-agent/research.md` §6); 1.9.0 -- Amended
2026-08-20 (locked A2A inbound authentication as a per-service
shared-secret header validated via `hmac.compare_digest`, plus
current/next dual-secret rotation support, as the enforcement mechanism
for Constitution Principle VI's v1.5.0 amendment; see spec 007's
`grading-agent/src/agent.py` for the reference implementation this
pattern is locked from)

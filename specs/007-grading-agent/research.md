# Research: Free-Text Grading via a Real A2A Service

**Feature**: `007-grading-agent` | **Phase**: 0 (outline & research)

## §1. A2A implementation: ADK's `to_a2a()` wrapping an ADK `LlmAgent`, backed by `a2a-sdk`

**Decision**: The Grading Agent is a Google ADK `LlmAgent` (same pattern as
Diagnostic/Sequencing/Assessment-Generation), wrapped into an A2A server
via `google.adk.a2a.utils.agent_to_a2a.to_a2a()` -- ADK's own utility
(not `a2a-sdk`'s), which internally depends on `a2a-sdk` for the actual
JSON-RPC/protocol routing -- converting an ADK `BaseAgent` instance into
a Starlette-based ASGI application with no hand-written protocol code.
The main backend acts as an A2A *client*, issuing a JSON-RPC/HTTP
request to the Grading Agent's public URL and awaiting its response.

**Verified at `/speckit-implement` time (T010)**: importing and building
the app, then exercising it with Starlette's `TestClient` under a real
ASGI lifespan, confirms `GET /.well-known/agent-card.json` returns
`200` with a well-formed Agent Card advertising JSON-RPC support at the
root -- not just an import-succeeds check. This required adding the
`a2a-sdk[http-server]` extra (pulls in `sse_starlette`, which `a2a-sdk`'s
base install does not include but its server-routing code path needs) --
narrower than the plain `a2a-sdk` dependency originally scoped here.
ADK's A2A support (`A2aAgentExecutor`, `to_a2a()`, and related pieces)
is marked **EXPERIMENTAL** upstream as of the installed version
(`google-adk` 2.7.x) -- a real breaking-change risk this project accepts
for now, not yet mitigated by pinning or a compatibility shim.

**Rationale**: `to_a2a()` is the documented, first-party path for
exactly this situation (an existing ADK agent that needs to become an
independently deployable A2A service) -- it auto-generates the Agent
Card and request-handling pipeline, so no protocol plumbing is written
by hand. It also produces a Starlette ASGI app, which Vercel's Python
runtime already supports (the same class of app FastAPI itself is
built on), so no new deployment mechanism is needed beyond what
`tech-stack.md` already locks for the existing backend.

**Alternatives considered**:
- Hand-rolled HTTP/JSON endpoint (no A2A protocol at all): rejected --
  this is exactly the "network boundary without genuine A2A" anti-
  pattern Constitution Principle VI warns against; if the boundary
  exists, using the actual interoperability protocol is what makes the
  "agent" framing meaningful rather than decorative.
- `adk api_server --a2a` (CLI-based agent-directory server): rejected
  in favor of the programmatic `to_a2a()` call -- the CLI approach is
  suited to serving a directory of many agents together; this feature
  needs exactly one agent as one deployable unit, and `to_a2a()` gives
  tighter, explicit control over what's exposed via `uvicorn`/Vercel's
  Python runtime.

Sources: [a2a-python (official SDK)](https://github.com/a2aproject/a2a-python), [Exposing Agents via A2A -- ADK docs](https://google.github.io/adk-docs/a2a/quickstart-exposing/), [A2A Protocol](https://a2a-protocol.org/latest/)

## §2. Deployment shape: a separate Vercel project, not a Services route

**Decision**: The Grading Agent deploys as its own Vercel project (new
top-level `grading-agent/` directory in the monorepo, its own
`vercel.json`, its own Python runtime deployment, its own public URL),
distinct from the existing `backend/` + `frontend/` Vercel Services
project. The main backend calls it over HTTPS using a
`GRADING_AGENT_URL` environment variable.

**Rationale**: SC-005 requires demonstrating that a grading-logic fix
ships "while every other agent and the frontend remain on their
previously-deployed version." Vercel's Services feature (used for
`backend/`+`frontend/`) explicitly deploys its member services
*together* on every push to one project -- the opposite of what this
milestone needs to prove. A genuinely separate Vercel project is the
only option that produces an independent deployment event/pipeline,
which is the literal mechanism Constitution Principle VI's
justification depends on.

**Alternatives considered**:
- Vercel Services (same project as `backend/`+`frontend/`): rejected --
  each service can build independently, but all services still deploy
  together on the same push/deployment event, per Vercel's own
  documentation of the feature's purpose ("frontend and backend deploy
  together"). This would make SC-005 undemonstrable as written.
- A route within the existing FastAPI app (in-process, no network
  boundary at all): rejected -- this is the exact "local ADK sub-agent"
  shape Constitution Principle VI says is the default until a concrete
  need justifies otherwise; free-text grading's need (independent
  rubric-logic versioning/evaluation) is the concrete need already
  named in `tech-stack.md`, so the boundary should be real, not
  in-process.

Sources: [Vercel Services](https://vercel.com/docs/services), [Vercel Monorepos](https://vercel.com/docs/monorepos)

## §3. Grading Agent statelessness -- no direct database access

**Decision**: The Grading Agent has no database connection and persists
nothing itself. Its A2A response is a pure function of its request
(question rubric + learner answer in, graduated score + criteria
breakdown + Grading Logic Version out). The calling backend is solely
responsible for validating that response (FR-014) and persisting it
(as an `AssessmentEvent`, see data-model.md).

**Rationale**: Mirrors the existing Assessment-Generation Agent's own
boundary exactly -- `generate_question()` returns a validated
`GeneratedQuestionDraft`; the *caller* (`questions.py`) persists it.
Keeping the Grading Agent stateless also directly resolves this
feature's idempotency requirement (FR-010, FR-014, §4 below) for free:
a stateless service has no side effect to duplicate, so retrying a
timed-out call is safe by construction, and no new DB credentials/
migration surface is needed in the second Vercel project.

**Alternatives considered**:
- Grading Agent owns its own DB writes (e.g., a Grading Decision
  table it inserts into directly): rejected -- this would require a
  second set of DB credentials and Alembic migration history in an
  independently-deployed project, doubling the audit-log/schema
  surface for no benefit, since the backend already needs to persist
  the mastery-state update in the same transaction regardless.

## §4. Idempotency: the existing "already answered" guard is sufficient -- no new mechanism

**Decision**: FR-010's and FR-014's "a retry can never record a second
grading decision or mastery-state update" guarantee is satisfied by
two things already true or already decided: (a) the Grading Agent is
stateless (§3), so retrying the outbound A2A call itself has no
duplicate-write risk; (b) the backend's *persistence* step (writing the
`ANSWER_SUBMITTED`/`MASTERY_UPDATED` events and updating
`MasteryState`) is already guarded by the existing
`_already_answered()` check (`backend/src/api/routes/questions.py:136`,
raising `ConflictError` if `question_id` already has an
`ANSWER_SUBMITTED` event) -- this guard already applies uniformly to
every question type, free-text included, with no new code. No new
idempotency-key column or table is introduced.

**Clarification on the spec's framing**: `spec.md`'s edge case
describes this as "the exact failure class this project already hit
once and fixed for the quiz feature's answer-history bug" (commit
`6b3bc9b`). On inspection, that bug's actual mechanism was different --
a same-transaction query re-reading its own just-flushed event as
false "prior" history, not a retried network call producing a genuine
second write. Both are the same *category* of bug (a single learner
action's effect on mastery state getting counted more than once), but
the fix here is not a reuse of that commit's specific
`exclude_question_id` technique -- it's the pre-existing
`_already_answered()` guard plus this feature's stateless-Grading-Agent
design (§3).

**Alternatives considered**:
- A dedicated idempotency-key column (e.g. a UUID generated client-side
  and stored on first attempt, checked on retry): rejected as
  unnecessary -- `_already_answered()` already provides this exact
  guarantee at the point that matters (the persistence step), and
  adding a second mechanism would duplicate what's already enforced.

## §5. Moderation check: prompt-based classification via the existing LiteLLM/Claude path

**Decision**: FR-012's pre-grading moderation check is a lightweight
LLM classification call (ALLOW/BLOCK-style, per Anthropic's own
documented content-moderation pattern) issued through the same
`LiteLlm` wrapper already locked in `tech-stack.md`, using Claude Haiku
(not the Sonnet default used for grading/generation) for
cost/latency -- moderation is a high-volume, low-complexity
classification task where Haiku's cited $1/$5-per-million-token pricing
and ~500-1000ms response time comfortably fit within SC-006's 5-second
budget alongside the grading call itself.

**Rationale**: Reuses already-locked infrastructure (no new vendor
dependency, no `tech-stack.md` amendment needed) and follows Anthropic's
own documented moderation-filter pattern. A dedicated third-party
moderation API would be a new, unlocked technology choice this
project's `tech-stack.md` doesn't call for.

**Alternatives considered**:
- A dedicated third-party moderation/toxicity API: rejected -- would
  require amending `tech-stack.md` to introduce a new vendor for a
  capability the existing LLM provider already covers adequately at
  this project's scale.
- A local classical ML/keyword-based filter: rejected -- far weaker at
  catching the "coded language, policy-adjacent phrasing" cases
  Anthropic's own documentation calls out as exactly where an
  LLM-based check outperforms a keyword list, and this project already
  has an LLM call path available.

Sources: [Content moderation -- Claude Platform Docs](https://platform.claude.com/docs/en/about-claude/use-case-guides/content-moderation), [claude-cookbooks: building_moderation_filter](https://github.com/anthropics/anthropic-cookbook/blob/main/misc/building_moderation_filter.ipynb)

## §6. Rate limiting: DB-backed sliding window, not in-memory

**Decision**: FR-016's per-learner rate limit is enforced by counting
this learner's `AssessmentEvent` rows (both successful
`ANSWER_SUBMITTED` and rejected `FREE_TEXT_SUBMISSION_REJECTED` rows
for free-text questions) within the trailing time window, at request
time, via a normal DB query -- no in-memory counter, cache, or
token-bucket state.

**Rationale**: `tech-stack.md`'s Vercel deployment-target section is
explicit: "any session or mastery state an agent needs across requests
MUST be persisted to the database, never held in-memory" -- an
in-memory rate limiter would silently fail to limit anything in
production, since each Vercel Function invocation is a fresh, isolated
process. This is exactly the kind of Vercel-serverless mismatch
Constitution Principle IX exists to catch before it ships.

**Alternatives considered**:
- In-process/in-memory counter: rejected outright per the above --
  would not work correctly on Vercel at all, not merely a performance
  tradeoff.
- A dedicated rate-limiting service (e.g. Upstash Redis): rejected as
  premature -- `tech-stack.md`'s "Explicitly not yet decided" section
  defers a dedicated cache/rate-limit service to Milestone 13's
  semantic-caching decision, once real call volume is known; a simple
  DB count query is sufficient at this project's current (synthetic,
  low-volume) scale.

## §7. Locked numeric parameters

Per this project's established convention (BKT parameters, quiz
question-count bounds, etc. locked at `/speckit-plan` time rather than
left to the spec), this feature locks:

| Parameter | Value | Rationale |
|---|---|---|
| Graduated-score -> binary threshold (FR-005) | `0.7` | A conventional "70% to pass" grading bar. Chosen independently of, and not to be confused with, the mastery model's own `0.7` "mastered" band cutoff (`tech-stack.md`) -- the two are unrelated thresholds that happen to share a value. |
| Max free-text answer length (FR-015) | `2000` characters | Generously exceeds any genuine short-answer response (~400 words) while bounding worst-case prompt size/cost per grading call, including retries. |
| Per-learner grading rate limit (FR-016) | `20` submissions per rolling `10`-minute window | Comfortably covers a full quiz session's worth of free-text questions for a genuine learner while bounding cost/abuse exposure. |
| Moderation-flag escalation threshold (FR-013) | `5` flagged submissions per rolling `24`-hour window | Low enough to catch a genuine pattern, high enough that one or two ambiguous moderation calls don't over-trigger the account-level flag. |
| Grading Agent call retry bound (FR-010, FR-014) | `2` retries (`3` total attempts), short fixed backoff | Bounded so total latency (including retries) stays within SC-006's 5-second budget. |
| Initial Grading Logic Version (§8) | `"v1"` | Starting value; bumped whenever the Grading Agent's scoring prompt/logic changes (FR-008). |

These are implementation constants (Python module-level values in the
Grading Agent and the backend's rate-limit/moderation service code),
not database-configurable settings -- consistent with how BKT's
parameters are fixed global constants rather than per-topic-fitted
(`tech-stack.md`).

## §8. Grading Logic Version: a code constant, not a database row

**Decision**: "Grading Logic Version" (spec.md Key Entity) is a single
string constant defined in the Grading Agent's own source
(`GRADING_LOGIC_VERSION = "v1"`), included in every A2A response
payload, and copied verbatim into the persisted `AssessmentEvent`
payload by the caller (see data-model.md). It is bumped in code,
committed to git, and redeployed -- there is no `grading_logic_versions`
table to manage.

**Rationale**: Matches this project's existing convention for versioned
model parameters (BKT's constants) -- git history already provides the
audit trail of when and why a version changed; a database table would
duplicate that with no benefit, since nothing about a Grading Logic
Version is per-request configurable.

## §9. Schema changes: two enum-value additions, no new tables

**Decision**:
- `question_type` Postgres enum gains `'free_text'` (extends
  `QuestionType`), via `ALTER TYPE question_type ADD VALUE IF NOT
  EXISTS 'free_text'` -- the exact technique
  `533736af33d7_recommendation_event_types.py` already established for
  `assessment_event_type`.
- `assessment_event_type` Postgres enum gains
  `'free_text_submission_rejected'` (extends `AssessmentEventType`),
  same technique, same migration file style.
- No new tables. The free-text rubric reuses `GeneratedQuestion
  .answer_key` (already a type-agnostic JSON column, per
  `backend/src/models/generated_question.py`'s existing MC/numeric
  shapes) with a new free-text shape: `{"criteria": [{"description":
  str, "weight": float}, ...]}`. A "Grading Decision" (spec.md) is an
  `AssessmentEvent` of type `ANSWER_SUBMITTED` with a richer payload
  (see data-model.md); a "Moderation Flag" (spec.md) is an
  `AssessmentEvent` of type `FREE_TEXT_SUBMISSION_REJECTED`.

**Rationale**: Every prior milestone's schema changes follow this same
minimal-footprint pattern (extend an existing enum, extend an existing
JSON payload shape) rather than introducing new tables for what is
fundamentally the same event stream with richer content. `answer_key`
is already documented as "type-agnostic at the DB layer" -- free-text's
rubric shape is simply a third variant alongside MC's and numeric's.

## §10. Question-type selection stays content-artifact-owned -- no engine change needed

**Decision**: No change to `preferred_question_type()`
(`backend/src/agents/diagnostic/agent.py:29`) or the Sequencing Agent's
call to it. A subject's `subject.yaml` opts a topic into free-text
questions purely by adding `free_text` to that topic's
`preferred_question_types` list; `QuestionType("free_text")` then
resolves correctly once the enum is extended (§9). At least one topic
in each of the two existing seeded subjects (`algebra-1`, `biology`)
will list `free_text` to prove Constitution Principle III's
subject-agnostic claim continues to hold for the new type, matching
Milestone 1's own precedent of proving a second subject from day one.

**Rationale**: This is the mechanism that already makes question-type
selection subject-agnostic and engine-untouched for MC vs. numeric --
free-text is simply a third value flowing through the same,
unmodified path. Confirms FR-001 and FR-011 require no new selection
logic, only the new type's generation/grading/moderation handling
itself.

## §11. Ground-truth eval gate: accuracy/consistency threshold and near-threshold margin (FR-008, SC-003)

**Added at `/speckit-implement` time (T039/T040)**: spec.md's FR-008 and
SC-003 both require this threshold -- and FR-008's near-threshold-score
margin -- to be "locked and recorded at planning time in this feature's
`research.md`," but neither was actually added to the §7 locked-parameter
table during `/speckit-plan`. Recording them here now, before T039/T040
consume them, keeps the "locked in exactly one place" guarantee spec.md
asks for intact, even though the lock is happening one command later
than originally intended.

| Parameter | Value | Rationale |
|---|---|---|
| Near-threshold-score margin (FR-008) | `±0.05` around the `0.7` score-to-binary threshold (§7) -- i.e. a ground-truth triple with expected `graduated_score` in `[0.65, 0.75]` counts as "near-threshold" | Narrow enough to genuinely exercise the threshold boundary, wide enough to be a realistic band an LLM grader's score could land in for a borderline answer. |
| Ground-truth eval accuracy threshold (FR-008, SC-003) | `>= 90%` of triples' expected `correct` (threshold-derived boolean) matched by the current `GRADING_LOGIC_VERSION` | Mirrors this project's other "high but not 100%" automated gates (e.g. Milestone 3's generation-validation re-check) -- allows for inherent LLM grading variance on genuinely ambiguous ground-truth triples without weakening the gate to the point it can't catch a real regression. |
| Ground-truth eval consistency threshold (FR-008, SC-003) | `>= 95%` agreement between two independent grading runs of the same triple, on the threshold-derived boolean | Catches a scoring-logic change that makes grading nondeterministic/unstable, not just one that's inaccurate on average -- a grader that flips its answer run-to-run is exactly as untrustworthy as one that's simply wrong, per Constitution Principle II. |

**Rationale for locking here rather than adjusting `/speckit-plan`'s
output retroactively**: this project's established convention
(`research.md` §7's own header) is that locked parameters live in
`research.md`; amending this file at `/speckit-implement` time to add a
value that was missed, rather than silently picking it inside
`check_grading_agent_eval.py` (T040), keeps the traceability property
SC-003 explicitly asks for.

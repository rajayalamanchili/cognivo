# Phase 0 Research: Tutor Agent

## §1: Embedding model for `pgvector` retrieval

**Decision**: Voyage AI's `voyage-3` model, called through LiteLLM's
`embedding()` function (`litellm.embedding(model="voyage/voyage-3", ...)`),
mirroring the same LiteLLM-abstracted-provider pattern already used for
every LLM call in this codebase (`ASSESSMENT_GEN_MODEL`,
`MODERATION_MODEL`). New env vars: `TUTOR_EMBEDDING_MODEL` (default
`voyage/voyage-3`) and `VOYAGE_API_KEY`.

**Rationale**: This project's only configured LLM provider is
Anthropic (`ANTHROPIC_API_KEY`, `backend/.env.example`), and Anthropic
does not offer an embeddings API. Voyage AI is Anthropic's own
recommended embeddings partner, is directly supported by LiteLLM (no
new HTTP client to write), and adds exactly one new provider account
rather than pulling in a second general-purpose LLM provider (e.g.
OpenAI) that this codebase has deliberately avoided so far. `voyage-3`
(not the smaller `voyage-3-lite`) is chosen because content-artifact
passages are short, hand-authored paragraphs where retrieval quality
matters more than the marginal cost/latency difference at this
project's demo scale.

**Alternatives considered**:
- OpenAI `text-embedding-3-small` -- rejected: introduces a second
  general-purpose LLM provider account for a single-purpose need,
  when a purpose-built embeddings provider (Voyage) already integrates
  through the existing LiteLLM dependency.
- Google's embedding models (`text-embedding-004`) -- rejected: no
  Google AI Studio/Vertex credentials exist anywhere in this codebase
  today (`google-adk` is an agent *framework* dependency, not a signal
  that Google's model APIs are configured); would add a third provider
  surface for one milestone's needs.
- A locally-run open-source embedding model (e.g. `sentence-transformers`)
  -- rejected: adds a model-serving/runtime concern to a stateless
  Vercel Function that the project has consistently avoided (Constitution
  Principle IX); an API-based embedding call fits the existing
  request/response serverless shape used everywhere else.

## §2: Where retrieval and delegation-context assembly live

**Decision**: The main `backend` is the sole orchestrator of a tutoring
turn. It owns Postgres (including the new `pgvector` column) and the
existing local Sequencing/Recommendation ADK sub-agents, so it:
1. Runs the `pgvector` similarity query itself and selects the top-N
   Retrieved Passages.
2. Calls Sequencing/Recommendation in-process (no network hop -- they
   already run inside the backend) to get the learner's real
   mastery/weak-area state when the question needs it.
3. Bundles the question, retrieved passages, and any needed
   mastery/weak-area context into a single request, and calls the
   Tutor Agent (a new standalone A2A service, `tutor-agent/`) with
   that bundle.
4. The Tutor Agent's job is narrowly scoped to composing a grounded,
   streamed answer from exactly the context it was given -- it does
   not independently query Postgres, call Sequencing/Recommendation,
   or hold any state across requests.
5. The backend persists the TutoringSession/TutorExchange transcript
   and writes the audit-log event (FR-007) as the stream completes.

**Rationale**: `grading-agent/` (this project's only existing A2A
service) has no Postgres/SQLAlchemy dependency at all -- it receives
everything it needs in the request and returns a result; the backend
is the sole data owner and audit-log writer. Giving the Tutor Agent
direct Postgres access or letting it call back into the backend's
session-authenticated endpoints (a real alternative, see below) would
introduce a *new* reverse-authentication problem this project doesn't
have today, and would make the Tutor Agent stateful in a way Grading
Agent deliberately isn't. Keeping the same "backend orchestrates,
A2A service is a pure function over its input" shape means the Tutor
Agent needs no new authentication direction, no database credentials
of its own, and stays consistent with Constitution Principle IX
(stateless, ephemeral functions).

**Alternatives considered**:
- Tutor Agent as orchestrator, calling back into the backend's REST
  endpoints mid-conversation as ADK tool calls -- rejected: requires a
  new service-to-service auth scheme for backend endpoints that are
  currently only guardian/instructor-session-cookie-protected (no
  service-token concept exists yet), and makes the Tutor Agent's
  behavior harder to reconstruct after the fact (its tool calls
  wouldn't automatically land in the backend's existing audit-log
  writer the way an in-process call does). This is exactly the kind of
  A2A-boundary decision Constitution Principle VI says must be
  justified by a concrete need -- no concrete need for this direction
  was found.
- A separate "retrieval service" as its own A2A hop -- rejected: no
  independent-versioning/evaluation need stated (same Principle VI
  bar FR-009 already applied to Sequencing/Recommendation);
  `pgvector` querying is a few lines of SQLAlchemy the backend can run
  directly against a database it already owns.

## §3: Grading Agent delegation ("potentially," per `roadmap.md`)

**Decision**: When a tutoring question needs grading context (e.g. "why
was this answer marked wrong?"), the *backend* -- not the Tutor Agent --
makes that A2A call to the Grading Agent (an already-established
backend-to-grading-agent path since Milestone 6/7) and includes the
result in the same bundled context described in §2. No new
tutor-agent-to-grading-agent A2A path is introduced.

**Rationale**: Keeps exactly one orchestration point (the backend) and
avoids a three-hop A2A chain (backend -> tutor-agent -> grading-agent)
that would need its own new auth direction (tutor-agent calling
grading-agent) for a scenario the existing backend-to-grading-agent
path already covers.

## §4: Streaming transport

**Decision**: The Tutor Agent is built the same way as `grading-agent/`
-- an ADK agent wrapped by `to_a2a()` -- which gives it the A2A
protocol's native `message/stream` (SSE) method for free via
`a2a-sdk` (already a dependency in both `backend` and `grading-agent`,
so no new dependency for `tutor-agent`). The backend's own tutor
endpoint (`POST /api/tutor/sessions/{session_id}/messages`) is a
Next.js/FastAPI-compatible streaming response: it opens the A2A stream
to the Tutor Agent and forwards each received chunk to the frontend as
it arrives, rather than buffering the full answer. The frontend chat
UI reads that response via the browser's native streaming `fetch`
(matching `tech-stack.md`'s already-locked "Vercel/Next.js native
`Response` streaming support" choice).

**Rationale**: Reuses `a2a-sdk`'s existing streaming capability instead
of inventing a second, non-A2A streaming protocol between backend and
tutor-agent; keeps the frontend's streaming contract to one hop
(backend to browser) it already knows how to do.

**Alternatives considered**: A raw HTTP chunked-response endpoint on
the Tutor Agent outside the A2A protocol -- rejected: `to_a2a()`
already produces a conformant A2A service (matching Grading Agent's
pattern exactly, including its Vercel host/port/protocol-derivation
fix, see `tech-stack.md`); bypassing A2A's own streaming method for a
custom one would duplicate work the protocol already provides and
diverge from the one existing precedent this project has for an A2A
service.

## §5: Passage granularity for embedding

**Decision**: One Retrieved Passage per content-artifact field that
carries standalone pedagogical meaning: a topic's `skill_definition
.summary`, plus each of its three `difficulty_calibration` entries
(easy/medium/hard) as separate passages -- four passages per topic,
each tagged with `subject_id`, `topic_id`, `field`, and the
`content_version` it was generated from.

**Rationale**: Content artifacts are short, hand-authored paragraphs
(see `backend/content/biology/subject.yaml`), not long documents --
they don't need a text-splitting/chunking algorithm, just a
field-level pass over the same schema every subject already
implements, keeping this subject-agnostic (Constitution Principle
III). Per-field tagging lets a retrieved passage's provenance
(exactly which field of which topic) be shown under User Story 3's
inspection requirement, not just "some passage from this topic."

**Alternatives considered**: Embedding a single concatenated blob per
topic -- rejected: loses the ability to show *which specific field* a
retrieved answer grounded in (weakens FR-003/US3), and mixes an
easy-difficulty example with a hard one in a single vector, diluting
retrieval quality for a question aimed at one difficulty level.

## §6: Performance target for first-streamed-token latency (SC-001)

**Decision**: Provisional target of first token within 3 seconds,
p95, measured end-to-end from the frontend's request to the first
chunk it renders. `maxDuration: 60` on both the backend's tutor
endpoint and the `tutor-agent/` Vercel function (vs. the Grading
Agent's 30s), since a full streamed conversational answer plausibly
runs longer than Grading's single blocking call.

**Rationale**: No real latency data exists yet for this path (unlike
Grading Agent's SC-006, which was tightened only after real
measurement in `spec 007`). Setting an explicit provisional number now
-- rather than leaving it unstated -- gives `/speckit-tasks` and
`/speckit-implement` a concrete target to build and test against; per
this project's own established pattern (`tech-stack.md`'s Vercel
section), this should be revisited via `/speckit-clarify` once real
measurement exists, the same way Grading Agent's budget was.

## §7: Vercel deployment shape for `tutor-agent/`

**Decision**: `tutor-agent/` is a new, separately-deployed Vercel
project, structured identically to `grading-agent/` (own
`pyproject.toml`, `vercel.json`, `src/agent.py` using ADK's `to_a2a()`
with the same `host`/`protocol`/`port=443` derivation from
`VERCEL_BRANCH_URL`/`VERCEL_URL` that `grading-agent/src/agent.py`'s
`_to_a2a_kwargs` already implements). New env vars on the backend:
`TUTOR_AGENT_URL`, `TUTOR_AGENT_SHARED_SECRET` (+
`TUTOR_AGENT_SHARED_SECRET_NEXT` for rotation, per the pattern already
locked in `tech-stack.md`), `TUTOR_AGENT_VERCEL_BYPASS_SECRET`
(optional, only if Deployment Protection is enabled on that target).

**Rationale**: Directly reuses every already-solved Vercel/A2A
deployment gotcha this project already paid for once (the
`localhost:8000` default-host bug, the Deployment Protection bypass
header, the `functions` key needing to nest under the specific
service in a Services `vercel.json`) instead of rediscovering them for
a second A2A service.

## §8: Rate limiting, session uniqueness, and in-flight concurrency

Added after `/speckit-clarify` on `spec.md` (2026-08-23, run between
Phase 1 and `/speckit-tasks`) resolved FR-013/FR-014/FR-015 -- these
three decisions extend, not replace, §2's orchestration design.

**FR-013 (rate limiting) decision**: Reuse
`services/grading_client/guardrails.py`'s exact mechanism -- a DB
query counting this learner's recent Tutor Exchanges in a trailing
window (never an in-memory counter, since a fresh Vercel Function
invocation has no memory of the last one), returning a
`retry_after_seconds` the same way `check_rate_limit` does today. Same
constants (20 submissions / 10-minute window) as a starting point,
counted via `tutor_exchanges.created_at` directly rather than a join
through `assessment_events` (no `GeneratedQuestion`-style join target
exists here -- `tutor_exchanges` already carries `session_id` ->
`learner_id`).

**Rationale**: FR-013 explicitly calls for reusing the established
pattern, not inventing a new one; matching the existing numeric
constants avoids a second, unexplained rate-limit number in the
codebase without a data-driven reason to differ (revisit once real
usage data exists, same as every other provisional number in this
milestone).

**FR-014 (session uniqueness) decision**: A partial unique index on
`tutoring_sessions (learner_id, subject_id) WHERE status = 'active'`.
`POST /api/tutor/sessions` becomes get-or-create: look up an existing
active session for that `(learner_id, subject_id)` pair first: return
it (`200`) if found, only creating (`201`) otherwise.

**Rationale**: Enforcing this at the database level (not just in
application code) makes the "at most one" guarantee hold even under a
concurrent double-submit (e.g. a flaky network causing the frontend to
retry the open-session call) -- consistent with this codebase's
existing preference for DB-level uniqueness constraints over
application-only checks (e.g. `classroom_rosters.join_code`'s unique
constraint, migration `0892d285dcd8`).

**FR-015 (in-flight concurrency) decision**: No new column --
`tutor_exchanges.answer_text` is already nullable until streaming
completes (data-model.md), so "is there an in-flight exchange in this
session" is simply "does a `TutorExchange` row exist for this
`session_id` with `answer_text IS NULL`." The messages endpoint checks
this before opening a new stream and returns a `409` (see
contracts/api.md) rather than creating a second in-flight row.

**Rationale**: Reuses a column already in the data model instead of
adding a redundant `status`/`in_progress` flag that could drift out of
sync with `answer_text`'s own nullability -- one source of truth for
"is this exchange done."

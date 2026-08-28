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

## §9: FR-016 -- structurally separate grounding channel

Added after `/speckit-clarify` on `spec.md` (2026-08-28, branch
`019-tutor-grounding-structured-output`), prompted by three consecutive
PR-review rounds (PRs #42/#44, see `roadmap.md`'s Milestone 9 section)
each finding a new way `tutor_agent_client/client.py`'s heuristic
parsing of `GROUNDING_MARKER` + a trailing JSON array embedded in the
same streamed text the learner reads could pick the wrong array or
drop real citations -- a bug class inherent to parsing structured data
back out of freeform generation, not fixable by one more scoring
heuristic.

**Decision**: Replace the marker+JSON-in-text protocol with a
dedicated ADK `FunctionTool`, `cite_passages(passage_ids: list[str])`,
that `tutor-agent/src/agent.py`'s `LlmAgent` calls as the terminal
action of the same generation that produced the answer text. The tool
implementation sets `tool_context.actions.skip_summarization = True`
and returns no content of its own (its only purpose is to carry
structured arguments). `google-adk`'s A2A layer converts a
`function_call` content part to an A2A `DataPart` (not a `TextPart`),
tagged with metadata `adk_type: "function_call"`
(`google/adk/a2a/converters/part_converter.py`,
`A2A_DATA_PART_METADATA_TYPE_FUNCTION_CALL`) and carrying
`{"name": "cite_passages", "args": {"passage_ids": [...]}, "id": "..."}`
as its `data`. `tutor_agent_client/client.py` reads each streamed
message's parts directly (not through `get_message_text`, which
already only joins `TextPart`s and silently ignores `DataPart`s --
confirmed via `a2a.helpers.get_text_parts`'s source): forward `TextPart`
content to the learner as today, and read the `cite_passages`
`DataPart`'s `args.passage_ids` as the grounded-ID list, filtered
against `offered_passage_ids` exactly as `_parse_grounded_ids` already
does. `_extract_grounded_id_candidates`/`_candidate_score`/
`_looks_like_grounded_array` and `GROUNDING_MARKER` (both copies, in
`client.py` and `agent.py`) are deleted entirely -- no bracket-scanning
of any kind remains.

**No second LLM call**: confirmed by reading `google-adk`'s installed
source, not assumed. `Event.is_final_response()`
(`google/adk/events/event.py`) returns `True` whenever
`actions.skip_summarization` is set, regardless of whether the event
carries a function call/response. `BaseLlmFlow.run_async()`
(`google/adk/flows/llm_flows/base_llm_flow.py`) loops calling the model
again only `while` the last event is not yet a final response --
so the tool-response event with `skip_summarization = True` ends the
loop immediately after the one generation that already produced both
the answer text and the tool call, in the same streamed response. This
is the same mechanism ADK's own built-in `exit_loop` tool
(`google/adk/tools/exit_loop_tool.py`) uses to end a loop without a
further model turn -- not a novel pattern invented for this feature.

**Timing**: because `cite_passages` is the model's last content block
in one generation (Anthropic's streaming interleaves a trailing
`tool_use` block after preceding text blocks within a single message,
already how Claude's function-calling works), the citation signal
necessarily arrives after the answer text has fully streamed --
directly realizing the SC-001/SC-004 clarification that the citation
step is excluded from both latency measurements.

**Failure handling**: if the model's generation ends without calling
`cite_passages` at all (a compliance failure, not a transport error --
the stream itself completed), `client.py` yields a `TutorAnswerResult`
with `grounded_passage_ids = []`, matching the Edge Cases clarification
-- the already-streamed answer text is never touched, and this is not
treated as a `TutorStreamInterruptedError`/`failed_at` case, since the
stream did complete. "Logged for observability" (spec.md Edge Cases)
means `tutor_agent_client/client.py` emits a standard
`logging.getLogger(__name__).warning(...)` when this is detected --
**not** a Langfuse span attribute via `update_current_span()`, despite
`/speckit-analyze` (2026-08-28) originally recommending exactly that
for finding U2. Verified empirically during implementation (branch
`019-tutor-grounding-structured-output`) and corrected before shipping:
`stream_tutor_answer`'s A2A call is a plain `httpx`/`a2a-sdk` client
call, never wrapped in a `GoogleADKInstrumentor`-instrumented span on
the backend side (only `tutor-agent/`'s own ADK `Runner` invocation is
instrumented, and that's a separate process); `services/tutor/
session.py`'s `traced_request()` only propagates trace *metadata* to
spans other calls create (its own docstring), it does not create a
span itself. Confirmed directly: calling `update_current_span()` with
no active span context logs an internal "No active span" warning and
silently drops the metadata -- exactly the "anomaly logged" claim
this clarification exists to guarantee would have quietly failed.
Standard logging has no such precondition and is always captured by
Vercel's function logs, so it's the mechanism that actually satisfies
the Edge Cases requirement rather than merely appearing to (this is
an LLM compliance anomaly to debug, not a learner-facing pedagogical
decision, so FR-007's audit log is still the wrong fit either way).

**Rationale**: Moves grounding from "hope the model formats a JSON
array correctly inside freeform prose, then heuristically guess which
bracketed span is the real one" to "read a distinct, typed part of the
protocol response" -- the provider's tool-use mechanism guarantees
schema-valid arguments (Anthropic validates `cite_passages`' JSON
Schema before the tool call is ever emitted), so there is no longer a
freeform-formatting surface to parse defensively at all. This directly
serves FR-003/SC-002's reliability and closes the exact bug class the
last three PR reviews kept finding new instances of.

**Alternatives considered**:
- Keep text-embedded, but require a single mandatory sentinel line
  with nothing else on it (spec.md's Option C) -- rejected: still
  relies on the model formatting a bare JSON array correctly in
  freeform text with no provider-level schema guarantee; narrows the
  bug surface but doesn't eliminate it, and this codebase has already
  spent three PRs narrowing that exact surface.
- A2A `DataPart` populated by the model's own free-generated JSON,
  without a tool call (spec.md's Option B) -- rejected: still
  free-generated text the model could format wrong (missing a schema
  guarantee), just relocated to a different part type; the tool-call
  mechanism gets the structural separation *and* the schema guarantee
  in one step, so there's no reason to take only the weaker half.
- A real agentic tool-loop (tool executes, result fed back, model
  continues) -- rejected by FR-016 itself: doubles the billed LLM calls
  per exchange for a tool that has no actual side effect to execute:
  the `skip_summarization` terminal-tool pattern gets the structured
  output without paying for a second generation.

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

## §9: Interrupted-stream recovery and structured delegation context

Added after `/speckit-analyze` (2026-08-23, run against the completed
plan) found two issues in the design above.

**H2 -- FR-015 deadlock on an interrupted stream**: §8's original
`answer_text IS NULL` in-flight marker has no way to distinguish
"still streaming" from "died mid-stream without ever writing an
answer" -- the latter would permanently block that session from ever
accepting another question, since FR-015 would forever see an
in-flight exchange. **Decision**: add `tutor_exchanges.failed_at`
(nullable timestamptz), set on A2A stream failure/timeout; the FR-015
check becomes `answer_text IS NULL AND failed_at IS NULL`
(data-model.md). **Alternatives considered**: a TTL-based check (treat
any exchange older than N minutes with a null answer as abandoned) --
rejected, since it would let a slow-but-still-legitimate stream get
falsely treated as failed near the boundary, and it doesn't actually
fix anything for a stream that fails fast (the row would still block
for the full TTL window for no reason); an explicit `status` enum
column -- rejected as redundant with the simpler two-nullable-column
signal (`answer_text`/`failed_at`), which already fully covers the
three real states (in-flight, completed, failed) without a fourth
column to keep in sync.

**M1 -- `delegation_context`'s shape**: spec.md's "Delegation Call" Key
Entity describes "a record of one call ... including what was asked
and what was returned," implying one record per delegated call. §2/§3
above describe the backend *bundling* context into the Tutor Agent's
request but were silent on whether the persisted record keeps that
per-call granularity or only the merged result. **Decision**:
`delegation_context` is an ordered array of `{agent, request,
response}` objects, one per delegated call (e.g. one entry for a
Recommendation Agent lookup), not a single merged summary --
satisfies US3's acceptance scenario ("inputs and outputs ... visible
and traceable") and SC-003 literally, not just in spirit.
**Alternatives considered**: keeping the single merged-summary shape
(`{"weak_areas": [...]}`) -- rejected, since it can show the *outcome*
but not "what was asked," understating what US3 promises; a separate
`delegation_calls` table -- rejected as unnecessary normalization for
what's already a small, exchange-scoped, append-only list with no
independent query need of its own.

**H1 -- SC-002 has no test-question set to measure against**: flagged
separately (not a design decision, a missing build artifact). Fixed by
adding a Polish-phase task (tasks.md T036) to author
`specs/012-tutor-agent/eval/grounding-test-questions.md` before the
task that verifies against it (T038) -- mirrors Milestone 3's
personalization-eval harness precedent (a fixture checked into the
spec directory, not generated ad hoc at verification time).

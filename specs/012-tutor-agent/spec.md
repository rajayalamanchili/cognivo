# Feature Specification: Tutor Agent -- Conversational Delegation, Vector-Grounded Retrieval, and Streaming Responses

**Feature Branch**: `012-tutor-agent`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Milestone 9: Tutor Agent -- full A2A delegation, vector-grounded retrieval via pgvector, token-by-token streaming" (per `roadmap.md`'s Milestone 9 entry)

## Clarifications

### Session 2026-08-23

- Q: How fast must the Tutor Agent's first streamed token appear, as a concrete, testable number? → A: 3 seconds (p95)
- Q: Should the Tutor Agent conversational endpoint have its own rate limit, separate from the length/moderation checks already in scope? → A: Yes — reuse the existing per-learner rate-limit pattern already established for free-text answer submission
- Q: Can a learner have more than one Tutoring Session open at once, or does starting a new one end any session already in progress for that learner? → A: One active session per learner per subject — reopening returns the existing active session
- Q: If a learner sends a new question before the Tutor Agent finishes streaming its answer to the previous one, what should happen? → A: Reject the new question until the current exchange finishes streaming

### Session 2026-08-28

- Q: Should the grounding/citation signal move to a channel structurally separate from the answer text the learner sees, instead of being embedded in the same streamed prose and parsed back out afterward? → A: Yes -- a dedicated terminal tool/function call (e.g. `cite_passages`) whose arguments are the passage-ID list, ending that generation there with no loop-back to the model for a further turn, so this does not add a second billed LLM call per exchange.
- Q: Does the grounding-citation tool call happen strictly after the full answer text has finished streaming (outside SC-001/SC-004's timing), or must it complete within those same latency budgets? → A: After the answer text finishes streaming; SC-001/SC-004 measure only the text portion and exclude the citation step.
- Q: If the model fails to produce a valid citation tool call at all after the answer text has already streamed successfully, what should happen? → A: Persist `grounded = false` with an empty passage list, keep the already-streamed answer text as-is, log the anomaly -- no retry, no learner-visible error, no retroactive failure marking.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask the Tutor a plain-English question (Priority: P1)

A learner (via their guardian's session, or the seeded demo learner) is
practicing a topic and wants a conceptual explanation, not another
question -- e.g. "why does photosynthesis need light?" They open a
tutoring chat, type the question, and the Tutor Agent answers in plain
English, grounded in this platform's own content-artifact material for
that subject, streaming the answer token-by-token rather than making
the learner wait for the full response.

**Why this priority**: This is the feature's entire reason for
existing -- without a working conversational Q&A loop grounded in real
content, there is no Tutor Agent, just a chatbot.

**Independent Test**: Can be fully tested by submitting a single
question against a seeded subject's content artifact and verifying the
answer (a) streams incrementally rather than arriving all at once, and
(b) is grounded in retrieved passages from that subject's actual
content rather than ungrounded freeform generation.

**Acceptance Scenarios**:

1. **Given** a learner viewing a topic they've been practicing, **When**
   they ask the Tutor Agent a plain-English question about that topic,
   **Then** the response begins streaming back within a short, bounded
   time and is grounded in retrieved passages from that subject's
   content artifact.
2. **Given** a learner asks a question with no good match in any
   content artifact, **When** the Tutor Agent answers, **Then** the
   response honestly indicates it isn't grounded in specific retrieved
   material, rather than presenting an ungrounded guess as if it were
   sourced.

---

### User Story 2 - Tutor answers grounded in the learner's actual state (Priority: P2)

A learner asks something that depends on their own performance, not
just subject content -- e.g. "what should I work on next?" or "why do I
keep getting these wrong?" Rather than guessing from the conversation
alone, the Tutor Agent delegates to get that learner's real weak-area
and mastery data, and the answer reflects that real data.

**Why this priority**: This is what makes the Tutor Agent a
personalization surface rather than a generic subject chatbot --
directly extending Constitution Principle I (mastery state comes from
the deterministic model, not an LLM's guess) into the conversational
agent.

**Independent Test**: Can be fully tested by asking a learner with a
known mastery/weak-area state a personalized question and verifying
the answer's content matches that learner's actual recorded state, not
a plausible-sounding but unrelated answer.

**Acceptance Scenarios**:

1. **Given** a learner with at least one recorded "struggling" topic,
   **When** they ask the Tutor Agent what to work on, **Then** the
   answer names that actual struggling topic, not a generic or
   fabricated one.
2. **Given** a brand-new learner with no answer history yet, **When**
   they ask the same question, **Then** the Tutor Agent says so
   honestly rather than inventing a weak area that doesn't exist.

---

### User Story 3 - Inspect why the Tutor said what it said (Priority: P3)

An instructor (or, during development, an engineer) needs to answer
"why did the Tutor tell this learner that?" for a specific
conversation -- which passages were retrieved, which other agent(s)
were consulted, and what each returned -- not just the final chat
transcript.

**Why this priority**: Directly required by Constitution Principle V
(every personalization decision must be logged and explainable) and
Principle IV (delegation must be inspectable, not a black box) --
without this, the Tutor Agent's grounding and delegation claims in
User Stories 1-2 are unverifiable after the fact.

**Independent Test**: Can be fully tested by picking a past tutoring
exchange and confirming an inspector can retrieve the specific
retrieved passages and delegated-agent call(s)/response(s) that
produced it, independent of asking the Tutor Agent itself to explain.

**Acceptance Scenarios**:

1. **Given** a completed tutoring exchange, **When** its record is
   inspected, **Then** the retrieved passages and any delegated agent
   calls (inputs and outputs) that fed that specific answer are visible
   and traceable, not only the final text shown to the learner.

---

### Edge Cases

- What happens when retrieval finds no relevant content-artifact
  passages for the question at all? (Must not silently fabricate a
  grounded-looking citation -- see US1 scenario 2.)
- What happens when a delegated agent call (weak-area lookup, or a
  grading explanation) fails or times out mid-conversation? The Tutor
  Agent must degrade to an honest "I couldn't check that right now"
  rather than guessing in its place.
- What happens when a learner asks something off-topic, inappropriate,
  or an attempted prompt injection ("ignore your instructions and
  ...")? Existing guardrail patterns (moderation, length caps) from the
  Grading Agent apply here too, since this is this project's second
  externally-reachable agent service.
- What happens when streaming is interrupted mid-response (client
  disconnects, function execution time bound reached)? The learner must
  not be left with a silently truncated answer presented as complete,
  and the interrupted exchange must not permanently block that
  session from accepting its next question (an earlier version of
  FR-015's mechanism had exactly this gap, found and closed via
  `/speckit-analyze` -- see data-model.md's `failed_at` field).
- What happens when a learner exceeds the per-window rate limit
  (FR-013)? The learner must see a clear rejection, not a silently
  dropped or endlessly-queued request.
- What happens when a learner sends a new question while the previous
  one is still streaming (FR-015)? The new question is rejected with a
  clear "still answering" response, not interleaved, queued, or
  silently cancelled.
- What happens when the same question is asked twice in a row? (No
  near-duplicate suppression is implied here -- that's Milestone 1's
  question-generation concern, not a conversational one -- but the
  second answer should still be independently grounded, not just
  repeated verbatim from a cache with no re-verification.)
- What happens when the model fails to produce a valid FR-016 citation
  tool call (missing, malformed arguments, or a provider error on that
  step) after the answer text has already streamed successfully? The
  exchange is persisted with `grounded = false` and an empty passage
  list, the already-streamed answer text is kept as-is, and the
  anomaly is logged for observability -- MUST NOT retry the citation
  step as a second LLM call (FR-016 rules that out for cost) and MUST
  NOT retroactively mark the exchange failed once the learner has
  already received the answer text.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let a learner submit a plain-English
  question and receive a conversational answer, where "a learner"
  means either a guardian's own session acting on a targeted real
  learner's behalf (matching Milestone 8's guardian-mediated pattern)
  or the seeded demo learner -- no new real-learner-facing login
  surface is introduced by this milestone.
- **FR-002**: The system MUST retrieve relevant passages from the
  asked-about subject's content-artifact material before generating an
  answer, and MUST ground the answer in what was actually retrieved
  rather than generating freeform with no retrieval step.
- **FR-003**: The system MUST be able to show, for any given answer,
  which specific passages were retrieved and used -- not just that
  retrieval happened.
- **FR-004**: When no sufficiently relevant passage is found, the
  system MUST say so rather than presenting an ungrounded answer as if
  it were sourced.
- **FR-005**: The system MUST deliver answers to the learner
  incrementally (token-by-token or an equivalent streaming
  granularity), not only as a single complete response after full
  generation.
- **FR-006**: When a learner's question depends on their own recorded
  performance (e.g. "what should I work on," "why am I getting this
  wrong"), the system MUST obtain that learner's actual mastery/
  weak-area state from the existing deterministic mastery model and
  Recommendation Agent output -- MUST NOT have the Tutor Agent
  independently guess or re-derive a mastery judgment from
  conversation context alone (Constitution Principle I).
- **FR-007**: The system MUST log, for every tutoring exchange, enough
  detail to reconstruct after the fact what was retrieved and which
  other agent(s) were consulted and what they returned -- answering
  "why was I told this" the same way Constitution Principle V already
  requires for sequencing and grading decisions.
- **FR-008**: Every Tutor Agent invocation MUST emit an observability
  trace (inputs, outputs, latency, token cost), in addition to the
  pedagogical audit log in FR-007, consistent with every other agent in
  this project since Milestone 1.
- **FR-009**: The Tutor Agent MUST be deployed as its own standalone A2A
  service (mirroring the Grading Agent's pattern), reaching Sequencing
  and Recommendation's existing output through the backend's current
  APIs rather than requiring either to be freshly split out as its own
  A2A service -- neither has an independent-versioning/evaluation need
  established that would justify that boundary (Constitution Principle
  IV/VI). A true A2A call to the Grading Agent is in scope only where a
  concrete tutoring scenario needs it (see Assumptions).
- **FR-010**: If the Tutor Agent calls another network-reachable A2A
  service, that call MUST be authenticated (shared-secret header
  pattern already locked in `tech-stack.md` for the Grading Agent) --
  MUST NOT assume network-level privacy is sufficient on its own
  (Constitution Principle VI).
- **FR-011**: If the Tutor Agent is deployed as its own externally
  reachable service, it MUST apply the same compensating guardrails
  (request-length cap, content moderation) already established for the
  Grading Agent, independent of its inbound authentication, so a leaked
  secret alone cannot bypass every content guardrail.
- **FR-012**: The system MUST NOT retrieve or ground answers in
  third-party/external sources -- retrieval scope is limited to this
  platform's own content-artifact material (already locked in
  `tech-stack.md`), consistent with the Recommendation Agent's existing
  external-resource boundary (Milestone 2).
- **FR-013**: The system MUST rate-limit how many questions a learner
  can submit to the Tutor Agent in a given window, reusing the same
  per-learner rate-limit pattern already established for free-text
  answer submission (Milestone 6) rather than a new scheme -- bounding
  LLM cost/abuse risk on what is otherwise an unbounded freeform-text
  surface.
- **FR-014**: The system MUST allow at most one active Tutoring
  Session per learner per subject -- opening a session for a subject
  the learner already has an active session in MUST return that
  existing session rather than creating a duplicate.
- **FR-015**: The system MUST reject a new question submitted to a
  Tutoring Session while a prior question's answer is still streaming,
  with a clear "still answering" response -- MUST NOT interleave two
  answers or silently queue/cancel the in-flight one, so at most one
  Tutor Exchange is ever in flight per session (keeps FR-007's audit
  trail unambiguous).
- **FR-016**: The Tutor Agent MUST communicate which retrieved passages
  an answer actually grounded in (FR-003) through a channel
  structurally separate from the streamed answer text -- MUST NOT
  embed that signal in the same prose the learner reads and recover it
  by parsing that text afterward. This MUST be a dedicated tool/
  function call (e.g. `cite_passages`) whose arguments are the
  passage-ID list, configured as a terminal action within the same
  generation that produced the answer -- MUST NOT loop back to the
  model for a further turn, so this does not add a second billed LLM
  call per exchange.

### Key Entities

- **Tutoring Session**: A bounded, subject-scoped conversation between
  a learner (via the access model resolved in FR-001) and the Tutor
  Agent; groups a sequence of exchanges and is the unit an instructor/
  engineer inspects under User Story 3. At most one is active per
  learner per subject at a time (FR-014).
- **Tutor Exchange**: One question-answer turn within a Tutoring
  Session; owns its own retrieved-passage set, any delegated-agent
  call(s) and their responses, and the final streamed answer text.
- **Retrieved Passage**: A specific unit of content-artifact material
  (with its source content artifact and location within it) surfaced
  by vector retrieval for a given Tutor Exchange.
- **Delegation Call**: A record of one call the Tutor Agent made to
  another agent (Sequencing/Recommendation/Grading) while producing a
  Tutor Exchange, including what was asked and what was returned --
  the raw material User Story 3's inspection is built from.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A learner sees the first part of the Tutor Agent's answer
  begin appearing within 3 seconds (p95) of asking, measured end to
  end from the question being submitted (streaming, not a single long
  wait for a complete response). FR-016's citation tool call happens
  after the answer text finishes streaming and is excluded from this
  measurement -- it is not part of what the learner waits on for the
  answer itself to begin or finish rendering.
- **SC-002**: Across a defined set of test questions with known
  content-artifact coverage, at least 90% of answers are verified to
  cite or ground in a specific retrieved passage relevant to the
  question, not just a plausible-sounding freeform answer.
- **SC-003**: For 100% of sampled tutoring exchanges, an inspector can
  reconstruct which passages were retrieved and which other agent
  calls (if any) fed the final answer, without asking the Tutor Agent
  itself to explain.
- **SC-004**: Streaming is verified to render incrementally against the
  live Vercel deployment (not only local development). The trailing
  FR-016 citation tool call is not itself a rendered chunk and is not
  part of what this incremental-rendering check verifies.
- **SC-005**: Milestones 1-8's full test suites still pass unmodified.

## Assumptions

- Milestone 8's guardian-mediated access pattern (a guardian's own
  session acts on a targeted real learner's behalf; the seeded demo
  learner remains separately reachable) is who can open a Tutoring
  Session (FR-001) -- this milestone does not introduce a new
  real-learner-facing login surface, consistent with every prior
  milestone's stated scope.
- "Full A2A Delegation" in `roadmap.md`'s Milestone 9 title refers to
  the Tutor Agent itself being deployed as this project's next
  standalone A2A service (mirroring the Grading Agent's pattern and
  its locked auth/guardrail/deployment conventions in `tech-stack.md`),
  not that Sequencing or Recommendation are also freshly split out as
  A2A services (FR-009) -- they stay local ADK sub-agents, reached
  through the backend's existing APIs.
- Vector retrieval covers the content-artifact material already
  established by Milestone 1 onward (both required subjects); no new
  content-authoring capability is introduced by this milestone.
- Grading Agent delegation ("potentially," per `roadmap.md`) is
  in scope only where a concrete tutoring scenario needs it (e.g.
  explaining why a free-text answer was graded a certain way) -- not a
  requirement that every tutoring exchange touch the Grading Agent.
- Moderation/length-cap guardrails and the shared-secret A2A auth
  pattern are reused from the Grading Agent (Milestone 6) as-is, not
  redesigned for the Tutor Agent.

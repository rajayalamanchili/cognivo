# Feature Specification: Semantic Caching

**Feature Branch**: `023-semantic-caching`

**Created**: 2026-09-02

**Status**: Draft

**Input**: User description: "milestone 13"

## Clarifications

### Session 2026-09-02

- Q: When a grading or question-generation response is served from a
  cache hit instead of a fresh model call, does the platform still need
  its own pedagogical audit-log entry and a fresh Langfuse trace? → A:
  Both a full audit-log entry and a new Langfuse trace are created for
  every cache hit, exactly as for a fresh model call.
- Q: Should the 30% cache-hit-rate target (SC-001) be measured as one
  combined number across both cache types, or separately per type? →
  A: Separately -- question-generation and grading each independently
  must reach at least 30%.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Serve Repeated Question-Generation Requests From Cache (Priority: P1)

When multiple learners (or the same learner across sessions) trigger a
next-question generation for the same topic and difficulty band close
together in time, the platform reuses a previously generated,
already-validated question and answer key instead of asking the model
to generate a new one from scratch, cutting cost and response latency
with no visible difference to the learner.

**Why this priority**: Question generation is the system's highest
LLM-call-volume surface -- every placement flow, "next question"
selection, and quiz session routes through it -- so this is where
caching saves the most.

**Independent Test**: Seed the system with a topic/difficulty
combination, trigger two next-question requests for that same
combination close together (e.g., for two different learners), and
confirm the second request returns without a new model call, serving a
question that already passed the same content-artifact validation as
the first.

**Acceptance Scenarios**:

1. **Given** no cached entry exists for a (topic, difficulty,
   content-artifact version, generation prompt version) combination,
   **When** a learner is served a next question for that combination,
   **Then** the platform calls the model, validates the result, serves
   it, and stores it as a cache entry tagged with the current
   content-artifact version and prompt version.
2. **Given** a cache entry exists for a (topic, difficulty,
   content-artifact version, generation prompt version) combination,
   **When** a different learner is served a next question for the same
   combination, **Then** the platform serves the cached question and
   answer key without invoking the model again.
3. **Given** a cache entry exists for a topic/difficulty combination,
   **When** the active generation prompt version is bumped, **Then**
   the next request for that combination is treated as a cache miss and
   triggers a fresh model call -- the pre-bump entry is never served.
4. **Given** a cache entry exists for a topic/difficulty combination,
   **When** the subject's content-artifact version is bumped, **Then**
   the next request for that combination is treated as a cache miss --
   the pre-bump entry is never served.
5. **Given** the cache pool for a (topic, difficulty, content-artifact
   version, generation prompt version) combination already holds 5
   variants, **When** a new request for that combination misses the
   pool (e.g., all 5 entries have expired past their 24-hour freshness
   window), **Then** the platform generates a fresh variant and adds it
   to the pool, evicting the oldest entry if the pool would otherwise
   exceed 5.

---

### User Story 2 - Serve Semantically Similar Free-Text Grading Requests From Cache (Priority: P2)

When a learner submits a free-text answer that is semantically
equivalent -- not necessarily word-for-word identical -- to an answer
already graded for the same question, the platform reuses the
previously computed grade and rubric-criteria breakdown instead of
invoking the Grading Agent's model call again.

**Why this priority**: Grading is the system's second-highest-volume
LLM surface (every free-text answer, Milestone 6), and the roadmap
names it explicitly as a caching target; sequenced after question
generation because generation has higher aggregate call volume.

**Independent Test**: Submit two different learners' free-text answers
to the same question, worded differently but meaning the same thing,
and confirm the second submission's grade and rubric breakdown are
served without a new Grading Agent call, matching what a fresh grading
call would have produced.

**Acceptance Scenarios**:

1. **Given** no cached grade exists for a semantically equivalent
   answer to a question under the current grading prompt version,
   **When** a learner submits a free-text answer, **Then** the platform
   calls the Grading Agent, then stores the result as a cache entry
   tagged with the question, a semantic signature of the answer, and
   the current grading prompt version.
2. **Given** a cache entry exists for a semantically equivalent answer
   to a question under the current grading prompt version, **When** a
   different learner submits a differently-worded but semantically
   equivalent answer to that same question, **Then** the platform
   serves the cached grade and rubric breakdown without invoking the
   Grading Agent's model call again, and never exposes the original
   learner's answer text to the new learner.
3. **Given** a cache entry exists for an answer to question Q1,
   **When** a learner submits a similar-sounding answer to a different
   question Q2, **Then** the platform does not serve Q1's cached grade
   -- it treats the request as a cache miss.
4. **Given** a cache entry exists for a graded answer, **When** the
   grading prompt version is bumped, **Then** the next
   semantically-equivalent submission is treated as a cache miss and
   triggers a fresh Grading Agent call.

---

### User Story 3 - Measure Cache Hit Rate to Verify the Caching Investment Pays Off (Priority: P3)

A maintainer can see, for a given time period, what fraction of
cache-eligible question-generation and grading requests were served
from cache versus triggered a fresh model call, so the caching layer's
cost/latency benefit can be verified rather than assumed.

**Why this priority**: Necessary to demonstrate this milestone's own
Definition of Done (a measured hit-rate target), but delivers no
end-learner-facing value on its own -- it's an observability layer on
top of Stories 1 and 2, not a prerequisite for them.

**Independent Test**: Run the synthetic load test referenced in this
milestone's Definition of Done and confirm a hit-rate figure is
produced that matches manually-counted hits/misses from the same run.

**Acceptance Scenarios**:

1. **Given** a mix of cache-eligible requests during a test run,
   **When** the run completes, **Then** a hit-rate metric (hits / total
   cache-eligible requests) is available, broken out by cache type
   (question-generation vs. grading).
2. **Given** a cache-storage failure occurs, **When** a cache-eligible
   request is made, **Then** the request still succeeds via a direct
   model call (fail open, per FR-008), and this is recorded as a miss
   with a distinguishable reason, not silently uncounted.

---

### Edge Cases

- What happens when two near-simultaneous requests both miss the cache
  for the same (topic, difficulty) combination? Both are allowed to
  independently call the model and store their own cache entries -- no
  locking/coordination is required, since a missed dedup opportunity
  costs one extra model call, not a correctness failure.
- What happens when a cache-storage read or write fails (e.g., a
  transient database error)? The request must fail open to a direct
  model call rather than surfacing an error to the learner (FR-008).
- What happens when a learner's free-text answer is grammatically close
  to a cached answer but differs in meaning (e.g., negation:
  "photosynthesis does not require light" vs. "photosynthesis requires
  light")? The semantic-similarity match must not conflate them
  (FR-002/FR-003), verified against the same ground-truth grading eval
  set Milestone 6 already established.
- What happens to Milestone 1's per-learner near-duplicate exclusion
  (its FR-008) when a question is served from a cross-learner cache? It
  continues to run unchanged and independently -- a cached question is
  still excluded from a specific learner's next-question selection if
  they've seen it in their own recent-history window (FR-010).
- What happens to the Tutor Agent's responses? They are explicitly out
  of scope for this milestone -- see Assumptions.
- What happens to FR-013's audit-log requirement on the in-quiz
  question-generation path, which (even for a fresh call, today) has
  no dedicated decision-event of its own? It's held to that same
  pre-existing standard -- the per-learner generated-question record
  it already persists, plus its own Langfuse trace on a hit -- rather
  than requiring a new audit-log mechanism this milestone would
  otherwise be inventing solely for caching's sake (FR-013).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST cache validated Assessment-Generation output
  (question + answer key), keyed on the exact (topic, difficulty,
  content-artifact version, generation prompt version) combination, and
  serve a matching cache entry instead of invoking the model for a
  subsequent request with the same key.
- **FR-002**: System MUST cache Grading Agent output (grade +
  rubric-criteria breakdown), keyed on the specific question plus a
  semantic-similarity signature of the learner's free-text answer and
  the current grading prompt version, and serve a matching cache entry
  instead of invoking the Grading Agent's model call for a subsequent
  semantically-equivalent submission.
- **FR-003**: Grading-cache matching MUST use meaning-based (e.g.,
  embedding) similarity, not exact string matching, so a
  differently-worded but semantically equivalent answer can still
  produce a cache hit.
- **FR-004**: Grading-cache matching MUST be scoped to the same
  question -- an answer signature MUST NOT be matched against cache
  entries created for a different question, even if the answer text is
  superficially similar.
- **FR-005**: Every cache entry MUST be tagged with the exact prompt
  version, and (for question-generation entries) the content-artifact
  version, active when it was created.
- **FR-006**: System MUST treat a cache entry whose tagged prompt
  version or content-artifact version no longer matches the current
  version as a miss and MUST NOT serve it -- this MUST trigger a fresh
  model call instead.
- **FR-007**: A cache hit and a cache miss for a logically equivalent
  request MUST produce identical served content (question text, answer
  key, grade, rubric breakdown) -- differing only in response latency
  and whether a new model call occurred.
- **FR-008**: System MUST NOT let a cache-storage read or write failure
  block, materially delay, or degrade a generation or grading request
  -- such failures MUST fail open to a direct model call.
- **FR-009**: A grading cache hit MUST NOT expose the free-text answer
  content of the learner whose submission originally created the cache
  entry to any other learner -- only the computed grade and rubric
  breakdown are served.
- **FR-010**: Caching MUST NOT alter or bypass Milestone 1's per-learner
  near-duplicate exclusion (that spec's FR-008) -- a cross-learner cache
  hit can still be excluded from a specific learner's next-question
  selection under that existing rule.
- **FR-011**: System MUST record, per cache-eligible request, whether it
  was served from cache or triggered a fresh model call, in a form that
  can be aggregated into a hit-rate metric broken out by cache type
  (question-generation vs. grading).
- **FR-012**: System MUST retain, per (topic, difficulty,
  content-artifact version, generation prompt version) combination, a
  rotating pool of up to 5 cached question variants, each served on a
  round-robin or random basis on a cache hit, and each expiring after a
  24-hour freshness window independent of any version bump -- so
  learners aren't shown the identical question indefinitely between
  version changes, while still capturing most of the cost/latency
  benefit of reuse.
- **FR-013**: A cache hit MUST produce its own full pedagogical
  audit-log entry and its own new Langfuse trace, exactly as a fresh
  model call would, so "why was I shown this" / "why was this marked
  wrong" and per-invocation observability both remain answerable for
  every individual learner and request, per Constitution Principle V --
  a cache hit is never logged or traced any less completely than a
  fresh model call. "Its own full pedagogical audit-log entry" means:
  wherever a fresh call on that same code path already produces a
  dedicated decision-record (e.g. the `NEXT_TOPIC_SELECTED` /
  `ANSWER_SUBMITTED` audit-log events), a cache hit produces the
  identical record, just flagged as cache-served. Where a path has no
  such dedicated event even for a fresh call (the in-quiz
  question-generation path, which persists its own per-learner
  `GeneratedQuestion` row -- stem, answer key, prompt version, quiz
  session -- as its existing traceability mechanism, with no separate
  decision-event of its own), a cache hit is held to that same
  pre-existing standard: the identical per-learner row, populated
  identically regardless of hit or miss, plus its own Langfuse trace.
  This requirement does not create a new audit-log mechanism for a path
  that never had one.

### Key Entities *(include if feature involves data)*

- **Cache Entry**: A stored, previously-validated model response --
  either a generated question + answer key, or a computed grade +
  rubric breakdown -- tagged with its cache type, its lookup key
  (topic + difficulty for generation; question + answer signature for
  grading), the prompt version and (for generation) content-artifact
  version it was created under, its creation time, and how many times
  it has been served. Question-generation entries additionally belong
  to a rotating pool of up to 5 variants per lookup key, each expiring
  24 hours after creation (FR-012).
- **Cache Hit/Miss Outcome**: Not a separate stored record -- two
  additional fields (hit/miss, and if a miss, a reason: no matching
  entry, version-invalidated, or storage failure) recorded on the
  *same* full pedagogical audit-log entry FR-013 already requires for
  that request. User Story 3's hit-rate metric is computed by
  aggregating this outcome across existing audit-log entries, not by
  reading a second, independent log.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a synthetic load test replaying a realistic mix of
  repeated/near-duplicate question-generation and grading traffic, each
  cache type independently reaches at least 30% of its own
  cache-eligible requests served from cache without a new model call --
  question-generation and grading are measured and must each pass
  separately, not as one blended figure.
- **SC-002**: Model call volume (and associated cost) for cache-eligible
  traffic is measurably reduced compared to an identical load-test run
  with caching disabled.
- **SC-003**: No learner or instructor can distinguish, from the content
  or correctness of a served question, answer key, or grade, whether it
  came from a cache hit or a fresh model call.
- **SC-004**: 100% of cache entries tagged with a since-superseded
  prompt version or content-artifact version are verified unreachable
  after that version change takes effect.
- **SC-005**: Milestones 1-12's full acceptance-scenario suites still
  pass with caching enabled (regression check).

## Assumptions

- Caching in this milestone applies only to the Assessment-Generation
  Agent's question-generation calls and the Grading Agent's free-text
  grading calls -- the two highest-volume, already-eval-gated agents
  per Milestone 12's own scoping precedent. The Recommendation Agent is
  out of scope: roadmap's Milestone 13 scope doesn't name it as a
  caching target, its call pattern is a per-learner report rather than
  naturally near-duplicate across learners, and it doesn't yet carry a
  Milestone-12-style versioned prompt constant, so version-based cache
  invalidation would have nothing to key on.
- The Tutor Agent is out of scope for this milestone. Its core design
  commitment (Milestone 9) is token-by-token streaming; caching a full
  response would require either replaying a synthetic stream from a
  stored complete response or bypassing streaming outright, either of
  which changes a property of that agent's response generation this
  milestone doesn't intend to touch.
- Caching applies to the underlying generation/grading call only, not
  to what's ultimately shown to a specific learner -- Milestone 1's
  per-learner near-duplicate exclusion continues to run independently
  on top of any cache hit or miss, matching roadmap's explicit
  "Explicitly not included" note for this milestone.
- The cache storage mechanism itself (in-database via Postgres,
  Postgres + pgvector for embedding similarity, or a dedicated cache
  service) is left to `/speckit-plan`, per `tech-stack.md`'s "Explicitly
  not yet decided" section -- this spec describes required behavior,
  not the storage technology.
- A cache-hit-rate target of at least 30%, measured independently per
  cache type (SC-001), is a reasonable first-pass default given no real
  production call-volume data yet exists; revisit once this milestone's
  synthetic load test or real usage data provides a better baseline.
- Grading cache entries don't require a hard row-count/storage cap in
  this milestone -- prompt-version bumps are the only specified
  invalidation trigger for them (FR-006); a maintenance/eviction policy
  can be added later if storage growth becomes a problem in practice.
- Question-generation caching uses a rotating pool of 5 variants per
  (topic, difficulty, content-artifact version, generation prompt
  version) combination with a 24-hour freshness window (FR-012) --
  chosen by user decision during spec review to balance cost savings
  against content variety. The pool size of 5 deliberately mirrors
  Milestone 1's own per-learner near-duplicate window (its FR-008's
  "last 5 generated questions"), so a learner's recent-history exclusion
  can plausibly draw from a full, non-repetitive pool rather than being
  starved down to one option.

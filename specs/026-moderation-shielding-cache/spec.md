# Feature Specification: Moderation & Shielding Classification Caching

**Feature Branch**: `036-moderation-shielding-cache`

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: "moderation caching and other caching mentioned in chat earlier" -- the pre-grading moderation guardrail (spec 007 FR-012) and the Tutor Agent's answer-shielding match classifier (spec 016) were identified as the two remaining high-call-volume, non-cached model calls, following the same shape spec 015 (Semantic Caching) already established for question generation and grading.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Serve Repeated Moderation Checks From Cache (Priority: P1)

When a learner submits free-text or stepwise answer text that has already been classified by the moderation guardrail before -- whether from the same learner resubmitting, or a different learner submitting the same common blank/short/wrong answer -- the platform reuses the stored allow/block verdict instead of invoking the moderation model again.

**Why this priority**: `check_moderation` runs on every free-text and stepwise answer submission (spec 007 FR-012) -- one of the highest-call-volume guardrail checks in the system -- and real classroom traffic skews heavily toward a small set of repeated low-effort answers ("idk", blank, single-word guesses), making this the single highest-value caching target left after spec 015.

**Independent Test**: Submit the same exact answer text twice (from the same or different learners), and confirm the second submission's allow/block verdict is served without a new moderation model call, while the grading/answer flow behaves identically to an uncached verdict.

**Acceptance Scenarios**:

1. **Given** no cached verdict exists for a given normalized answer text under the current moderation instruction version, **When** a learner submits that text, **Then** the platform calls the moderation model, then stores the resulting verdict as a cache entry keyed on a signature of the normalized text and the current instruction version.
2. **Given** a cache entry exists for a normalized answer text under the current moderation instruction version, **When** any learner (the same or a different one) submits text that normalizes to the same signature, **Then** the platform serves the cached verdict without invoking the moderation model again, and the grading/rejection flow proceeds exactly as it would for a fresh identical verdict.
3. **Given** a cache entry exists for a normalized answer text, **When** the moderation instruction version is bumped, **Then** the next submission of that same text is treated as a cache miss and triggers a fresh moderation call -- the pre-bump verdict is never served.
4. **Given** two different answer texts that are merely similar but not identical after normalization, **When** each is submitted, **Then** each is classified independently -- the cache MUST NOT treat near-identical-but-distinct text as a match (exact-signature matching only, not semantic similarity).

---

### User Story 2 - Serve Repeated Shielding-Match Checks From Cache (Priority: P2)

When the Tutor Agent's answer-shielding check evaluates whether a learner's tutoring-chat message is asking for the answer to a specific open question, and that exact (open question, learner message) pairing has already been classified before, the platform reuses the stored match/no-match verdict instead of invoking the classifier model again.

**Why this priority**: `determine_shielding` calls its match classifier once per open question (up to 10 per tutor message, spec 016's `MAX_OPEN_QUESTIONS`), so a single tutor message can already trigger multiple model calls; sequenced after moderation because its cross-learner hit potential is lower (tutoring messages are freer-form than answer submissions) even though its per-message call multiplier is higher.

**Independent Test**: Send the same tutoring-chat message against the same open question twice (e.g., a learner re-asking, or the classifier being invoked again for an unrelated reason), and confirm the second check's match/no-match result is served without a new classifier model call.

**Acceptance Scenarios**:

1. **Given** no cached verdict exists for a given (open question stem, tutor message) pairing under the current shielding-classification instruction version, **When** the shielding check runs for that pairing, **Then** the platform calls the classifier model, then stores the resulting verdict as a cache entry keyed on a signature of both normalized texts and the current instruction version.
2. **Given** a cache entry exists for a (open question stem, tutor message) pairing under the current instruction version, **When** the shielding check runs again for that exact pairing, **Then** the platform serves the cached verdict without invoking the classifier model again, and `determine_shielding`'s downstream match/inconclusive/no-match handling behaves identically to an uncached result.
3. **Given** a cache entry exists for a pairing of question Q1's stem and message M, **When** the same message M is checked against a different open question Q2's stem, **Then** the platform does not serve Q1's cached verdict -- it treats the request as a cache miss (scoped per question, mirroring spec 015 FR-004's grading-cache scoping).
4. **Given** a cache entry exists for a pairing, **When** the shielding-classification instruction version is bumped, **Then** the next check of that same pairing is treated as a cache miss and triggers a fresh classifier call.

---

### User Story 3 - Measure Cache Hit Rate for Both New Cache Types (Priority: P3)

A maintainer can see, for a given time period, what fraction of cache-eligible moderation and shielding-classification checks were served from cache versus triggered a fresh model call, so the caching investment's cost/latency benefit can be verified rather than assumed.

**Why this priority**: Mirrors spec 015 User Story 3's own precedent for the first two cache types -- necessary to confirm this feature's Success Criteria are actually met in practice, but delivers no end-learner-facing value on its own.

**Independent Test**: Run a synthetic load test replaying a realistic mix of repeated/duplicate moderation and shielding traffic, and confirm a hit-rate figure is produced for each cache type that matches manually-counted hits/misses from the same run.

**Acceptance Scenarios**:

1. **Given** a mix of cache-eligible requests during a test run, **When** the run completes, **Then** a hit-rate metric (hits / total cache-eligible requests) is available for each cache type independently (moderation, shielding).
2. **Given** a cache-storage failure occurs, **When** a cache-eligible moderation or shielding check is made, **Then** the check still succeeds via a direct model call (fail open, per FR-006), and this is recorded as a miss with a distinguishable reason, not silently uncounted.

---

### Edge Cases

- What happens when a cache-storage read or write fails (e.g., a transient database error)? The check must fail open to a direct model call rather than surfacing an error, or -- worse -- silently defaulting to an unsafe verdict (FR-006).
- What happens when two near-simultaneous requests both miss the cache for the same signature? Both are allowed to independently call the model and store their own cache entries -- no locking/coordination required, since a missed dedup opportunity costs one extra model call, not a correctness failure (mirrors spec 015's identical edge case).
- What happens to a moderation verdict cached before a learner later reports the text as inappropriate through some other channel (e.g., a manual flag)? Out of scope -- this cache only ever serves the moderation classifier's own prior verdict for identical text; it has no relationship to, and does not suppress, any separate human-review/flagging pathway.
- What happens if the exact same tutor message text is asked about two different open questions in the same conversation? Each (question, message) pairing is classified and cached independently (User Story 2, Acceptance Scenario 3) -- no cross-question reuse.
- What happens to the shielding classifier's existing fail-safe (spec 016 FR-010: any exception defaults to shielding)? Unchanged -- a cache-storage failure triggers the same fresh-call path as an uncached request, and if the fresh call itself then fails, FR-010's existing default-to-shielded behavior still applies exactly as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST cache the moderation guardrail's allow/block verdict, keyed on a signature of the normalized submitted text and the current moderation instruction version, and serve a matching cache entry instead of invoking the moderation model for a subsequent submission whose normalized text produces the same signature.
- **FR-002**: System MUST cache the Tutor Agent's shielding-match verdict, keyed on a signature of the normalized (open question stem, tutor message) pairing and the current shielding-classification instruction version, and serve a matching cache entry instead of invoking the classifier model for a subsequent check of the same pairing.
- **FR-003**: Both caches MUST match on an exact signature of normalized text (e.g., trimmed/case-folded, hashed) only -- not semantic/embedding similarity. Unlike spec 015's grading cache, these are safety- and answer-leakage-relevant boolean classifications with no equivalence check to fall back on if a near-duplicate match were wrong, so approximate matching is deliberately excluded (see Assumptions).
- **FR-004**: Shielding-cache matching MUST be scoped to the same open question -- a (open question, tutor message) signature MUST NOT be matched against a cache entry created for a different open question, even if the tutor message text is identical.
- **FR-005**: Every cache entry MUST be tagged with the exact instruction version (moderation or shielding-classification, respectively) active when it was created. A cache entry whose tagged instruction version no longer matches the current version MUST be treated as a miss and MUST NOT be served -- this MUST trigger a fresh model call instead.
- **FR-006**: System MUST NOT let a cache-storage read or write failure block, materially delay, or degrade a moderation or shielding check, and MUST NOT let such a failure cause an unsafe default (e.g., silently allowing text that was never actually classified) -- such failures MUST fail open to a direct model call, preserving each check's own existing fail-safe behavior (moderation's fail-closed-on-no-response; shielding's default-to-shielded).
- **FR-007**: A cache hit and a cache miss for the same underlying (text, or question+text) pairing MUST produce an identical served verdict -- differing only in response latency and whether a new model call occurred.
- **FR-008**: Cache entries for both cache types MUST store only a non-reversible signature (e.g., a hash) of the normalized input text, never the raw submitted answer text or raw tutor message text itself, so this caching layer introduces no new store of learner-identifiable free-text content beyond what already exists in the assessment/tutoring records these checks gate.
- **FR-009**: System MUST record, per cache-eligible moderation and shielding check, whether it was served from cache or triggered a fresh model call, in a form that can be aggregated into a hit-rate metric broken out by cache type.
- **FR-010**: A cache hit MUST NOT reduce the observability already produced for a fresh moderation or shielding check along the same code path -- wherever a fresh call already contributes to an existing Langfuse trace or audit-log record for the request it gates (e.g., the answer-submission or tutor-exchange record), a cache hit produces the same, just flagged as cache-served, per Constitution Principle V. This does not create a new dedicated audit-log event for either check where none exists today.

### Key Entities *(include if feature involves data)*

- **Moderation Cache Entry**: A stored allow/block verdict, keyed on a signature of the normalized submitted text and the moderation instruction version it was classified under, plus creation time and hit count. Contains no raw submitted text.
- **Shielding Classification Cache Entry**: A stored match/no-match verdict, keyed on a signature of the normalized (open question stem, tutor message) pairing and the shielding-classification instruction version it was classified under, plus creation time and hit count. Contains no raw open-question or tutor-message text.
- **Cache Hit/Miss Outcome**: Not a separate stored record -- fields recorded alongside whatever existing record or trace already covers the request each check gates (mirrors spec 015's identical design), so User Story 3's hit-rate metric is computed by aggregating this outcome rather than reading a new independent log.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a synthetic load test replaying a realistic mix of repeated/duplicate answer-submission and tutoring-chat traffic, each cache type independently reaches at least 30% of its own cache-eligible requests served from cache without a new model call -- moderation and shielding are measured and must each pass separately, not as one blended figure.
- **SC-002**: Model call volume (and associated cost) for cache-eligible moderation and shielding traffic is measurably reduced compared to an identical load-test run with caching disabled.
- **SC-003**: No learner can distinguish, from the behavior of the answer-submission or tutoring-chat flow, whether a given moderation or shielding determination came from a cache hit or a fresh model call.
- **SC-004**: 100% of cache entries tagged with a since-superseded instruction version are verified unreachable after that version change takes effect.
- **SC-005**: Spec 007's (moderation) and spec 016's (shielding) full acceptance-scenario suites still pass with caching enabled (regression check).

## Assumptions

- Scope is limited to the two caching targets identified as the remaining high-call-volume, non-cached model calls: the moderation guardrail (spec 007) and the Tutor Agent's shielding-match classifier (spec 016). The misconception-classifier's per-answer baseline call, also discussed as a candidate for call-volume reduction, is excluded -- that call's concern is unbatched per-answer invocation (a structural/batching fix), not a repeated-input caching opportunity, and is already tracked as a separate follow-up (Milestone 11 status notes).
- Exact-signature (hashed, normalized-text) matching is used for both cache types, not semantic/embedding similarity. This deliberately diverges from spec 015's grading cache, which added an LLM-based equivalence check specifically to make semantic matching safe (spec 015 FR-003). Moderation and shielding verdicts are safety-and-answer-leakage-relevant booleans classified from short, low-context inputs where a false-positive near-duplicate match carries higher risk relative to the caching benefit than for grading's richer free-text answers; exact matching has zero drift risk and still captures the dominant real-world pattern (identical repeated blank/short/common answers, and repeated identical tutoring-chat phrasing).
- Neither cache stores the raw submitted text -- only a non-reversible signature -- because moderation/shielding inputs are exactly the kind of free-text learner content Milestone 7's privacy/retention spec governs, and a hash-only design (mirroring spec 015 FR-009's "never store the original answer text" precedent for the grading cache) avoids introducing a new place that content is retained, with no deletion-cascade linkage required since no learner-identifiable content is stored.
- No hard storage cap or freshness-window eviction is specified for either cache in this milestone -- unlike spec 015's question-generation pool (which needed eviction for content *variety*, not correctness), a moderation or shielding verdict for a given exact signature never goes stale except via an explicit instruction-version bump (FR-005), so unbounded retention of hash-keyed rows is not a correctness concern. A maintenance/eviction policy can be added later if storage growth becomes a problem in practice, mirroring spec 015's identical deferral for its grading cache.
- A cache-hit-rate target of at least 30% per cache type (SC-001) reuses spec 015's own precedent value, given no real production call-volume data yet exists for either check; revisit once a synthetic load test or real usage data provides a better baseline.
- The cache storage mechanism itself (in-database via Postgres, or otherwise) is left to `/speckit-plan`, per `tech-stack.md`'s existing pattern for spec 015 -- this spec describes required behavior, not storage technology.

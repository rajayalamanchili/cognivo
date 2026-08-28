---

description: "Task list for Tutor Agent (Milestone 9)"
---

# Tasks: Tutor Agent -- Conversational Delegation, Vector-Grounded Retrieval, and Streaming Responses

**Input**: Design documents from `/specs/012-tutor-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present)

**Tests**: Included -- matches this project's established convention (every prior milestone's tasks.md includes contract/integration/unit tests per user story, e.g. spec 007/010/011).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3) to enable independent implementation and testing of each.

**Revision note (2026-08-23)**: Revised after `/speckit-analyze` found five issues in the original 36-task version. This version (38 tasks) fixes all of them: T006/T009 gained `failed_at` (H2); the original single T021 is now T021+T022 (H2 completion-vs-failure split, also resolving M2's task-granularity finding); T029/T030 gained explicit `delegation_context` structuring (M1); T036 is new (H1, SC-002's missing test-question fixture). C1 (the privacy/retention data-classification gap) was fixed directly in `specs/009-privacy-retention/data-classification.md` and `roadmap.md`'s new "Known gap" section, not via a task here -- see those files.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths: `backend/`, `frontend/` (existing projects); `tutor-agent/` (new, mirrors `grading-agent/`'s layout)

---

## Phase 1: Setup

**Purpose**: New `tutor-agent/` project scaffold and backend dependency/config additions.

- [X] T001 Create `tutor-agent/` project scaffold (`pyproject.toml`, `vercel.json`, `src/__init__.py`, `tests/`) mirroring `grading-agent/`'s layout exactly (plan.md Project Structure; dependencies: `a2a-sdk[http-server]`, `google-adk`, `langfuse`, `litellm`, `openinference-instrumentation-google-adk`, `uvicorn[standard]`)
- [X] T002 [P] Add `pgvector` to `backend/pyproject.toml` dependencies
- [X] T003 [P] Add new env vars to `backend/.env.example`: `TUTOR_EMBEDDING_MODEL`, `VOYAGE_API_KEY`, `TUTOR_AGENT_URL`, `TUTOR_AGENT_SHARED_SECRET`, `TUTOR_AGENT_SHARED_SECRET_NEXT`, `TUTOR_AGENT_VERCEL_BYPASS_SECRET` (research.md §1, §7)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data layer, the standalone `tutor-agent/` A2A service, and the backend's A2A client -- all three user stories depend on this being in place.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Create `ContentPassageEmbedding` model in `backend/src/models/content_passage_embedding.py` (data-model.md)
- [X] T005 [P] Create `TutoringSession` model in `backend/src/models/tutoring_session.py` (data-model.md)
- [X] T006 [P] Create `TutorExchange` model in `backend/src/models/tutor_exchange.py`, including the nullable `failed_at` column (data-model.md, `/speckit-analyze` finding H2)
- [X] T007 Register the three new models in `backend/src/models/__init__.py` (depends on T004-T006)
- [X] T008 Add `TUTOR_EXCHANGE_COMPLETED = "tutor_exchange_completed"` to `AssessmentEventType` in `backend/src/models/enums.py` (data-model.md)
- [X] T009 Alembic migration in `backend/alembic/versions/<hash>_tutor_agent.py`: enable the `pgvector` extension; create `content_passage_embeddings`, `tutoring_sessions` (with the partial unique index `(learner_id, subject_id) WHERE status = 'active'`, FR-014), and `tutor_exchanges` (including `failed_at`, finding H2) tables; add the new `AssessmentEventType` enum value (depends on T004-T008)
- [X] T010 Extend `backend/src/services/content_artifact/loader.py`'s load pipeline to generate/upsert `ContentPassageEmbedding` rows (one per topic's `skill_definition.summary` and each `difficulty_calibration` entry) via `litellm.embedding()` against Voyage `voyage-3`, deleting rows for a superseded `content_version` (research.md §5, data-model.md) (depends on T004, T009)
- [X] T011 Implement the `pgvector` cosine-similarity query in `backend/src/services/retrieval/passage_search.py`, scoped to a given `subject_id` (research.md §2/§5) (depends on T004, T009)
- [X] T012 Implement `tutor-agent/src/agent.py`: an ADK `LlmAgent` wrapped by `to_a2a()`, with `_to_a2a_kwargs` deriving `host`/`protocol`/`port=443` from `VERCEL_BRANCH_URL`/`VERCEL_URL` (mirrors `grading-agent/src/agent.py`, research.md §7) (depends on T001)
- [X] T013 [P] Implement `tutor-agent/src/guardrails.py`: `X-Tutor-Agent-Secret` shared-secret auth middleware plus the compensating length-cap/moderation checks (FR-010/FR-011, mirrors `grading-agent/src/guardrails.py`) (depends on T001)
- [X] T014 [P] Implement `tutor-agent/src/tracing.py`: Langfuse/OpenInference ADK instrumentation with an explicit flush before the function returns (FR-008, mirrors `grading-agent/src/tracing.py`) (depends on T001)
- [X] T015 Implement `backend/src/services/tutor_agent_client/client.py`: an A2A streaming client that calls `tutor-agent/`'s `message/stream`, sends `X-Tutor-Agent-Secret`, and retries once on failure (mirrors `services/grading_client/client.py`) (depends on T012)

**Checkpoint**: Data layer, `tutor-agent/` service, and the backend's client for it all exist -- user story implementation can now begin.

---

## Phase 3: User Story 1 - Ask the Tutor a plain-English question (Priority: P1) 🎯 MVP

**Goal**: A learner opens a Tutoring Session, asks a question, and receives a `pgvector`-grounded, token-by-token streamed answer -- with the rate-limit, session-uniqueness, and in-flight-concurrency guardrails (FR-013/014/015) all enforced, including a clean recovery path when a stream fails mid-answer (finding H2).

**Independent Test**: Submit a single question against a seeded subject's content artifact; verify the answer streams incrementally and grounds in retrieved passages from that subject's actual content (spec.md US1).

### Tests for User Story 1

- [X] T016 [P] [US1] Integration test for `POST /api/tutor/sessions` (create, and get-or-create per FR-014) in `backend/tests/integration/test_tutor_sessions.py`
- [X] T017 [P] [US1] Integration test for `POST /api/tutor/sessions/{id}/messages` covering the streamed-grounded case, the honest-non-grounded case, the `409`/`429`/`422`/`503` rejection paths, and a session recovering after a `failed_at` exchange (finding H2) in `backend/tests/integration/test_tutor_messages.py`
- [X] T018 [P] [US1] Unit test for `passage_search.py`'s similarity ranking in `backend/tests/unit/test_passage_search.py`

### Implementation for User Story 1

- [X] T019 [P] [US1] Implement `check_tutor_rate_limit` in `backend/src/services/tutor/rate_limit.py`, mirroring `services/grading_client/guardrails.py`'s `check_rate_limit` exactly (FR-013, research.md §8)
- [X] T020 [US1] Implement session get-or-create (`open_session`) in `backend/src/services/tutor/session.py` against the partial unique index (FR-014) (depends on T005, T009)
- [X] T021 [US1] Implement request assembly and the streamed call in `submit_message` (`backend/src/services/tutor/session.py`): in-flight check (FR-015) -> rate limit (T019) -> length/moderation -> `passage_search` (T011) -> bundle context -> call `tutor_agent_client` (T015) -> proxy the stream to the caller (FR-002/FR-005/FR-012) (depends on T006, T011, T015, T019, T020)
- [X] T022 [US1] Implement `submit_message`'s completion handling (`backend/src/services/tutor/session.py`): on stream success, persist the `TutorExchange` row (`answer_text`, `grounded`, `retrieved_passage_ids`, `delegation_context`), write the `tutor_exchange_completed` audit event, and flush the Langfuse span; on stream failure/timeout, set `failed_at` instead of leaving `answer_text` ambiguously `NULL` (FR-003/FR-004/FR-007/FR-008, closes finding H2) (depends on T021)
- [X] T023 [US1] Implement `POST /api/tutor/sessions` and `POST /api/tutor/sessions/{session_id}/messages` in `backend/src/api/routes/tutor.py`, guardian-mediated + demo-learner auth (FR-001) (depends on T020, T022)
- [X] T024 [US1] Register the `tutor` router in `backend/src/api/main.py` (depends on T023)
- [X] T025 [P] [US1] Implement the tutoring chat page `frontend/src/app/tutor/page.tsx` and streaming chat component `frontend/src/components/TutorChat.tsx`
- [X] T026 [P] [US1] Add a streaming-fetch helper for `/api/tutor/...` to `frontend/src/services/api.ts`
- [X] T027 [P] [US1] Unit tests for `TutorChat.tsx` in `frontend/tests/unit/tutor-chat.test.tsx`

**Checkpoint**: User Story 1 is fully functional and independently testable (quickstart scenarios 1, 2, 5, 6).

---

## Phase 4: User Story 2 - Tutor answers grounded in the learner's actual state (Priority: P2)

**Goal**: When a question depends on the learner's own performance, the answer reflects their real mastery/weak-area state, obtained from the existing deterministic model -- never guessed.

**Independent Test**: Ask a learner with a known "struggling" topic what to work on; verify the answer names that actual topic. Repeat with a brand-new learner; verify an honest "not enough data" response (spec.md US2).

### Tests for User Story 2

- [X] T028 [P] [US2] Integration test for a performance-dependent question (known weak area) and a brand-new learner's honest no-data response in `backend/tests/integration/test_tutor_delegation_context.py`

### Implementation for User Story 2

- [X] T029 [US2] Extend `submit_message` (`backend/src/services/tutor/session.py`) with an in-process call to the existing Recommendation/Sequencing services when the question needs performance context, appending a `{agent, request, response}` record to `delegation_context` per call (FR-006, structured shape per finding M1) (depends on T022)
- [X] T030 [US2] Extend `tutor-agent/src/agent.py`'s prompt/tool wiring so the bundled `delegation_context` entries are used verbatim in the answer rather than re-derived (depends on T012)

**Checkpoint**: User Stories 1 and 2 both work independently (quickstart scenario 3).

---

## Phase 5: User Story 3 - Inspect why the Tutor said what it said (Priority: P3)

**Goal**: An instructor or engineer can reconstruct, for a specific past exchange, which passages were retrieved and which delegated-agent calls (with their actual inputs and outputs) fed the answer -- without asking the Tutor Agent to explain itself.

**Independent Test**: Pick a past tutoring exchange and confirm an inspector can retrieve its retrieved passages and per-call delegation context via `GET /api/tutor/exchanges/{id}` (spec.md US3).

### Tests for User Story 3

- [X] T031 [P] [US3] Integration test for `GET /api/tutor/exchanges/{exchange_id}` auth (owning guardian, enrolled instructor, demo-instructor), the derived `status` field (`completed`/`failed`/`in_progress`), and the structured `delegation_context` payload shape in `backend/tests/integration/test_tutor_exchange_inspection.py`

### Implementation for User Story 3

- [X] T032 [US3] Implement `GET /api/tutor/exchanges/{exchange_id}` in `backend/src/api/routes/tutor.py`, enrollment-scoped auth mirroring `content_review`'s existing pattern, deriving `status` from `answer_text`/`failed_at` (depends on T022, T024)

**Checkpoint**: All three user stories are independently functional (quickstart scenario 4).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation across all three stories, regression, and the milestone's own Success Criteria.

- [ ] T033 [P] Playwright E2E `frontend/tests/e2e/tutor-round-trip.spec.ts`: open a session, ask a question, confirm a grounded streamed answer, then inspect the exchange as the instructor (quickstart scenarios 1-4) -- **spec written, lint/format/`tsc --noEmit` all clean, NOT yet run against a live stack** (needs backend + `tutor-agent/` + a migrated DB + real `ANTHROPIC_API_KEY`/`VOYAGE_API_KEY` all running together locally -- real API spend, not attempted without checking first). Along the way, found and fixed a real gap this spec's own "inspect the exchange" step depends on: nothing in the SSE stream or the frontend DOM ever exposed an exchange's id, so `GET /api/tutor/exchanges/{id}` was undiscoverable from any real client -- added `exchange_id` to the stream's final `done` event (contracts/api.md, `services/tutor/session.py`) and a `data-exchange-id` attribute on `TutorChat.tsx`'s tutor message bubble.
- [X] T034 Run the full backend suite against a real, freshly migrated dev database; confirm SC-005 (Milestones 1-8 unmodified) and record the result in `roadmap.md`'s Milestone 9 status, following the precedent set by Milestones 7/8's own DoD confirmation
- [X] T035 [P] Run `check_no_subject_conditionals.py` against the new retrieval/loader code (Constitution Principle III gate)
- [X] T036 [P] Author a defined grounding test-question set (>=20 questions across both subjects, each with its expected topic/passage coverage) in `specs/012-tutor-agent/eval/grounding-test-questions.md` (`/speckit-analyze` finding H1 -- SC-002 has no fixture to measure against otherwise)
- [ ] T037 [P] Verify SC-001 (3s p95 first-token latency) and SC-004 (incremental streaming) against a live Vercel deployment of both `tutor-agent/` and `backend` -- **blocked: no live Vercel deployment exists yet in this environment**
- [ ] T038 [P] Verify SC-002 (>=90% grounding rate) against T036's test-question set (depends on T036) -- **blocked: same live-deployment dependency as T037, plus real LLM/embedding calls against every row in the new fixture**

---

## Phase 7: FR-016 -- Structural Grounding Channel

**Purpose**: Replace the marker+JSON-in-text grounding protocol (found
unreliable across three PR-review rounds, PRs #42/#44) with a
structurally separate `cite_passages` tool call, per `/speckit-clarify`
(2026-08-28) and `/speckit-plan`'s research.md §9. Not a new user
story -- this changes *how* User Story 1's existing grounding signal
(FR-003) is transported, not what it claims to a learner.

- [ ] T039 [P] In `tutor-agent/src/agent.py`: add a `cite_passages(passage_ids: list[str])` `FunctionTool` whose implementation sets `tool_context.actions.skip_summarization = True` and returns no content; register it via `LlmAgent(tools=[cite_passages_tool], ...)` in `_build_agent`; remove `GROUNDING_MARKER` and its instruction paragraph from `_INSTRUCTION`, replacing it with an instruction to call `cite_passages` as the final step of the same generation; update the module docstring's "Grounding protocol" paragraph to describe the tool call instead of the marker (research.md §9).
- [ ] T040 [P] New unit test `tutor-agent/tests/test_cite_passages_tool.py`: the tool sets `skip_summarization` on its `ToolContext`; `_INSTRUCTION` no longer contains `GROUNDING_MARKER` and does instruct the model to call `cite_passages`.
- [ ] T041 [P] Rewrite `backend/src/services/tutor_agent_client/client.py`: delete `GROUNDING_MARKER`, `_matching_bracket_end`, `_candidate_score`, `_extract_grounded_id_candidates`; replace `_response_text_and_state(response) -> tuple[str, int | None]` with `_response_parts_and_state(response) -> tuple[list[Part], int | None]` that returns the status-update message's raw `parts` (or `[]` for a response that carries none) plus its task state -- preserving the existing status_update-only / artifact_update-dedup rule *unchanged* (the function being replaced only ever treated `status_update` as carrying genuinely new content because the final `artifact_update` duplicates the last `status_update`'s text verbatim; that rule must still hold for parts, not just text, `/speckit-analyze` finding U1). Add `_extract_cite_passages_ids(parts: list[Part]) -> list[UUID] | None` that scans for a `DataPart` tagged `adk_type: "function_call"` with `data.name == "cite_passages"` and returns `data.args.passage_ids` (dropping any non-UUID-shaped entry, same defensive tolerance the old code had). Rewrite `_process_raw_events` to yield a `TutorAnswerDelta` per `TextPart`'s text and use `_extract_cite_passages_ids` (filtered against `offered_passage_ids`) for the final `TutorAnswerResult`. If the stream completes with no `cite_passages` call found, set a `missing_citation_call: true` attribute on the exchange's existing Langfuse span before returning `grounded_passage_ids = []` (research.md §9, `/speckit-analyze` finding U2). `TutorAnswerDelta`/`TutorAnswerResult` and every other module (`services/tutor/session.py`, `tests/integration/tutor_helpers.py`) are unaffected -- they consume this module's public shape, not its internals.
- [ ] T042 [P] Replace `backend/tests/unit/test_parse_grounded_ids.py` with `backend/tests/unit/test_extract_cite_passages_ids.py`: unit-test `_extract_cite_passages_ids` directly -- passage-id filtering against `offered_passage_ids`, a fabricated/stale id still dropped, and a `None`/no-`DataPart` input returning `None`. Delete the bracket-scanning/candidate-scoring tests -- that behavior no longer exists.
- [ ] T043 [P] New unit test `backend/tests/unit/test_process_raw_events.py`: drive `_process_raw_events` with a synthetic multi-chunk `StreamResponse` sequence covering (a) multiple `TextPart`s split across separate `status_update` chunks, (b) a `TextPart` and the `cite_passages` `DataPart` arriving in the *same* `status_update` message, (c) a final `artifact_update` response duplicating the last `status_update`'s text/parts (must not double-yield deltas or re-scan for the citation call), and (d) no `cite_passages` call at all -- asserting `grounded_passage_ids == []` and that the T041 Langfuse span attribute is set (`/speckit-analyze` finding C1: the old test file only ever covered the marker-parsing helper in isolation, never this aggregation loop).
- [ ] T044 Run the full backend (`backend/`) and Tutor Agent (`tutor-agent/`) suites; confirm no regression in `tests/integration/test_tutor_*.py` (unaffected by construction, T041's note); record FR-016 as shipped in `roadmap.md`'s Milestone 9 status, following T034's precedent.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- can start immediately.
- **Foundational (Phase 2)**: Depends on Setup -- BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only.
- **User Story 2 (Phase 4)**: Depends on Foundational; its two tasks (T029/T030) also depend on User Story 1's T022/T012 already existing (it extends, not duplicates, US1's orchestration and agent) -- not independent of US1's code, though its own test/behavior is independently verifiable once US1 is in place.
- **User Story 3 (Phase 5)**: Depends on Foundational; T032 depends on US1's T022 (the data it reads) and T024 (the router it registers into).
- **Polish (Phase 6)**: Depends on all three user stories being complete. T038 additionally depends on T036.
- **FR-016 (Phase 7)**: Independent of Phases 3-6's completion status (it only touches the grounding-signal transport, not orchestration) but shipped after Polish since it was clarified/planned after the original implementation was live. T040 depends on T039 (same file's tool); T042 and T043 both depend on T041 (same file's extraction function and rewritten aggregation loop); T044 depends on all five.

### Within Each User Story

- Tests are written before their corresponding implementation task and MUST fail first.
- Models/services before routes; routes before router registration; backend before frontend where the frontend depends on a real endpoint shape.
- Within US1: T021 (assemble + stream) before T022 (persist success/failure) before T023 (routes) before T024 (router registration).

### Parallel Opportunities

- All Setup tasks marked [P] (T002, T003) can run in parallel with T001.
- Within Foundational: T004-T006 (models) in parallel; T013/T014 (tutor-agent guardrails/tracing) in parallel once T001 lands.
- All [P]-marked tests within a story can run in parallel with each other.
- T025-T027 (frontend) can run in parallel with each other and with T019 (rate limit) once their respective dependencies land.
- US2 and US3 cannot start their implementation tasks until US1's T022/T012/T024 exist, but their own test tasks (T028, T031) can be written in parallel with US1's late-stage implementation.
- T036 (fixture) can be authored any time after Foundational -- doesn't depend on any user story's implementation, only on the content artifacts already existing.
- T039 (`tutor-agent/`) and T041 (`backend/`) can run in parallel -- different projects, each independently implementing its own half of the wire contract research.md §9 already fixed; T040 (depends only on T039) and T042/T043 (both depend only on T041) can all run in parallel with each other once their respective implementation task lands.

---

## Parallel Example: Foundational Phase

```bash
# Launch the three new models together:
Task: "Create ContentPassageEmbedding model in backend/src/models/content_passage_embedding.py"
Task: "Create TutoringSession model in backend/src/models/tutoring_session.py"
Task: "Create TutorExchange model in backend/src/models/tutor_exchange.py"

# Once tutor-agent/'s scaffold (T001) exists, launch guardrails and tracing together:
Task: "Implement tutor-agent/src/guardrails.py"
Task: "Implement tutor-agent/src/tracing.py"
```

## Parallel Example: User Story 1

```bash
# Launch all three tests together:
Task: "Integration test for POST /api/tutor/sessions in backend/tests/integration/test_tutor_sessions.py"
Task: "Integration test for POST /api/tutor/sessions/{id}/messages in backend/tests/integration/test_tutor_messages.py"
Task: "Unit test for passage_search.py in backend/tests/unit/test_passage_search.py"

# Launch frontend work together, independent of backend route wiring:
Task: "Implement frontend/src/app/tutor/page.tsx and frontend/src/components/TutorChat.tsx"
Task: "Add streaming-fetch helper to frontend/src/services/api.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (blocks everything).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run quickstart.md scenarios 1, 2, 5, 6 against a real dev database and deployment.
5. Deploy/demo if ready -- this alone proves the milestone's core claim (a grounded, streamed conversational answer).

### Incremental Delivery

1. Setup + Foundational -> foundation ready.
2. User Story 1 -> test independently -> deploy/demo (MVP).
3. User Story 2 -> test independently -> deploy/demo (personalization proof).
4. User Story 3 -> test independently -> deploy/demo (inspectability proof, closes Constitution Principle IV/V's requirement).
5. Polish -> full regression, live SC verification, roadmap.md status update.

---

## Notes

- [P] tasks touch different files with no unmet dependencies.
- Every user story's data and A2A plumbing come from Foundational -- no story reimplements retrieval, the A2A client, or the `tutor-agent/` service itself.
- FR-013/FR-014/FR-015 (rate limit, session uniqueness, in-flight rejection) are all US1 tasks, not Foundational -- they're behavior of the two endpoints US1 builds, not generic platform infrastructure other stories need independently.
- Commit after each task or logical group, per this repo's own convention (see recent `quiz-assignment`/`instructor-classroom` commit history).
- Stop at any checkpoint to validate a story independently before continuing.
- This project's Principle-VIII deletion-execution gap (`roadmap.md`'s new "Known gap" section) is explicitly **not** a task in this file -- it predates Milestone 9 and belongs to whichever milestone picks up `specs/009-privacy-retention/spec.md`'s deferred FR-004/FR-005, not to a feature that only extends the set of tables that gap already applies to.
- Phase 7 (FR-016) was scoped by reading the actual call sites, not assumed: `backend/tests/integration/tutor_helpers.py` mocks at the `stream_tutor_answer`/`TutorAnswerDelta`/`TutorAnswerResult` boundary, not the raw A2A response -- so integration tests and `services/tutor/session.py` need no changes at all; the rewrite is contained to `tutor_agent_client/client.py`'s raw-parsing internals, `tutor-agent/src/agent.py`, and their direct unit tests.
- T041's `_response_parts_and_state`/`_extract_cite_passages_ids` split (`/speckit-analyze` finding U1) and T043's dedicated `_process_raw_events` test (finding C1) exist because the pre-Phase-7 code's `_response_text_and_state` collapsed a response straight to flattened text, discarding the raw parts a `DataPart`-based design needs -- and because that same function's status_update/artifact_update dedup rule (its own docstring: skipping this double-counts the final chunk) had no dedicated test at all before Phase 7, only incidental coverage via `_extract_grounded_id_candidates`'s marker-based tests, which T042 replaces with narrower, function-scoped ones.

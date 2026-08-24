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

- [ ] T016 [P] [US1] Integration test for `POST /api/tutor/sessions` (create, and get-or-create per FR-014) in `backend/tests/integration/test_tutor_sessions.py`
- [ ] T017 [P] [US1] Integration test for `POST /api/tutor/sessions/{id}/messages` covering the streamed-grounded case, the honest-non-grounded case, the `409`/`429`/`422`/`503` rejection paths, and a session recovering after a `failed_at` exchange (finding H2) in `backend/tests/integration/test_tutor_messages.py`
- [ ] T018 [P] [US1] Unit test for `passage_search.py`'s similarity ranking in `backend/tests/unit/test_passage_search.py`

### Implementation for User Story 1

- [ ] T019 [P] [US1] Implement `check_tutor_rate_limit` in `backend/src/services/tutor/rate_limit.py`, mirroring `services/grading_client/guardrails.py`'s `check_rate_limit` exactly (FR-013, research.md §8)
- [ ] T020 [US1] Implement session get-or-create (`open_session`) in `backend/src/services/tutor/session.py` against the partial unique index (FR-014) (depends on T005, T009)
- [ ] T021 [US1] Implement request assembly and the streamed call in `submit_message` (`backend/src/services/tutor/session.py`): in-flight check (FR-015) -> rate limit (T019) -> length/moderation -> `passage_search` (T011) -> bundle context -> call `tutor_agent_client` (T015) -> proxy the stream to the caller (FR-002/FR-005/FR-012) (depends on T006, T011, T015, T019, T020)
- [ ] T022 [US1] Implement `submit_message`'s completion handling (`backend/src/services/tutor/session.py`): on stream success, persist the `TutorExchange` row (`answer_text`, `grounded`, `retrieved_passage_ids`, `delegation_context`), write the `tutor_exchange_completed` audit event, and flush the Langfuse span; on stream failure/timeout, set `failed_at` instead of leaving `answer_text` ambiguously `NULL` (FR-003/FR-004/FR-007/FR-008, closes finding H2) (depends on T021)
- [ ] T023 [US1] Implement `POST /api/tutor/sessions` and `POST /api/tutor/sessions/{session_id}/messages` in `backend/src/api/routes/tutor.py`, guardian-mediated + demo-learner auth (FR-001) (depends on T020, T022)
- [ ] T024 [US1] Register the `tutor` router in `backend/src/api/main.py` (depends on T023)
- [ ] T025 [P] [US1] Implement the tutoring chat page `frontend/src/app/tutor/page.tsx` and streaming chat component `frontend/src/components/TutorChat.tsx`
- [ ] T026 [P] [US1] Add a streaming-fetch helper for `/api/tutor/...` to `frontend/src/services/api.ts`
- [ ] T027 [P] [US1] Unit tests for `TutorChat.tsx` in `frontend/tests/unit/tutor-chat.test.tsx`

**Checkpoint**: User Story 1 is fully functional and independently testable (quickstart scenarios 1, 2, 5, 6).

---

## Phase 4: User Story 2 - Tutor answers grounded in the learner's actual state (Priority: P2)

**Goal**: When a question depends on the learner's own performance, the answer reflects their real mastery/weak-area state, obtained from the existing deterministic model -- never guessed.

**Independent Test**: Ask a learner with a known "struggling" topic what to work on; verify the answer names that actual topic. Repeat with a brand-new learner; verify an honest "not enough data" response (spec.md US2).

### Tests for User Story 2

- [ ] T028 [P] [US2] Integration test for a performance-dependent question (known weak area) and a brand-new learner's honest no-data response in `backend/tests/integration/test_tutor_delegation_context.py`

### Implementation for User Story 2

- [ ] T029 [US2] Extend `submit_message` (`backend/src/services/tutor/session.py`) with an in-process call to the existing Recommendation/Sequencing services when the question needs performance context, appending a `{agent, request, response}` record to `delegation_context` per call (FR-006, structured shape per finding M1) (depends on T022)
- [ ] T030 [US2] Extend `tutor-agent/src/agent.py`'s prompt/tool wiring so the bundled `delegation_context` entries are used verbatim in the answer rather than re-derived (depends on T012)

**Checkpoint**: User Stories 1 and 2 both work independently (quickstart scenario 3).

---

## Phase 5: User Story 3 - Inspect why the Tutor said what it said (Priority: P3)

**Goal**: An instructor or engineer can reconstruct, for a specific past exchange, which passages were retrieved and which delegated-agent calls (with their actual inputs and outputs) fed the answer -- without asking the Tutor Agent to explain itself.

**Independent Test**: Pick a past tutoring exchange and confirm an inspector can retrieve its retrieved passages and per-call delegation context via `GET /api/tutor/exchanges/{id}` (spec.md US3).

### Tests for User Story 3

- [ ] T031 [P] [US3] Integration test for `GET /api/tutor/exchanges/{exchange_id}` auth (owning guardian, enrolled instructor, demo-instructor), the derived `status` field (`completed`/`failed`/`in_progress`), and the structured `delegation_context` payload shape in `backend/tests/integration/test_tutor_exchange_inspection.py`

### Implementation for User Story 3

- [ ] T032 [US3] Implement `GET /api/tutor/exchanges/{exchange_id}` in `backend/src/api/routes/tutor.py`, enrollment-scoped auth mirroring `content_review`'s existing pattern, deriving `status` from `answer_text`/`failed_at` (depends on T022, T024)

**Checkpoint**: All three user stories are independently functional (quickstart scenario 4).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation across all three stories, regression, and the milestone's own Success Criteria.

- [ ] T033 [P] Playwright E2E `frontend/tests/e2e/tutor-round-trip.spec.ts`: open a session, ask a question, confirm a grounded streamed answer, then inspect the exchange as the instructor (quickstart scenarios 1-4)
- [ ] T034 Run the full backend suite against a real, freshly migrated dev database; confirm SC-005 (Milestones 1-8 unmodified) and record the result in `roadmap.md`'s Milestone 9 status, following the precedent set by Milestones 7/8's own DoD confirmation
- [ ] T035 [P] Run `check_no_subject_conditionals.py` against the new retrieval/loader code (Constitution Principle III gate)
- [ ] T036 [P] Author a defined grounding test-question set (>=20 questions across both subjects, each with its expected topic/passage coverage) in `specs/012-tutor-agent/eval/grounding-test-questions.md` (`/speckit-analyze` finding H1 -- SC-002 has no fixture to measure against otherwise)
- [ ] T037 [P] Verify SC-001 (3s p95 first-token latency) and SC-004 (incremental streaming) against a live Vercel deployment of both `tutor-agent/` and `backend`
- [ ] T038 [P] Verify SC-002 (>=90% grounding rate) against T036's test-question set (depends on T036)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- can start immediately.
- **Foundational (Phase 2)**: Depends on Setup -- BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only.
- **User Story 2 (Phase 4)**: Depends on Foundational; its two tasks (T029/T030) also depend on User Story 1's T022/T012 already existing (it extends, not duplicates, US1's orchestration and agent) -- not independent of US1's code, though its own test/behavior is independently verifiable once US1 is in place.
- **User Story 3 (Phase 5)**: Depends on Foundational; T032 depends on US1's T022 (the data it reads) and T024 (the router it registers into).
- **Polish (Phase 6)**: Depends on all three user stories being complete. T038 additionally depends on T036.

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

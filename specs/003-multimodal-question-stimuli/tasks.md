# Tasks: Multimodal Question Stimuli -- Image-Based Questions

**Input**: Design documents from `/specs/003-multimodal-question-stimuli/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present)

**Tests**: Included. `roadmap.md`'s Milestone 10 Definition of Done makes SC-002 (100% of image questions have alt text) and SC-003 (missing/oversized/wrong-format images fail at load time, not display time) hard gates, and requires Milestones 1-9's full suites to still pass -- so the test tasks below are load-bearing, not optional scaffolding.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete same-phase task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are per `plan.md`'s Project Structure

## Path Conventions

Extends the existing `backend/` + `frontend/` monorepo: `backend/content/<subject>/`, `backend/src/{models,services/content_artifact,services/quiz,agents/{assessment_gen,sequencing},api/routes}/`, `backend/alembic/versions/`, `backend/tests/{unit,integration}/`; `frontend/scripts/`, `frontend/public/content-images/`, `frontend/src/{services,components}/`, `frontend/tests/{unit,e2e}/`.

---

## Phase 1: Setup

**Purpose**: Confirm this feature needs no new dependency, and keep the build-time sync target out of git

- [ ] T001 [P] Confirm no new dependency is required in `backend/pyproject.toml` or `frontend/package.json` (research.md §1/§2 -- image validation is extension/`Path.stat()` checks, no imaging library; the sync script uses only Node's built-in `fs`/`path`)
- [ ] T002 [P] Add `frontend/public/content-images/` to `.gitignore` (research.md §1 -- a build-time sync target copied from `backend/content/*/images/`, never itself git-tracked)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Content-artifact schema/validation, DB schema, and the build-time image pipeline every user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 [P] Extend `ValidatedTopic` with an optional `image_asset: dict | None` field and add schema-only validation (a mapping with non-empty `filename`/`alt_text` strings, FR-003) to `validate_content_artifact()` in `backend/src/services/content_artifact/validator.py` per data-model.md -- no filesystem access in this file, preserving its existing pure-validation contract
- [ ] T004 [P] Add nullable `image_asset: Mapped[dict | None]` JSON column to `Topic` in `backend/src/models/topic.py` per data-model.md
- [ ] T005 [P] Add nullable `image_url: Mapped[str | None]` and `image_alt_text: Mapped[str | None]` Text columns to `GeneratedQuestion` in `backend/src/models/generated_question.py` per data-model.md
- [ ] T006 Extend `load_content_artifact_file()` with filesystem-level image checks (file exists under `<artifact_dir>/images/`, size <= 1,048,576 bytes, extension in `.png`/`.jpg`/`.jpeg`/`.svg`, case-insensitive, all raising `ContentArtifactValidationError`, FR-002) and extend `persist_content_artifact()` to persist `Topic.image_asset`, in `backend/src/services/content_artifact/loader.py` per data-model.md (depends on T003, T004)
- [ ] T007 Alembic migration: add `topics.image_asset` (JSON, nullable) and `generated_questions.image_url`/`generated_questions.image_alt_text` (Text, nullable) columns in `backend/alembic/versions/` (depends on T004, T005)
- [ ] T008 [P] Implement `content_image_url(subject_id: str, filename: str) -> str` in `backend/src/services/content_artifact/image_asset.py` per research.md §1/§5 (`f"/content-images/{subject_id}/{filename}"`)
- [ ] T009 [P] Implement `frontend/scripts/sync-content-images.mjs` -- `fs.cpSync(..., {recursive: true})` copying every `backend/content/<subject>/images/` directory into `frontend/public/content-images/<subject>/`, failing loudly (non-zero exit) if `backend/content/` isn't reachable from the frontend build context (research.md §1's flagged risk) rather than silently skipping
- [ ] T010 Wire `predev`/`prebuild` npm scripts invoking `node scripts/sync-content-images.mjs` in `frontend/package.json` (depends on T009) -- `dev`/`build` themselves stay untouched; npm runs the pre-hooks automatically
- [ ] T011 [P] Unit test: `load_content_artifact_file()` rejects a content artifact whose `image_asset.filename` doesn't exist under `images/`, one exceeding 1 MB, and one with a `.gif` extension -- each with a specific `ContentArtifactValidationError` message and no partial DB write (FR-002, SC-003, spec.md Edge Cases) in `backend/tests/unit/test_content_artifact_image_validation.py` (depends on T006)

**Checkpoint**: Schema, validation, and the image-serving pipeline are ready. No learner-visible behavior yet -- that starts at User Story 1.

---

## Phase 3: User Story 1 - Answer a question that shows an image, not just text (Priority: P1) 🎯 MVP

**Goal**: A learner requesting a question for an image-bearing algebra-1 topic gets a question that references and displays that image, and grades it exactly like a text-only question.

**Independent Test**: Given a content artifact with a topic that includes a bundled image asset, request a question for that topic and confirm the resulting question includes a reference to the image and displays correctly.

### Tests for User Story 1

- [ ] T012 [P] [US1] Integration test: `GET /api/learners/{learner_id}/next-question` for an image-bearing topic returns non-null `image_url`/`image_alt_text` (and the referenced file exists once synced); for a topic with no `image_asset` both are `null` (User Story 1 Acceptance Scenarios 1 & 3) in `backend/tests/integration/test_next_question_image.py` -- exercises the algebra-1 image-bearing topic added in T022/T023 (`conftest.py`'s `algebra_subject` fixture loads the real `content/algebra-1/subject.yaml`, not a synthetic fixture); write this test first per TDD, expect it to fail with "no image-bearing topic found" until T022/T023 land, same as it fails on missing implementation until T015-T019 land
- [ ] T013 [P] [US1] Integration test: `POST /api/questions/{question_id}/answer` for an image-based question produces the exact same response shape and grading outcome as a text-only question of the same `question_type` -- no new fields, no new error cases, same deterministic answer-key comparison (User Story 1 Acceptance Scenario 2, FR-004, SC-001) in `backend/tests/integration/test_answer_image_question_grading_unchanged.py` -- same T022/T023 content dependency as T012
- [ ] T014 [P] [US1] Frontend unit test: `QuestionCard` renders an `<img>` with the given `alt` text when `question.image_url` is set, and renders nothing extra when it's `null` in `frontend/tests/unit/question-card-image.test.tsx`

### Implementation for User Story 1

- [ ] T015 [US1] Add an optional `image_alt_text: str | None = None` parameter to `generate_question()` plus one added instruction-template paragraph telling the model an image will be shown and to phrase the stem accordingly, in `backend/src/agents/assessment_gen/agent.py` per research.md §3 (depends on T003)
- [ ] T016 [US1] Extend `NextQuestionResult` with `image_url: str | None`/`image_alt_text: str | None`, computed from `topic.image_asset` via `content_image_url()` and passed into `generate_question()`, in `backend/src/agents/sequencing/agent.py` (depends on T008, T015)
- [ ] T017 [US1] Extend `QuizQuestionResult` the same way in `generate_quiz_question()`, and copy `image_url`/`image_alt_text` onto the persisted row in `persist_quiz_question()`, in `backend/src/services/quiz/session.py` (depends on T008, T015)
- [ ] T018 [US1] Extend `NextQuestionOut` and the inline `GeneratedQuestion(...)` construction in `get_next_question()` to set/return `image_url`/`image_alt_text` in `backend/src/api/routes/questions.py` (depends on T016)
- [ ] T019 [US1] Extend `QuizQuestionOut` (shared by `POST /api/quizzes` and `GET /api/quizzes/{id}/next-question`) to include `image_url`/`image_alt_text` in `backend/src/api/routes/quiz.py` (depends on T017)
- [ ] T020 [P] [US1] Extend the `NextQuestion` interface with `image_url: string | null`/`image_alt_text: string | null` in `frontend/src/services/api.ts` per contracts/api.md
- [ ] T021 [US1] Render `<img src={question.image_url} alt={question.image_alt_text ?? ""} />` above the stem when `image_url` is set in `frontend/src/components/QuestionCard.tsx` (depends on T020, T014)
- [ ] T022 [US1] Add an `image_asset` entry (`filename`, `alt_text`) to one topic in `backend/content/algebra-1/subject.yaml`, with a real image file under `backend/content/algebra-1/images/` (depends on T006, T007)
- [ ] T023 [US1] Reload the algebra-1 content artifact via `backend/scripts/load_content_artifact.py` and confirm it validates and persists `Topic.image_asset` (depends on T022)

**Checkpoint**: User Story 1 is independently functional and demoable -- an image-bearing algebra-1 question displays its image and grades identically to a text-only one.

---

## Phase 4: User Story 2 - Add image-based questions to a subject without touching engine code (Priority: P1)

**Goal**: Prove the capability built in User Story 1 is genuinely domain-agnostic by adding an image to a second subject with zero engine-code changes.

**Independent Test**: Add an image asset to a second subject's content artifact, with zero edits to any file outside that artifact's own directory, and confirm image-based question generation works correctly for it.

- [ ] T024 [US2] Add an `image_asset` entry to one topic in `backend/content/biology/subject.yaml`, with a real image file under `backend/content/biology/images/` (depends on Phase 3 complete)
- [ ] T025 [US2] Reload the biology content artifact via `backend/scripts/load_content_artifact.py` and confirm it validates and persists `Topic.image_asset` (depends on T024)
- [ ] T026 [US2] Extend `backend/tests/integration/test_second_subject.py` to request a question for biology's image-bearing topic and assert `image_url`/`image_alt_text` are present and grading behaves identically to algebra-1's image-based question (FR-006, SC-004) (depends on T025)
- [ ] T027 [US2] Run `backend/scripts/check_no_subject_conditionals.py` and confirm this feature introduced zero subject-id-keyed conditionals (FR-006) (depends on T026)

**Checkpoint**: The capability is proven domain-agnostic across two subjects with zero engine-code changes -- both P1 stories requiring new engine code are now complete.

---

## Phase 5: User Story 3 - Every image-based question is accessible (Priority: P1)

**Goal**: Prove the alt-text requirement built into Foundational's schema validation (T003) actually rejects a definition that omits it.

**Independent Test**: Attempt to define a content artifact's image asset without an alt-text/description field and confirm content-artifact validation rejects it at load time.

- [ ] T028 [US3] Unit test: a content artifact whose `image_asset` entry omits (or blanks) `alt_text` fails `validate_content_artifact()`/`load_content_artifact_file()` with `ContentArtifactValidationError`, and `Subject.validated_at` is never set (FR-003, SC-002) in `backend/tests/unit/test_content_artifact_image_alt_text_required.py` (depends on T003, T006)

**Checkpoint**: All three P1 stories are independently verified -- display+grading (US1), domain-agnosticism (US2), and accessibility enforcement (US3).

---

## Phase 6: User Story 4 - Images work correctly on the live Vercel deployment (Priority: P2)

**Goal**: Confirm the build-time sync pipeline (Foundational) actually serves images correctly once deployed -- no new production code, verification only.

**Independent Test**: Deploy to Vercel and confirm an image-based question renders correctly end to end against the live deployment.

- [ ] T029 [US4] Extend the deployment smoke test to request an image-bearing question and assert the resulting `<img>` element's resolved `src` returns `200` in `frontend/tests/e2e/smoke.spec.ts` (SC-005) (depends on Phase 3 and Phase 4 complete)
- [ ] T030 [US4] Deploy to `staging` and run quickstart.md's step 7 (live Vercel validation) against the real deployment; record the result here and in spec.md/roadmap.md, resolving research.md §1's flagged "Known unverified risk" one way or the other (depends on T029; requires an actual deploy, external action per this project's established practice for live-only verification)

**Checkpoint**: All four user stories independently functional, including against the real deployment.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and closing out this milestone's roadmap entry

- [ ] T031 [P] Regression check: run Milestones 1-9's full backend (`pytest`) and frontend (`vitest`) suites, confirm they still pass unmodified (roadmap.md Milestone 10 Definition of Done: "Milestones 1-9's full suites still pass")
- [ ] T032 [P] Regression test (FR-007): confirm `POST /api/questions/{question_id}/answer`'s `validate_response_shape()` still rejects/ignores an image-like payload (e.g. a base64 data-URI string submitted as a `free_text` or `numeric` response) exactly like any other malformed answer -- no image-upload answer path exists, and this makes that fact mechanically checked rather than merely assumed by omission, in `backend/tests/unit/test_answer_rejects_image_payload.py`
- [ ] T033 Run quickstart.md's 7 validation scenarios end to end against a live dev DB with real Claude generation calls, and record results (depends on all prior tasks)
- [ ] T034 [P] Update `roadmap.md`'s Milestone 10 status line to reflect completion, verified against this feature's actual final state rather than left stale (per this project's own precedent of catching stale status lines late -- see Milestone 3's "Sequencing note")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion -- BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion only. This is the actual feature build.
- **User Story 2 (Phase 4)**: Depends on User Story 1 being complete -- exercises the same mechanism against a second subject's content.
- **User Story 3 (Phase 5)**: Depends on Foundational completion (the enforcement it verifies is built there); ordered after US1/US2 here only because both are P1 stories with new engine code, not because of a hard dependency.
- **User Story 4 (Phase 6)**: Depends on User Story 1 and User Story 2 being complete and deployed -- verifies live behavior of already-built mechanisms.
- **Polish (Phase 7)**: T031/T032/T034 have no hard dependency beyond Foundational; T033 needs everything.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3/US4 -- this is the real engine-code build.
- **US2 (P1)**: Content + test-extension only; depends on US1's mechanism existing to exercise.
- **US3 (P1)**: Verification-only; depends on Foundational's validator/loader existing to exercise.
- **US4 (P2)**: Verification-only, live-deployment-dependent; depends on US1 and US2 existing to exercise.

### Within Each User Story

- Tests written and failing before implementation for US1 (T012-T014 before T015-T023).
- US2/US3/US4 verify already-composed behavior after implementation completes, mirroring spec 005's precedent of a late-phase check run rather than a pre-implementation TDD test for stories that add content/deployment verification rather than new engine code.
- Schema/model changes before migration; migration before any DB-touching test or implementation.
- `content_image_url()` helper before the two result-carrier dataclasses that call it.
- Result-carrier dataclasses before the API routes that read them; API routes before the frontend types that mirror them; frontend types before the component that consumes them.

---

## Parallel Example: Foundational

```bash
# Independent files, no dependency on an incomplete same-phase task:
Task: "Add nullable image_asset JSON column to Topic in backend/src/models/topic.py"
Task: "Add nullable image_url/image_alt_text columns to GeneratedQuestion in backend/src/models/generated_question.py"
Task: "Implement content_image_url() in backend/src/services/content_artifact/image_asset.py"
Task: "Implement frontend/scripts/sync-content-images.mjs"
```

---

## Implementation Strategy

### MVP scope: User Story 1 alone

Unlike User Stories 2, 3, and 4 (which verify behavior US1's own mechanism already produces, per research.md §4's fixed-per-topic design and Foundational's validation logic), User Story 1 is the entire feature build. The smallest real MVP is US1 alone: one algebra-1 topic's questions display an image and grade identically to a text-only question.

1. Complete Phase 1 (Setup) + Phase 2 (Foundational) -- schema migrated,
   validation in place, image-sync pipeline wired.
2. Complete Phase 3 (US1) -- image-based questions work end to end for
   algebra-1, grading verified unchanged (SC-001).
3. **STOP and VALIDATE**: run US1's Independent Test. This is the
   smallest demoable increment.
4. Complete Phase 4 (US2) -- domain-agnosticism proven for biology
   (SC-004), no new engine code.
5. Complete Phase 5 (US3) -- accessibility enforcement mechanically
   verified (SC-002), no new engine code.
6. Complete Phase 6 (US4) -- live deployment verified (SC-005).
7. Complete Phase 7 (Polish) -- Milestones 1-9 regression check, full
   quickstart.md validation, roadmap.md status closed out.

### Incremental delivery

Each phase checkpoint (end of Phase 3, 4, 5, 6, 7) is a point where the
multimodal-question capability is in a coherent, independently
testable state.

---

## Notes

- `[P]` tasks = different files, no dependency on an incomplete same-phase task.
- `[Story]` label maps a task to its user story for traceability; Setup, Foundational, and Polish tasks carry no `[Story]` label by design -- Foundational's schema/validation/sync-pipeline work serves all four user stories rather than any one of them.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently before continuing.
- `/speckit-analyze` MUST run before `/speckit-implement` per CLAUDE.md/Constitution Development Workflow -- do not skip it once this task list is approved.

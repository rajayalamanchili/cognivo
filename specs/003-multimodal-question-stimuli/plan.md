# Implementation Plan: Multimodal Question Stimuli -- Image-Based Questions

**Branch**: `003-multimodal-question-stimuli` | **Date**: 2026-08-30 | **Spec**: `specs/003-multimodal-question-stimuli/spec.md`

**Input**: Feature specification from `/specs/003-multimodal-question-stimuli/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Content artifacts can bundle a per-topic image asset (a static file,
git-versioned alongside that subject's topic graph, with required
alt-text); the Assessment-Generation Agent produces a structured
question referencing it when the selected topic has one, and grading
stays the exact same deterministic answer-key comparison as a
text-only question -- no new grading logic (Constitution Principle
II). Images are authored/trusted static files served by the frontend
Next.js Service's built-in `public/` static serving, synced there at
build time from their authoritative home under `backend/content/`
(research.md §1) -- no new backend endpoint, no external storage
service, no runtime filesystem read. Two existing subjects
(`algebra-1`, `biology`) each get an image-bearing topic to prove the
capability requires zero engine-code changes (Constitution Principle
III, FR-006/SC-004).

## Technical Context

**Language/Version**: Python 3.12+ (backend, unchanged), TypeScript on
Next.js 16 (frontend, unchanged). No new language.

**Primary Dependencies**: No new dependency in either service. Backend
reuses PyYAML/SQLAlchemy/Pydantic/ADK+LiteLLM already in place;
image format/size validation is a stdlib-only extension check +
`Path.stat()` (research.md §2), not a new imaging library. Frontend's
build-time image sync script uses only Node's built-in `fs`/`path`
(research.md §1).

**Storage**: PostgreSQL (existing, via Neon) -- two new nullable
columns (`Topic.image_asset`, `GeneratedQuestion.image_url`/`image_alt_text`).
Image files themselves are never DB-stored (FR-001 explicitly rules out
inline base64 in the topic-graph document) -- they're git-versioned
static files plus one new Next.js-served static directory.

**Testing**: `pytest` (backend, existing) + `Vitest` (frontend,
existing) + `Playwright` deployment smoke test (existing) -- all
extended with new cases, no new framework.

**Target Platform**: Vercel Services (existing two-service project:
`services.frontend` Next.js, `services.backend` FastAPI) --
unchanged deployment shape.

**Project Type**: Web application (existing frontend+backend Vercel
Services split).

**Performance Goals**: None newly introduced -- images are pre-supplied
static files served via Vercel's static hosting, not a model-call
latency path; spec 007's SC-006 (10s p95 answer-path budget) is
unaffected since grading is byte-for-byte unchanged.

**Constraints**: Image assets MUST be <= 1 MB and one of PNG/JPEG/SVG
(FR-002), enforced at content-artifact load time.

**Scale/Scope**: Two subjects (`algebra-1`, `biology`), each with at
least one image-bearing topic (SC-004); no new learner-facing scale
requirement beyond what Milestone 1 already established.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Personalization Is a Model, Not a Guess | Unaffected -- the BKT mastery model and Sequencing Agent's topic selection are untouched; an image is a display-only property of whichever topic Sequencing already picked. |
| II. Generated Content Is Graded Against a Rubric, Never Vibes | Unaffected by design (FR-004): `image_url`/`image_alt_text` are display-only fields never read by `services/mastery/grading.py` or the Grading Agent A2A path. SC-001 verifies this explicitly. |
| III. One Engine, Many Subjects | `image_asset` is topic-level content-artifact data (like `skill_definition`/`difficulty_calibration`), never a subject-id-keyed conditional in engine code. SC-004 requires extending `test_second_subject.py` to prove this for a second subject -- planned as part of this feature, not deferred. |
| IV. Multi-Agent Boundaries Reflect Real Responsibility | No new agent. The Assessment-Generation Agent gains one optional instruction input (`image_alt_text`); no independent-evaluation/versioning need exists for splitting image handling into its own agent. |
| V. Every Personalization/Grading Decision Is Logged and Explainable | Unaffected -- the existing `traced_request()` wrapping and `record_event()` audit-log calls around question generation are unchanged; no new decision type is introduced that needs its own "why" trail (an image attachment is deterministic from `Topic.image_asset`, not a decision requiring justification). |
| VI. Agent Boundaries Match Deployment Boundaries | N/A -- no new A2A service. |
| VII. Spec Before Code, Milestone-Gated | `spec.md` is clarified and approved; this `plan.md` follows it, `tasks.md` follows this. |
| VIII. No Real Learner Data Until Privacy/Retention Specified | Unaffected -- image assets are authored content, not learner data; no change to demo-account handling. |
| IX. Deployable and Demoable From the Start | Directly addressed: the build-time sync (research.md §1) keeps image serving inside Vercel's static-hosting model, with no runtime filesystem read from either serverless function. One risk is flagged as unverified until first deploy (research.md §1's "Known unverified risk") -- documented rather than assumed, consistent with this project's existing practice for Vercel-specific unknowns (tech-stack.md's A2A deployment rows). |
| X. Staged Release Discipline | This work lands on feature branch `003-multimodal-question-stimuli`, PR'd into `staging` per the existing workflow -- no change to that process. |

**Result**: PASS, no violations requiring justification. Complexity
Tracking table below is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-multimodal-question-stimuli/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── content/
│   ├── algebra-1/
│   │   ├── subject.yaml            # extended: image_asset on >=1 topic
│   │   └── images/                 # NEW: git-versioned image files
│   └── biology/
│       ├── subject.yaml            # extended: image_asset on >=1 topic
│       └── images/                 # NEW
├── src/
│   ├── models/
│   │   ├── topic.py                        # extended: image_asset JSON column
│   │   └── generated_question.py           # extended: image_url, image_alt_text columns
│   ├── services/
│   │   ├── content_artifact/
│   │   │   ├── validator.py                # extended: image_asset schema check
│   │   │   ├── loader.py                   # extended: FS-level image validation
│   │   │   └── image_asset.py              # NEW: content_image_url() helper
│   │   └── quiz/session.py                 # extended: QuizQuestionResult + persist_quiz_question
│   ├── agents/
│   │   ├── assessment_gen/agent.py         # extended: image_alt_text instruction param
│   │   └── sequencing/agent.py             # extended: NextQuestionResult
│   └── api/routes/
│       ├── questions.py                    # extended: NextQuestionOut
│       └── quiz.py                         # extended: QuizQuestionOut
├── alembic/versions/                       # NEW migration
└── tests/integration/test_second_subject.py  # extended (SC-004)

frontend/
├── scripts/
│   └── sync-content-images.mjs     # NEW: build-time copy from backend/content/*/images
├── public/content-images/          # NEW: build-time sync target, gitignored
├── package.json                    # extended: predev/prebuild hooks
└── src/
    ├── services/api.ts             # extended: NextQuestion.image_url/image_alt_text
    └── components/QuestionCard.tsx # extended: <img> render when image_url is set
```

**Structure Decision**: Existing two-service Vercel web application
(`frontend/` Next.js Service, `backend/` FastAPI Service, per
`vercel.json`) -- this feature adds no new service and no new
top-level directory, only extending files within both existing trees
plus one new `backend/content/<subject>/images/` convention and one
new `frontend/scripts/` build step (research.md §1).

## Complexity Tracking

*No entries -- Constitution Check above passed with no violations to justify.*

# Cognivo

Cognivo is a domain-agnostic, AI-powered learning platform. It
personalizes what a learner sees next using a real statistical mastery
model (not an LLM's guess), generates assessment questions dynamically
against a rubric it authors alongside every question, grades free-text
answers against that rubric, flags weak areas with concrete next-step
suggestions, and tutors conversationally — all for an instructor-run
classroom, not just a solo learner.

## Why "domain-agnostic"?

Nothing about mastery tracking, question generation, or grading is
hardcoded to a subject. Every subject-specific detail (topics, skill
definitions, prerequisite graphs, difficulty calibration) lives in a
versioned content artifact, never in engine code. The project ships
with two live subjects (**Algebra 1** and **Biology**) from the very
first milestone specifically to prove this claim early, not as an
afterthought.

## Features

- **Real mastery model, not a vibe.** Every learner's per-topic mastery
  is tracked with Bayesian Knowledge Tracing — explicit, deterministic,
  and explainable ("recommended because mastery on X is below
  threshold Y"), called by the Sequencing Agent as a tool rather than
  inferred from chat context.
- **Dynamically generated, rubric-backed questions.** Multiple-choice,
  numeric, and free-text questions are generated on demand, each with
  its own answer key or grading rubric authored *before* it's ever
  shown to a learner — never graded against an LLM's freeform judgment.
- **Free-text grading via a real agent-to-agent service.** Short-answer
  responses are graded by an independently deployable Grading Agent
  against the question's own rubric, with per-criterion feedback on
  what was met and what was missed.
- **Weak-area recommendations with cited evidence.** The Recommendation
  Agent flags struggling topics and suggests a concrete, prerequisite-
  aware next step — every flag backed by the specific graded answers
  that produced it, never an unsupported claim.
- **Conversational Tutor Agent.** Ask plain-English questions and get a
  streamed, token-by-token answer grounded in the subject's own content
  (via vector retrieval), with the ability to delegate to the
  Recommendation Agent for "how am I doing?"-style questions.
- **Adaptive difficulty quizzes.** A bounded, named quiz session where
  difficulty adjusts to in-quiz performance, feeding every answer back
  into the same persistent mastery state a regular question would.
- **Learner dashboard.** Per-topic mastery, a freshly generated
  weak-area report, and an illustrative (explicitly not-a-fixed-plan)
  path of what's next.
- **Instructor classroom.** Roster management, an instructor dashboard
  aggregating every enrolled learner's weak areas, and a content-review
  queue for questions flagged as low quality.
- **Instructor-assigned quizzes.** An instructor can target a quiz at
  some or all of a roster, with per-student results broken out in the
  instructor dashboard.
- **Multimodal question stimuli.** Questions can bundle an image for
  context (with required alt text), graded with the exact same
  deterministic logic as a text-only question.
- **Every decision is logged and explainable.** "Why was I shown this?"
  and "why was this marked wrong?" both have real, traceable answers —
  and every agent call is separately traced (inputs, outputs, latency,
  cost) for engineering-side observability.
- **Deployable from day one.** The whole platform — frontend, backend,
  and each independently deployable agent service — runs on Vercel,
  designed around its stateless, serverless execution model rather than
  assuming a persistent server process.

See [`roadmap.md`](roadmap.md) for the full milestone-by-milestone
build sequence, including what's shipped and what's still in progress.

## Screenshots

Coming soon — the demo flow below is the fastest way to see these
pages live in the meantime.

| Page | Screenshot |
|---|---|
| Learner placement & practice | _coming soon_ |
| Learner dashboard (mastery + weak areas) | _coming soon_ |
| Adaptive quiz | _coming soon_ |
| Tutor chat | _coming soon_ |
| Instructor dashboard | _coming soon_ |
| Content review queue | _coming soon_ |

## Architecture

Cognivo is a monorepo with several independently deployable units:

| Project | Role |
|---|---|
| `backend/` | FastAPI service owning all data, agent orchestration (Google ADK), the mastery model, and content-artifact loading. |
| `frontend/` | Next.js + TypeScript app for learners, guardians, and instructors. |
| `grading-agent/` | A standalone A2A service that grades free-text answers against a question's rubric — independently versionable and deployable from the rest of the platform. |
| `tutor-agent/` | A standalone A2A service that composes the Tutor Agent's grounded, streamed answers. |

Cross-cutting technology decisions (agent framework, database, LLM
provider, observability, deployment target) are locked in
[`tech-stack.md`](tech-stack.md) — nothing here is guessed per feature.
The full architectural rationale (why mastery is a model and not an
LLM guess, why agent boundaries are justified individually rather than
adopted by default, why real learner data has its own gate) lives in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Getting started

### Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js 22+ and `npm`
- A PostgreSQL database with the `pgvector` extension (this project
  uses [Neon](https://neon.tech) in every deployed environment)
- API keys for Anthropic (Claude) and Voyage AI (embeddings) — see
  `backend/.env.example` for the full list of required environment
  variables

### Backend

```bash
cd backend
uv sync
cp .env.example .env   # fill in DATABASE_URL, ANTHROPIC_API_KEY, etc.
uv run alembic upgrade head
uv run uvicorn src.api.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — the home page
lets you start a placement flow for either seeded subject immediately,
against a clearly badged demo learner profile, with no sign-up
required.

### Grading Agent / Tutor Agent (optional, for local free-text/tutor flows)

```bash
cd grading-agent   # or tutor-agent/
uv sync
uv run uvicorn src.agent:app --reload --port 8001
```

Point the backend's `GRADING_AGENT_URL` / `TUTOR_AGENT_URL` at
whichever port you run these on locally.

## Testing

```bash
cd backend && uv run pytest
cd frontend && npm test         # Vitest unit/component tests
cd frontend && npm run test:e2e # Playwright, against a running app
```

Each independently deployed agent service (`grading-agent/`,
`tutor-agent/`) carries its own test suite, deliberately kept
independent of the backend's — see the constitution's Principle IV.

## Demo accounts

A seeded demo learner, plus a seeded demo instructor and student, let
you explore the whole product without creating a real account. Every
demo account is explicitly flagged in the data model and shown with a
persistent, unmissable "DEMO ACCOUNT" badge in the UI — never reachable
via the real sign-up flow, and reset to a known-good state on a
schedule. Real guardian/learner/instructor accounts are only permitted
because a dedicated privacy/retention spec (data classification,
retention, deletion) was approved first, per Constitution Principle
VIII — that gate, not an afterthought, is what real accounts operate
under today.

## How this project is built

Cognivo is spec-driven: no feature's implementation begins without an
approved `spec.md`, followed by a `plan.md` and `tasks.md`, under
`specs/<feature-name>/`. See [`CLAUDE.md`](CLAUDE.md) for the full
workflow this repo follows, and [`roadmap.md`](roadmap.md) for the
milestone sequence and each milestone's definition of done.

## License

[MIT](LICENSE)

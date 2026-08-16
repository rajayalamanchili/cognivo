# Research: Domain-Agnostic Core

**Feature**: `001-domain-agnostic-core` | **Date**: 2026-08-15

Resolves every `NEEDS CLARIFICATION` left open by `tech-stack.md` for this
milestone. Each decision recorded here is also mirrored into
`tech-stack.md` so it becomes the locked, cross-feature record per the
Constitution's Technology Constraints section.

## 1. Mastery model algorithm

**Decision**: Bayesian Knowledge Tracing (BKT), with fixed global
parameters (not per-topic-fitted), computed per learner/topic:

- `p(L0)` (prior probability of mastery before any evidence) = 0.3
- `p(T)` (probability of transitioning from not-mastered to mastered
  after one assessment opportunity) = 0.1
- `p(S)` (slip -- probability of an incorrect answer despite mastery) =
  0.1
- `p(G)` (guess -- probability of a correct answer despite no mastery) =
  0.25 for multiple-choice (4-option questions), 0.05 for numeric-answer
  questions

A topic with no recorded answer has no BKT state row at all -- it is
represented as "unknown" (FR-005), never as `p(L0)` itself. `p(L0)` is
used only as the Bayesian prior the first time a topic receives an
answer; every subsequent answer updates from the previous posterior via
the standard BKT update equations. The resulting posterior `p(mastery)`
is what's compared against the 0.4 / 0.7 three-band thresholds
established in `spec.md`'s Clarifications.

**Rationale**: BKT is the leading candidate tech-stack.md already named,
it's a textbook example of Constitution Principle I's "explicit,
inspectable model," and its output is naturally a `[0,1]` probability --
exactly what the three-band mastery model and SC-001's determinism
requirement need. Global (not per-topic-fitted) parameters are the right
scope for this milestone specifically because per-topic parameter
fitting (e.g. via Expectation-Maximization over historical response
data) requires a volume of real learner response data that does not
and, per Constitution Principle VIII, MUST NOT exist yet -- only
synthetic profiles are permitted pre-Milestone-7. Fixed global constants
keep the model fully deterministic and auditable from day one without
overfitting to synthetic seed data that wouldn't generalize anyway.

**Alternatives considered**:
- *Per-topic EM-fitted BKT parameters* -- rejected for this milestone;
  revisit once Milestone 6's real grading data (or a large enough
  synthetic corpus) makes fitting meaningful rather than noise-fitting.
- *A simpler heuristic (e.g. rolling accuracy percentage)* -- rejected;
  it satisfies "deterministic" but not "explainable in probabilistic
  terms an instructor would recognize," and BKT is barely more complex
  to implement correctly.

## 2. LLM provider for structured question generation

**Decision**: Call the LLM through Google ADK's `LiteLlm` model wrapper
(ADK's documented path for any non-Gemini provider), keeping the
provider itself a runtime configuration value rather than a hardcoded
choice. The default model for local development and the live Vercel
demo deployment is Anthropic Claude (Sonnet), set via an environment
variable (e.g. `ASSESSMENT_GEN_MODEL=anthropic/claude-sonnet-...`).

**Rationale**: The user explicitly chose not to lock a single provider
into code, preferring the LiteLLM abstraction so the choice stays a
config value. A concrete default is still required for SC-007's
post-deploy smoke test and for local development to actually run
end-to-end; Claude was chosen as that default for consistency with the
project's existing Anthropic-centric tooling (`claude-code-action` PR
review gate) and strong structured-output reliability for the
question+answer-key-together generation FR-007 requires.

**Alternatives considered**:
- *Gemini as the hardcoded default, no LiteLLM* -- rejected; ADK's
  native Gemini path is simpler but locks the provider into code,
  which the user explicitly wanted to avoid.
- *No default, provider required at deploy time with no fallback* --
  rejected; SC-007's automated smoke test needs a working default to
  run without manual per-environment setup.

## 3. Near-duplicate question detection (FR-008)

**Decision**: A lightweight, in-process text-similarity check (TF-IDF
cosine similarity, or Python's `difflib.SequenceMatcher` ratio, over the
generated question's stem text) comparing a newly generated question
against the learner's last 5 generated questions for that topic
(per the Clarifications session). No vector database or embeddings API
call is introduced for this.

**Rationale**: `pgvector`-backed semantic embeddings are already locked
in `tech-stack.md`, but explicitly scoped to the Tutor Agent's
Milestone 9 retrieval-grounding need. Pulling that infrastructure
forward into Milestone 1 for a 5-question lookback window would be
exactly the kind of premature-dependency introduction
`tech-stack.md`/Constitution Principle III's sibling constraint (avoid
undeclared stack expansion) warns against, for no proportionate benefit
-- a 5-item text-similarity comparison is cheap enough to run in-process
on every generation call with no new infrastructure, and is fully
deterministic and explainable (FR-010).

**Alternatives considered**:
- *pgvector embedding similarity now* -- rejected; premature
  infrastructure pull-forward from Milestone 9, no proportionate benefit
  at a 5-question window size.
- *Exact-text-match only* -- rejected; spec's Edge Cases section
  explicitly calls out near-duplicates that are not text-identical as a
  real risk to catch.

## 4. Testing frameworks

**Decision**:
- Backend (Python/FastAPI/ADK): `pytest`.
- Frontend (Next.js/TypeScript) component/unit tests: `Vitest` +
  `React Testing Library`.
- Deployment smoke test (SC-007) and full-flow end-to-end validation:
  `Playwright`, run against the live Vercel deployment URL after every
  deploy.

**Rationale**: `pytest` is the de facto standard for FastAPI/Python
projects and integrates cleanly with ADK's Python-first design.
Vitest+RTL is the standard modern pairing for Next.js component tests
(faster than Jest, no extra config beyond what Next.js already expects).
Playwright is chosen for SC-007 specifically because it drives a real
browser against the real deployed URL -- the most faithful check of
Constitution Principle IX's "deployable and demoable," not just "the
API responds correctly."

**Alternatives considered**:
- *Jest instead of Vitest* -- rejected; no material advantage for a
  fresh Next.js project, and Vitest's faster iteration loop is a better
  default going forward.
- *A plain `requests`/`httpx` script instead of Playwright for SC-007*
  -- rejected; it would verify the API but not the actual clickable
  demo experience Constitution Principle IX cares about.

## Summary of items resolved

| Item | Resolution |
|---|---|
| Mastery model algorithm | BKT, fixed global parameters (§1) |
| LLM provider | LiteLLM abstraction, Claude Sonnet default (§2) |
| Near-duplicate detection | In-process text similarity, 5-question window (§3) |
| Backend testing | pytest |
| Frontend testing | Vitest + React Testing Library |
| Deployment smoke test | Playwright |

All `NEEDS CLARIFICATION` markers from the plan template's Technical
Context are resolved by the decisions above combined with
`tech-stack.md`'s already-locked choices.

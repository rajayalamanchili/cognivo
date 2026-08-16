# Cognivo

A domain-agnostic, AI-powered learning platform that personalizes
sequencing based on a real mastery model, generates assessments
dynamically, grades free-text answers against a rubric, flags weak areas
with concrete next-step suggestions, and tutors conversationally -- for
an instructor-configured classroom, not just a solo learner.

See `.specify/memory/constitution.md` for governing principles,
`roadmap.md` for the milestone sequence and each milestone's definition
of done, and `tech-stack.md` for locked technology decisions.

## How to work in this repo

- **This is spec-driven, per Constitution Principle VII.** No feature's
  implementation begins without an approved `spec.md` under
  `specs/<feature-name>/`, followed by `plan.md` and `tasks.md`.
- **Always run `/speckit-analyze` before `/speckit-implement`.** Report
  what it flags against `.specify/memory/constitution.md`; don't
  silently proceed past a flagged violation.
- **Check `roadmap.md` before starting work.** It's the source of truth
  for milestone order and dependencies -- this order can change as scope
  is added mid-project, so don't assume an earlier conversation's
  milestone numbering is still current without checking the file.
- **`tech-stack.md` is locked, not a suggestion.** Don't introduce an
  alternate agent framework, database, or frontend stack without first
  updating `tech-stack.md` and stating why. This includes the Vercel
  deployment target (Principle IX) -- don't introduce a dependency or
  pattern that assumes a persistent server process without checking it
  against Vercel's serverless execution model first.
- **Never push or merge directly to `main` or `staging`** (Constitution
  Principle X). All work happens on a feature branch, PR'd into
  `staging` first. Promotion from `staging` to `main` is its own,
  separate PR -- don't fold a promotion into a feature PR. Wait for the
  automated `anthropics/claude-code-action@v1` review check to pass on
  every PR before treating it as mergeable, even if a human has already
  approved it.

## Non-negotiable engineering rules (see the constitution for full rationale)

- **Personalization is a model, not a guess** (Principle I). The
  Sequencing Agent's mastery state must come from an explicit,
  deterministic statistical model called as a tool -- never an LLM's
  freeform impression of a conversation.
- **Generated content is graded against a rubric, never vibes**
  (Principle II). Every generated question ships with its own answer
  key or rubric, generated alongside it, before it's ever shown to a
  learner.
- **One engine, many subjects** (Principle III). If you find yourself
  writing a subject-id-keyed conditional anywhere outside a content
  artifact's own directory, stop -- that's the exact anti-pattern this
  architecture exists to prevent.
- **Agent boundaries reflect real responsibility, not decoration**
  (Principle IV) and **A2A is justified by a concrete need, not adopted
  by default** (Principle VI). Don't split an agent out as a remote A2A
  service, or even as a separate local sub-agent, without being able to
  state the specific independent-evaluation or independent-versioning
  need that justifies it.
- **Every personalization and grading decision is logged and
  explainable** (Principle V). "Why was I shown this" and "why was this
  marked wrong" must both have real, traceable answers.
- **No real learner data until privacy/retention is specified**
  (Principle VIII). This is a real classroom product plausibly involving
  real minors' data, which is a higher-stakes data-handling problem than
  most AI-product prototypes take on by default. Synthetic learner
  profiles only until Milestone 7's dedicated spec is approved.
- **Deployable and demoable from the start** (Principle IX). Every
  architectural choice must account for Vercel's stateless, ephemeral
  serverless execution model -- no in-memory session state, no
  persistent background process assumed anywhere.
- **Staged release discipline** (Principle X). `staging` and `main` are
  both long-lived; nothing lands on either via a direct push. Promotion
  `staging` → `main` is its own reviewed PR, and every PR in either
  direction needs the automated review check to pass -- a human
  approval doesn't substitute for it.
- **Demo accounts are explicitly flagged, always** (Principle VIII,
  extended). Never create a seeded/demo account without setting
  `is_demo` at creation time, and never let a demo account be reachable
  through the same path as real sign-up. If you're implementing
  anything that creates an account and you're not sure whether it's a
  demo account, that uncertainty itself is the bug -- the flag must be
  explicit, not inferred.

## When something seems ambiguous or underspecified

Prefer surfacing the ambiguity and proposing `/speckit-clarify` over
guessing and implementing -- especially for anything touching the
mastery model's algorithm, grading rubric design, or the boundary
between what's a local ADK sub-agent vs. a remote A2A service.

## Useful context for any session

- Current milestone: **Milestone 1** -- domain-agnostic content schema,
  structured-only assessment, single-learner mastery model. See
  `specs/001-domain-agnostic-core/spec.md` for full scope.
- Two subjects' content artifacts are required in Milestone 1 itself
  (not deferred to a later milestone) specifically to prove the
  domain-agnostic claim early -- see that spec's Assumptions for the
  reasoning.
- Milestone 1 must be deployed and demoable on Vercel, not just runnable
  locally -- see `tech-stack.md`'s deployment-target section for the
  concrete constraints this places on session/state management.
- Every agent invocation must emit a Langfuse trace from Milestone 1
  onward (Constitution Principle V, `tech-stack.md`'s Observability
  section) -- this is separate from, and in addition to, the pedagogical
  audit log. Don't treat one as satisfying the other.
- The Recommendation Agent (Milestone 2) is a distinct agent from
  Sequencing, not a renamed version of it -- Sequencing picks the single
  next question in real time; Recommendation synthesizes a broader
  weak-area report on request. Their test suites must stay independent
  (spec.md 002's FR-009/SC-005) -- if you find yourself reusing
  Sequencing's fixtures for a Recommendation test, that's a signal the
  boundary is being treated as decorative, which Constitution Principle
  IV specifically prohibits.
- The Learner Dashboard (Milestone 4) and Adaptive Difficulty Quiz
  (Milestone 5) both round out the solo-learner experience before the
  platform's scope broadens. Notably: the Quiz feature does NOT
  introduce a sixth agent -- its in-quiz difficulty adjustment is new
  logic layered on the existing Assessment-Generation Agent, not a new
  agent boundary (see spec 005's Assumptions for why that would fail
  Constitution Principle IV's bar).
- The Grading Agent (Milestone 6) is this project's first anticipated
  real A2A service; Diagnostic, Sequencing, Assessment-Generation,
  Recommendation, and the Quiz feature's in-quiz logic all stay local to
  ADK sub-agents/existing agents unless a concrete need to split
  something out emerges.
- The Instructor Classroom milestone (Milestone 7) was extended beyond
  its original scope to also own two things that previously had no
  home: an instructor dashboard (must aggregate Milestone 2's
  Recommendation Agent output, never re-implement weak-area detection)
  and the content-review workflow for questions flagged via Milestone
  1's FR-011, which existed as a requirement long before anything owned
  reviewing the flags it produces. Instructor-assigned quizzes were
  deliberately pulled out into their own Milestone 8, rather than piled
  onto Milestone 7 too -- that milestone was already carrying five axes
  before this one would have made six.
- The Tutor Agent (Milestone 9) carries two capabilities beyond its
  original A2A-delegation scope: vector-grounded retrieval via
  `pgvector` (so answers are grounded in real content-artifact material,
  not freeform generation) and token-by-token streaming. Both are
  properties of this agent's response generation specifically -- they
  don't get their own milestones because neither is independently
  useful before the Tutor Agent itself exists.
- Multimodal support (Milestone 10) is deliberately scoped to image
  stimuli only -- a question displaying a pre-supplied image, with
  grading staying exactly as deterministic as a text-only question.
  Don't let "multimodal" scope-creep into audio, video, learner-
  submitted images, or AI-generated images without a new spec; each is
  explicitly named as deferred in that milestone's Assumptions for a
  reason (each introduces a genuinely different, harder problem).
- "Tutor" in this project's product language refers to the human
  instructor role (Milestone 7) once it exists; the AI **Tutor Agent**
  (Milestone 9) is a separate, distinct concept. Prefer "instructor" for
  the human role in code and docs to keep the two unambiguous.
- Demo accounts exist at two points: a lightweight seeded demo learner
  profile from Milestone 1 onward (so the live deployment isn't an
  empty state for a first-time visitor), and full seeded instructor +
  student demo accounts from Milestone 7 onward (once real auth and real
  accounts exist at all).
- Milestones 11-13 (Fine-Tuned Misconception Classifier, Prompt
  Versioning, Semantic Caching) are sequenced last deliberately -- each
  is engineering depth on an already-complete product, not a gap in core
  functionality, the same reasoning applied to Multimodal (Milestone
  10). Don't let urgency to "close AI-stack gaps" pull any of these
  earlier than their stated dependencies allow -- Milestone 11 needs
  Milestone 6's real grading data, Milestone 13 needs Milestone 12's
  versioning to exist first so cache entries can be tied to a specific
  prompt version. Both must carry the explicit `is_demo` flag
  and the persistent UI badge defined in `tech-stack.md` -- see
  Constitution Principle VIII.

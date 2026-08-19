# Roadmap

**Project**: Cognivo
**Governing rule**: per the constitution's Development Workflow section,
a milestone does not begin until the previous milestone's `spec.md`
Success Criteria are met.

**Cross-cutting from Milestone 1 onward**: per Constitution Principle X,
the `staging`/`main` branch model and the automated PR review gate
(`anthropics/claude-code-action@v1`, see `tech-stack.md`) are
repository-level infrastructure, not a milestone's feature scope -- they
must exist before Milestone 1's own work is considered done, and every
milestone from here forward is expected to use them, not just the ones
that happen to mention them explicitly.

---

## Milestone 1: Domain-Agnostic Core -- Content Schema, Structured Assessment, Mastery Model
**Spec**: `specs/001-domain-agnostic-core/spec.md`
**Status**: Complete (2026-08-16). All Definition of Done items below
are met and verified against a live Vercel deployment, not only local
development -- see `specs/001-domain-agnostic-core/tasks.md`'s Phase 6
notes for the verification record.

**Scope**: Subject-agnostic content-artifact schema; Diagnostic Agent
(placement) and Sequencing Agent (explicit, deterministic mastery model
+ next-topic selection) as local ADK sub-agents; Assessment-Generation
Agent producing structured (multiple-choice/numeric) questions with
validated answer keys; deterministic grading of structured answers; a
second subject's content artifact proving the engine is genuinely
subject-agnostic from day one; Langfuse tracing on every agent
invocation; one or more clearly-flagged demo learner profiles so the
live deployment has something to show a visitor; a live Vercel
deployment of the whole flow, per Constitution Principles V, VIII, and
IX.

**Definition of done**:
- All acceptance scenarios in `spec.md` pass.
- SC-001 (mastery determinism), SC-003 (question validation), and SC-004
  (extensibility, zero engine-file changes for a second subject) are all
  hard gates with automated checks, not verified by inspection -- built
  from the start rather than promised now and added later.
- SC-005 (degenerate answer pattern doesn't fake mastery) has a specific
  test, not just a plausible-sounding claim.
- The full placement-through-first-question flow works end to end on the
  live Vercel deployment, not only in local development -- verified by
  the deployment smoke test defined in `tech-stack.md`.
- The `staging`/`main` branch structure and the automated PR review gate
  (Constitution Principle X) are in place and enforced by branch
  protection before this milestone's own work is merged -- this is
  infrastructure the whole project depends on, not a nice-to-have added
  after the fact.
- At least one demo learner profile is seeded, marked with the explicit
  `is_demo` flag and the persistent UI badge defined in `tech-stack.md`,
  and is what the live Vercel deployment shows a first-time visitor --
  not an empty state.

**Explicitly not included**: free-text grading, the Grading Agent, any
A2A remote service, instructor/classroom features, real learner data,
the Tutor Agent, dashboards, quizzes.

---

## Milestone 2: Recommendation Agent -- Weak-Area Flagging and Next Steps
**Spec**: `specs/002-recommendation-agent/spec.md`
**Status**: Implemented and merged (PR #10) -- 26/27 tasks complete;
the sole remaining item (`tasks.md` T027, live-deployment quickstart
validation) is explicitly deferred to a maintainer running it against a
real Vercel URL, not a code gap. (This status line, and `spec.md`'s own
header, were left stale after merge -- corrected here alongside the
Milestone 3 promotion that surfaced the discrepancy.)

**Scope**: A Recommendation Agent that analyzes a learner's mastery
state and assessment-event history to flag weak areas (each with cited
evidence, never a bare claim) and suggest concrete, prerequisite-aware
next steps -- the direct implementation of the original product
requirement to "analyze performance data to flag weak areas and suggest
next steps." Deliberately proven as a distinct responsibility from the
Sequencing Agent, with its own independent test suite, per Constitution
Principle IV.

**Why this comes before free-text grading**: This agent only needs
Milestone 1's mastery-state and assessment-event data model to exist --
it doesn't depend on free-text grading, A2A, or classroom features. It's
also a more central piece of the original product's value proposition
than grading nuance, so it's sequenced earlier.

**Definition of done**:
- All acceptance scenarios in `specs/002-recommendation-agent/spec.md`
  pass.
- SC-002 (every weak-area flag cites real evidence) and SC-005 (this
  agent's test suite is independent of Sequencing's) are hard gates --
  the first because an unsupported "weak area" claim is exactly the kind
  of ungrounded AI output this project's constitution exists to prevent,
  the second because it's the concrete proof that this agent's boundary
  is real, not decorative.
- Milestone 1's full acceptance-scenario suite still passes (regression
  check).

**Explicitly not included**: instructor/classroom aggregation across a
roster (Milestone 7 consumes this agent's output rather than
duplicating its logic); external-resource recommendation.

---

## Milestone 3: Real Personalization Signal -- Does Sequencing Actually Help?
**Spec**: `specs/006-personalization-eval/spec.md`
**Status**: Implemented (harness + report page); real population-scale
validation of the DoD's core claim (below) still outstanding -- see PR
#11 and that spec's `tasks.md` T031/T032.

**Sequencing note**: M3's original PR review flagged an apparent
sequencing violation ("do not begin until Milestone 2 DoD is met"),
based on this file's Milestone 2 entry, which at the time still read
"Spec drafted, pending `/speckit-clarify` and `/speckit-plan`." That
status line was stale, not current: Milestone 2 (PR #10) had already
been fully implemented and merged into `staging` before Milestone 3's
branch was created -- `spec.md`'s own status header just hadn't been
updated after that merge either (both corrected 2026-08-18, during the
`staging` -> `main` promotion that surfaced the discrepancy). So there
was no actual sequencing violation; the concern was an artifact of two
stale status lines, not a real out-of-order implementation. Left here
as a reminder to update a milestone's roadmap/spec status line in the
same PR that completes it, not after.

**Scope**: An evaluation harness that simulates synthetic learner
populations (with known, simulated true mastery) and measures whether
the Sequencing Agent's chosen order reaches target mastery faster than a
random or fixed-order baseline. This is the milestone that makes
"personalizes based on what you know" a measured claim instead of an
assumed one.

**Definition of done**:
- The simulated-learner evaluation harness shows the Sequencing Agent's
  ordering reaching target mastery in fewer questions than a random
  baseline, across multiple synthetic learner profiles (not cherry-picked
  ones), at `specs/006-personalization-eval/research.md` §10's full
  population scale (30 learners x 4 profiles x 2 subjects) -- **not yet
  demonstrated**; only small-scale (n=1-3) live spot checks and scripted
  unit fixtures exist so far (`tasks.md` T031/T032).
- Milestones 1 and 2's full acceptance-scenario suites still pass
  (regression check) -- both were already merged before Milestone 3
  began (see Sequencing note above).

---

## Milestone 4: Learner Dashboard
**Spec**: `specs/004-learner-dashboard/spec.md`
**Status**: Complete (2026-08-18). All 31 tasks across 4 user stories
implemented and merged to `staging` (PR #14), then promoted to `main`
(PR #15). `specs/004-learner-dashboard/tasks.md`'s Phase 7 records
`quickstart.md`'s 10 validation scenarios run end to end against a
freshly migrated and seeded dev database, not only local development.

**Scope**: A learner-facing dashboard surfacing per-topic mastery, the
Recommendation Agent's freshly-generated weak-area report and next-step
suggestions, and an illustrative (explicitly not-a-fixed-plan) path
visualization showing topics completed, current focus, and likely
upcoming topics.

**Why this comes after the personalization-eval milestone**: Surfacing
a "personalized path" to a learner is more honest to ship once
Milestone 3 has actually measured that the personalization works, not
before.

**Definition of done**:
- All acceptance scenarios in `specs/004-learner-dashboard/spec.md`
  pass.
- SC-003 (weak-area section matches a direct Recommendation Agent call)
  and SC-004 (100% of "upcoming topics" sections carry the
  illustrative/subject-to-change disclosure) are hard gates -- the first
  because a dashboard silently drifting from the agent it's supposed to
  reflect is worse than no dashboard, the second because presenting an
  adaptive system's one-decision-at-a-time reality as a fixed plan would
  misrepresent how the product actually works.
- Milestones 1-3's full suites still pass.

---

## Milestone 5: Adaptive Difficulty Quiz
**Spec**: `specs/005-adaptive-quiz/spec.md`
**Status**: `/speckit-implement` complete (35/35 tasks). All 10
`quickstart.md` validation scenarios (T035) verified against the live
dev DB with real Claude generation calls, 40/40 quiz tests plus the
full 177-test backend suite passing with no regressions (2026-08-18).

**Scope**: A bounded, named quiz session (learner-chosen topic(s) and
question count) where difficulty adapts within the session based on
in-quiz performance, reaching a defined completion state with a score --
and feeding every answered question back into the learner's persistent
mastery state via the exact same mechanism as a regular question, so a
quiz is never a disconnected side activity.

**Why this is sequenced here**: Only depends on Milestone 1
(Assessment-Generation Agent, difficulty bands) -- placed alongside the
Learner Dashboard to complete a full, compelling solo-learner experience
before the platform's scope broadens into grading depth (Milestone 6)
and multi-tenancy (Milestone 7).

**Definition of done** (draft, to be formalized in its own `spec.md`):
- All acceptance scenarios in `specs/005-adaptive-quiz/spec.md` pass.
- SC-001 (deterministic difficulty progression and score) and SC-002
  (100% of in-quiz questions verified to also update persistent mastery
  state) are hard gates -- the first is Constitution Principle I applied
  to a new session type, not an exception to it; the second is what
  keeps a quiz from becoming a second, inconsistent source of truth
  about what a learner knows.
- Milestones 1-4's full suites still pass.

**Explicitly not included**: instructor-configured or instructor-
assigned quizzes (built in Milestone 8, once Milestone 7's roster/auth
exists).

---

## Milestone 6: Free-Text Grading via a Real A2A Service
**Spec**: `specs/007-grading-agent/spec.md`
**Status**: `/speckit-implement` in progress. Phases 1-3 of 6 complete
(setup, foundational schema/content/agent-skeleton, and User Story 1 --
free-text questions are generated, guarded, graded via a real A2A call
to the Grading Agent, and update mastery state, including inside a quiz
session). Phase 3's guardrail/grading/A2A-client code has not yet been
run against a live Postgres instance or a live Grading Agent deployment
in this sandbox (no `DATABASE_URL`/Docker available) -- integration
tests are written and collect cleanly but remain unexecuted pending a
live-DB validation pass (deferred to T046 per `tasks.md`). User Stories
2-3 (Phases 4-5) and Polish (Phase 6, including the live SC-005
deployment demonstration) remain.

**Scope**: The Grading Agent, built as an independently deployable A2A
service per Constitution Principle VI's justification (independent
rubric versioning and evaluation without redeploying the rest of the
system). Free-text answers are graded against the same
generated-alongside-the-question rubric pattern established in
Milestone 1 for structured answers (Constitution Principle II), not
freeform LLM judgment.

**Definition of done** (draft):
- Grading accuracy/consistency is measured against a hand-labeled
  ground-truth set of (question, learner answer, expected grade) triples
  -- eval results are a merge gate, not a nice-to-have.
- The Grading Agent's A2A boundary is demonstrated to actually deliver
  its stated justification: a rubric change can be deployed to Grading
  alone, verified not to require touching any other agent's deployment.
- Milestones 1-5's full suites still pass.

**Explicitly not included**: instructor/classroom features, the Tutor
Agent's full A2A delegation (Milestone 9).

---

## Milestone 7: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review, Real Learner Data Gate
**Spec**: not yet written -- do not begin until Milestone 6 DoD is met.
**Status**: Not started.

**Scope**: Instructor-facing classroom features -- roster management;
an instructor dashboard aggregating the Recommendation Agent's
per-learner weak-area output across a class (built by aggregating
Milestone 2's agent output per learner, not by re-implementing weak-area
detection); a content-authoring and review workflow giving an
instructor ownership of the flagged-question mechanism already
established in Milestone 1 (FR-011), which currently has no defined
owner; seeded demo accounts (one instructor, at least one student),
explicitly flagged and visibly distinguishable from real accounts per
Constitution Principle VIII, reachable via a dedicated demo entry point
separate from real sign-up -- and, as a hard prerequisite per
Constitution Principle VIII, the dedicated privacy/retention spec that
must exist and be approved before any real (non-synthetic) learner data
is permitted anywhere in the system.

**Why this comes late, deliberately**: This axis is the one most
orthogonal to the AI-engineering substance of the project (auth,
multi-tenancy, roster CRUD are standard SaaS-building work, not
AI-specific) and the one most likely to balloon into generic
product-building if front-loaded. Deliberately kept to auth, rosters,
dashboard, content review, and the privacy gate only -- instructor-
assigned quizzes are pulled out into their own Milestone 8 specifically
so this milestone doesn't absorb yet another axis on top of the five it
already carries.

**Definition of done** (draft):
- The privacy/retention spec is approved before this milestone's other
  work begins -- not written in parallel with feature work, and not
  retrofitted after real data is already flowing.
- The instructor dashboard is verified to aggregate, not duplicate,
  Milestone 2's Recommendation Agent logic -- no separate weak-area
  detection code path.
- Seeded demo instructor and student accounts exist, carry the explicit
  `is_demo` flag and persistent UI badge, are reachable only via the
  dedicated demo entry point (never indistinguishable from a real
  sign-up), and reset to a known-good state on the schedule defined in
  `tech-stack.md` -- verified by an automated check that no account
  reachable via the real sign-up flow can ever have `is_demo` set to
  true.
- Milestones 1-6's full suites still pass.

---

## Milestone 8: Instructor-Assigned Quizzes
**Spec**: not yet written -- do not begin until Milestone 7 DoD is met.
**Status**: Not started.

**Scope**: Extends the Adaptive Difficulty Quiz (Milestone 5) so an
instructor can configure and assign a specific quiz (topic(s), question
count, optionally a due date) to some or all of their roster, rather
than only the learner-initiated quizzes Milestone 5 covers. Assigned-quiz
results appear broken out per student in the instructor dashboard
established in Milestone 7.

**Why this is its own milestone, not folded into Milestone 5 or 7**:
It strictly depends on both Milestone 5 (the quiz mechanism itself) and
Milestone 7 (roster/auth) existing -- it cannot be built before either.
Giving it a separate milestone, rather than adding it to Milestone 7's
already-substantial scope, keeps that milestone from absorbing a sixth
axis on top of auth, rosters, dashboard, content review, demo accounts,
and the privacy gate it already carries.

**Definition of done** (draft, to be formalized in its own `spec.md`):
- An instructor can assign a quiz (topic(s), question count) to a chosen
  subset of their roster, and assigned-quiz results appear per student
  in the instructor dashboard, not only as an aggregate number.
- Assigned-quiz grading and mastery-update behavior are verified
  unchanged from Milestone 5 and Milestone 6's existing mechanisms --
  this milestone introduces no new grading logic, only assignment and
  reporting.
- Milestones 1-7's full suites still pass.

**Explicitly not included**: quiz templates or reuse across terms/
semesters (a plausible future idea, not required to prove
instructor-assigned quizzes work at all).

---

## Milestone 9: Tutor Agent -- Full A2A Delegation, Vector-Grounded Retrieval, and Streaming Responses
**Spec**: not yet written -- do not begin until Milestone 8 DoD is met.
**Status**: Not started.

**Scope**: The conversational Tutor Agent, answering plain-English
questions and delegating to the Sequencing Agent ("what does this
learner already struggle with?"), the Recommendation Agent, and
potentially the Grading Agent via A2A, tying the multi-agent system
together end to end -- plus two capabilities that only make sense once
this agent exists at all:
- **Vector-grounded retrieval**: the Tutor Agent retrieves relevant
  content-artifact material (via pgvector, see `tech-stack.md`) before
  answering, so its answers are grounded in the subject's actual content
  rather than freeform generation with no retrieval step -- directly
  reducing hallucination risk in exactly the agent where that risk is
  highest.
- **Streaming responses**: the Tutor Agent's answers stream
  token-by-token to the learner rather than waiting for a full response,
  using Vercel/Next.js's native streaming support.

**Why retrieval and streaming are part of this milestone, not their
own**: Both are properties of the Tutor Agent's response generation --
neither is a capability that exists independently of this agent, so
splitting them into separate milestones would create an artificial
dependency chain (a "vector DB milestone" that produces nothing usable
until the Tutor Agent that consumes it also exists).

**Definition of done** (draft, to be formalized in its own `spec.md`):
- The Tutor Agent's delegation to other agents is demonstrated to be
  inspectable, not a black box -- the actual intermediate calls and
  responses are visible, not only the final answer.
- For a defined percentage of test questions, the Tutor Agent's answer
  is verified to cite or ground in specific retrieved content-artifact
  passages, not only plausible-sounding freeform generation -- the
  retrieval step must be shown to matter, not just exist.
- Streaming is verified to render incrementally against the live Vercel
  deployment, not only in local development.
- Milestones 1-8's full suites still pass.

**Explicitly not included**: vector-grounded retrieval for any other
agent (Assessment-Generation, Grading, and Recommendation all operate
directly on structured content-artifact data and don't need it).

---

## Milestone 10: Multimodal Question Stimuli -- Image-Based Questions
**Spec**: `specs/003-multimodal-question-stimuli/spec.md`
**Status**: Spec drafted, pending `/speckit-clarify` and `/speckit-plan`.

**Scope**: Content artifacts can bundle images as question context
(with required alt-text for accessibility); the Assessment-Generation
Agent can produce structured questions that display a bundled image;
grading remains the exact same deterministic answer-key comparison
established in Milestone 1 -- this milestone introduces no new grading
logic. Images work correctly on the live Vercel deployment.

**Why this comes here, deliberately**: This milestone's only real
dependency is Milestone 1 -- it doesn't need any of Milestones 2-9. It's
sequenced this late anyway because it extends the platform's *capability
breadth* rather than deepening the core personalization thesis
Milestones 1-9 establish. Scoped deliberately narrow (image stimuli
only, not audio, video, or learner-submitted images) for the same
reason every other milestone in this roadmap avoids stacking multiple
hard axes at once.

**Definition of done**:
- All acceptance scenarios in
  `specs/003-multimodal-question-stimuli/spec.md` pass.
- SC-002 (100% of image questions have alt text) and SC-003 (missing/
  oversized images fail at content-artifact load time, not at
  question-display time) are hard gates -- the former for accessibility,
  the latter because a validation gap here would surface as a broken
  question in front of a learner instead of a caught error during
  content authoring.
- Milestones 1-9's full suites still pass (regression check).

**Explicitly not included**: audio or video stimuli, learner-submitted
images as answers, AI-generated (rather than pre-supplied) images,
shared/deduplicated image asset libraries across subjects.

---

## Milestone 11: Fine-Tuned Misconception Classifier
**Spec**: not yet written -- do not begin until Milestone 10 DoD is met.
**Status**: Not started.

**Scope**: Using the (question, learner free-text answer, expected
grade) data accumulated since Milestone 6, fine-tune a lightweight
classifier to detect specific, named misconception patterns -- not just
right/wrong, but e.g. "this learner consistently confuses X with Y" --
feeding richer signal into the Recommendation Agent's next-step
suggestions than a bare correctness count can provide.

**Why this is sequenced here**: Strictly depends on Milestone 6 having
accumulated real graded data -- attempting this earlier would mean
fine-tuning on too little or unrepresentative data. Positioned after
Milestone 10 because, like multimodal support, this is engineering
depth rather than a gap in the core product's completeness.

**Definition of done** (draft, to be formalized in its own `spec.md`):
- The fine-tuned classifier's misconception-detection accuracy is
  measured against a hand-labeled validation set and compared against a
  prompted-only baseline -- reported honestly even if the fine-tuned
  model does not outperform the baseline, since that would itself be a
  legitimate, useful finding, not a failure to hide.
- The classifier's output is consumed by the Recommendation Agent
  (Milestone 2) as an optional enrichment -- the Recommendation Agent
  MUST continue to function correctly if the classifier is unavailable
  or not yet trained, i.e. graceful degradation, not a new hard
  dependency on a fine-tuned model existing.
- Milestones 1-10's full suites still pass.

**Explicitly not included**: fine-tuning any other model in the system
(question generation, grading itself, sequencing) -- scoped narrowly to
this one misconception classifier, consumed only by Recommendation.

---

## Milestone 12: Prompt Versioning and Regression Testing
**Spec**: not yet written -- do not begin until Milestone 11 DoD is met.
**Status**: Not started.

**Scope**: Every prompt used by every agent (Assessment-Generation,
Grading, Recommendation, Tutor) is stored as a versioned artifact --
never an inline string literal scattered through code -- with a
regression-test harness that runs each agent's existing eval suite
(Milestone 3's personalization eval, Milestone 6's grading-accuracy
eval) against a candidate prompt change before it can be promoted. Ties
directly into the `staging`/`main` and CI review gate already
established by Constitution Principle X: a prompt change is just another
PR that must pass its relevant eval gate, not a special case that
bypasses it.

**Why this is sequenced here**: Most valuable once most agents and their
prompts already exist (specifically, after the Tutor Agent in Milestone
9) -- versioning a system that's still substantially changing shape
provides less value than versioning a comparatively stable one.

**Definition of done** (draft, to be formalized in its own `spec.md`):
- 100% of agent prompts are stored as versioned artifacts, verified by
  an automated check scanning for inline prompt string literals in
  engine source.
- A deliberately regressed test prompt (scripted to make grading or
  generation quality measurably worse) is verified to be caught by the
  CI gate before merge -- not merely by manual review.
- Milestones 1-11's full suites still pass.

**Explicitly not included**: automatic prompt optimization or
auto-tuning -- a distinct, much larger capability not implied by
"versioning," and not built here.

---

## Milestone 13: Semantic Caching
**Spec**: not yet written -- do not begin until Milestone 12 DoD is met.
**Status**: Not started.

**Scope**: Near-duplicate or semantically similar LLM requests
(question-generation requests for the same topic/difficulty within a
short window, grading of very similar free-text answers) are served
from a cache rather than re-invoking the model, reducing cost and
latency -- extending the near-duplicate-avoidance logic already
established in Milestone 1's FR-008, now applied as a caching strategy
rather than only a "don't show the same thing twice" rule.

**Why this is sequenced last**: Most valuable once call volume is high
enough to matter -- after Grading (Milestone 6) and the Tutor Agent
(Milestone 9) both exist and meaningfully increase LLM call volume
beyond Milestone 1's much lower baseline. Sequenced after prompt
versioning (Milestone 12) since a cache keyed on a specific prompt
version needs that versioning to already exist, or cache entries would
silently survive a prompt change they were never validated against.

**Definition of done** (draft, to be formalized in its own `spec.md`):
- A defined cache-hit-rate target is measured against a synthetic load
  test.
- Cache entries are verified to be invalidated on content-artifact
  version changes -- a cached response must never be served against a
  content artifact it was not generated for.
- Caching is verified not to weaken Constitution Principle I's
  determinism guarantee: a cache hit and a cache miss for the same
  input must be indistinguishable in output, differing only in latency.
- Milestones 1-12's full suites still pass.

**Explicitly not included**: caching that crosses per-learner
near-duplicate history -- caching applies to the underlying generation
call, not to what's ultimately shown to a specific learner, so a cached
question can still be excluded from a specific learner's next question
if they've already seen it recently.

---

## Out of current roadmap (not planned, not rejected)
- A second, cross-language A2A agent purely to demonstrate
  interoperability (e.g. a Go-based Grading service) -- Milestone 6
  leaves the Grading Agent's language undecided rather than defaulting
  to a cross-language choice for its own sake, per Constitution
  Principle VI. Worth revisiting once Milestone 6 is underway and
  there's a concrete reason (team skill, performance) to pick a specific
  language.
- Deployment platforms other than Vercel (e.g. a Kubernetes-based setup
  for the Grading Agent if it later needs resources Vercel Functions
  can't provide) -- not needed unless Milestone 6 planning surfaces a
  concrete constraint Vercel genuinely can't meet.
- Multimodal input beyond image stimuli -- Milestone 10 covers images
  displayed as question context only. Audio or video stimuli,
  learner-submitted images as answers (which would require real
  vision-based grading, not the deterministic comparison Milestone 10
  keeps unchanged), and AI-generated (rather than pre-supplied) images
  are all still deferred, each named explicitly in Milestone 10's own
  Assumptions rather than left ambiguous.
- External-resource recommendation (linking to specific third-party
  videos, articles, or content outside this platform) -- explicitly
  deferred from the Recommendation Agent's scope (Milestone 2) per that
  feature's own Assumptions, since evaluating third-party content
  quality is a distinct problem from evaluating this platform's own
  generated content.
- Quiz templates or reuse across terms/semesters -- explicitly deferred
  from Milestone 8's instructor-assigned quizzes scope, a plausible
  future idea rather than something required to prove the core
  capability works.
- Fine-tuning any model other than the Milestone 11 misconception
  classifier (question generation, grading, or sequencing themselves) --
  explicitly out of that milestone's scope; would need its own spec and
  its own justification if pursued later.
- Automatic prompt optimization/auto-tuning -- explicitly deferred from
  Milestone 12's prompt-versioning scope, a distinct and much larger
  capability.

Keeping this section explicit documents what was considered and
deliberately deferred, rather than leaving it ambiguous whether it was
forgotten.

**Version**: 3.1.0 -- 2026-08-16, Milestone 1 marked complete (deployed
and verified live on Vercel); 3.0.0 (2026-08-15, added Milestones 8
(Instructor-Assigned Quizzes), 11 (Fine-Tuned Misconception Classifier),
12 (Prompt Versioning and Regression Testing), and 13 (Semantic
Caching); extended Milestone 9 (Tutor Agent) with vector-grounded
retrieval and streaming responses; renumbered former Milestones 8-9 to
9-10 accordingly)

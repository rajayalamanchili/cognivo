<!--
Sync Impact Report
- Version change: 1.4.0 -> 1.5.0 (MINOR: materially expanded guidance on
  an existing principle, no principle added/removed/renamed)
- Modified principles:
  - VI. Agent Boundaries Match Deployment Boundaries Where It Earns Its
    Keep -- added an inbound-authentication requirement for any agent
    split out as a network-reachable A2A service, plus rationale tying
    it to the Grading Agent (spec 007) gap that motivated it
- Added sections: none
- Removed sections: none
- Templates/commands requiring follow-up: none checked for this
  amendment beyond the constitution itself (scope guard: this command
  updates only .specify/memory/constitution.md)
- Deferred non-governance items: recording the actual authentication
  mechanism (shared-secret header via env var) as the locked
  implementation pattern in tech-stack.md is intentionally NOT done
  here -- see Next Actions in the command's final summary
-->

# Cognivo Constitution

A domain-agnostic, AI-powered learning platform that personalizes what a
learner sees next based on a real model of what they already know,
generates assessments dynamically instead of pulling from a fixed
question bank, tutors conversationally, and turns performance data into
concrete next steps -- for instructors running a classroom, not just a
solo learner.

## Core Principles

### I. Personalization Is a Model, Not a Guess
The learner's mastery state MUST be maintained by an explicit,
inspectable model (e.g. Bayesian Knowledge Tracing or an equivalent
statistical approach) that the Sequencing Agent calls as a tool -- never
inferred fresh by an LLM guessing from chat context. Given the same
mastery state and the same candidate next-topics, the sequencing decision
MUST be reproducible and explainable ("recommended because mastery on
X is below threshold Y"), not a black box.

**Rationale**: "Personalizes based on what a learner already knows" is a
real claim about a real product. If the mastery model is just an LLM's
impression of the conversation so far, the personalization is
unfalsifiable and untestable -- no test could ever distinguish correct
personalization from a model that's simply agreeable.

### II. Generated Content Is Graded Against a Rubric, Never Vibes
Every dynamically generated assessment question MUST carry an explicit
answer key or grading rubric, generated alongside the question, before
it is ever shown to a learner. Free-text grading MUST evaluate the
learner's answer against that rubric, not against the grading model's
own freeform judgment of "does this seem right."

**Rationale**: Free-text LLM grading is the single highest-risk surface
in this product -- an ungrounded grader can be inconsistent, gameable, or
simply wrong in ways a learner has no way to contest. A rubric makes a
grading decision auditable and appealable rather than a one-off opinion
that changes if you ask the model again.

### III. One Engine, Many Subjects
The platform's core engine (content schema, sequencing logic, assessment
generation, grading) MUST be subject-agnostic. All subject-specific
knowledge (topic graphs, skill definitions, worked examples) MUST live in
versioned content artifacts, never hardcoded into engine source.

**Rationale**: A platform that requires editing core files to add a new
subject will, in practice, never get a second subject added. The
constraint has to be load-bearing from the first subject, not retrofitted
once a second one is wanted, and it needs to be enforced by an automated
check, not by memory or code review alone.

### IV. Multi-Agent Boundaries Reflect Real Responsibility Boundaries, Not Decoration
Every agent (Diagnostic, Sequencing, Assessment-Generation, Grading,
Tutor) MUST exist because it owns a distinct responsibility with its own
evaluation criteria and its own failure modes -- not because using
multiple agents is itself a goal. Where an agent boundary would only add
network/orchestration overhead without a corresponding gain in
independent testability, versionability, or evaluability, the
responsibilities MUST be merged instead of artificially split.

**Rationale**: Multi-agent architecture is justified here specifically
because Grading needs to be independently versioned and evaluated
without redeploying the whole system. That argument only holds if every
agent boundary is held to the same bar -- otherwise this collapses into
agents-for-the-sake-of-agents, which adds latency and failure surface
without adding any real capability.

### V. Every Personalization and Grading Decision Is Logged and Explainable
Every sequencing decision, generated question, and grading outcome MUST
be logged with enough context to answer, after the fact: what mastery
state triggered this, what rubric graded this, and why this was the
system's decision -- not just its output. An instructor or learner MUST
be able to ask "why was I shown this?" or "why was this marked wrong?"
and get a real answer traceable to a specific model state or rubric, not
"the AI decided." Separately, and at a more technical level, every agent
invocation MUST be traced (inputs, outputs, latency, token cost) via an
observability backend -- the pedagogical audit log answers "why this
decision," the trace answers "what actually happened inside the model
call that produced it," and both are required, not interchangeable.

**Rationale**: In an educational context, an unexplainable grading or
sequencing decision isn't just a UX gap -- it undermines a learner's
trust in the whole system and gives an instructor no way to catch a
systemic error before it affects an entire class. Separately, a
multi-agent system with no call-level tracing is nearly undebuggable in
practice once more than one or two agents are involved -- the technical
observability requirement exists for the engineering team's own sake,
not the learner's.

### VI. Agent Boundaries Match Deployment Boundaries Where It Earns Its Keep
Where an agent is split out as a remote A2A service rather than a local
ADK sub-agent, that choice MUST be justified by a concrete need
(independent versioning, independent evaluation, a different language
being the right tool, or genuine horizontal scaling) stated in that
feature's `spec.md` -- never adopted by default because A2A is available.
Any such service, once split out, MUST authenticate inbound requests
(e.g. a shared secret, mTLS, or equivalent) before this project's usual
per-request guardrails (rate limiting, content moderation, length caps)
can be assumed to apply -- independent deployability does not confer
implicit network-level privacy, and a guardrail design that depends on
"only the backend can reach this" MUST NOT be trusted unless that
assumption is actually enforced. The specific authentication mechanism
is a `tech-stack.md` decision, not restated per feature.

**Rationale**: A2A and ADK are tools for a specific architectural
problem (independently evolvable, possibly cross-language agent
boundaries), not a checklist item. A remote-service boundary that exists
only to demonstrate the technology, rather than to solve a real
deployment or evaluation need, adds real cost (latency, operational
surface, failure modes) for no real benefit. The authentication
requirement exists because Milestone 6's Grading Agent shipped this
project's first A2A service as a public, unauthenticated Vercel URL --
none of the backend's guardrails ran inside the agent itself, so anyone
with the URL could bypass every one of them and run up LLM costs
directly. That gap was fixed in code (spec 007, PR #18) but nothing in
this constitution had actually required it; writing it down here closes
it for every future A2A service (starting with Milestone 9's Tutor
Agent) rather than leaving it to be independently rediscovered per
feature.

### VII. Spec Before Code, Milestone-Gated
No feature's implementation begins without an approved `spec.md`,
followed by `plan.md` and `tasks.md`. A milestone does not begin until
the previous milestone's Success Criteria, as written in its `spec.md`,
are met.

**Rationale**: Catching a design gap on paper, before any code exists,
is cheaper than catching it in a security review or a learner-facing bug
after the fact -- and writing the constraint down is what keeps it from
being treated as optional under time pressure.

### VIII. No Real Learner Data Until Privacy and Retention Are Specified
This project MUST NOT ingest real minors' educational data (FERPA/COPPA-
scoped) or any real instructor/institution data until a dedicated spec
covering data retention, deletion, and access-control requirements
exists and is approved. Early milestones MUST use synthetic learner
profiles and synthetic performance histories only. Any seeded demo
account (instructor or student) MUST be clearly, persistently
distinguishable from a real user's account -- both in stored data (an
explicit demo flag, never inferred) and in the UI itself (a visible,
unmissable indicator, not a footnote) -- and MUST NOT be treated as
satisfying this principle's synthetic-data requirement once real users
exist; a demo account remains permanently synthetic, not a stepping
stone to real data.

**Rationale**: This project's eventual real-world use case -- a real
classroom -- plausibly involves real learners who are minors. That is a
materially higher-stakes data-handling problem than most AI-product
prototypes take on by default, and it deserves an explicit gate rather
than being assumed safe because earlier milestones only used synthetic
data. Separately: a demo account that isn't obviously a demo account is
exactly the kind of ambiguity that turns into a real privacy incident --
someone mistaking a real learner's data for a safe-to-share demo, or a
demo account quietly accumulating what looks like real personal
information because nobody could tell it was synthetic.

### IX. Deployable and Demoable From the Start
The product MUST be deployable to Vercel at every milestone boundary,
producing a live, clickable demo -- not a local-only prototype with
deployment deferred to "later." Every architectural choice (agent
framework, session/state management, database) MUST account for
Vercel's serverless execution model (stateless, ephemeral functions with
bounded execution time) rather than assuming a persistent, long-running
server process.

**Rationale**: A project that only runs locally is much harder to
evaluate, share, or demonstrate credibly. Deferring deployment to the
end of a build risks discovering a fundamental architectural mismatch
(e.g. an agent framework assuming in-memory session state) only after
significant work has already gone the wrong direction -- designing for
Vercel's constraints from Milestone 1 avoids that risk entirely.

### X. Staged Release Discipline
The repository MUST maintain two long-lived branches: `staging` and
`main`. All feature work MUST land via a pull request into `staging`
first -- never directly into `main`. Promotion from `staging` to `main`
MUST itself be a reviewed pull request, never a direct push or an
unreviewed fast-forward merge. Every pull request, in either direction,
MUST pass an automated code-review check before it is eligible to merge
-- a human or AI reviewer's approval is necessary but not sufficient on
its own without that automated check also passing.

**Rationale**: `main` is what Constitution Principle IX's live,
demoable Vercel deployment reflects -- `staging` exists to give every
change a place to be validated (including against its own live Vercel
preview) before it reaches what a demo or interview audience would
actually see. An automated review gate on every PR creates a consistent,
unskippable minimum bar rather than a norm that quietly erodes under
time pressure -- exactly the same reasoning that makes this project's
automated Success Criteria checks non-negotiable rather than merely
recommended.

## Technology Constraints

Cross-feature technology choices (agent framework, orchestration
language(s), frontend stack, knowledge-tracing model implementation,
Vercel-specific deployment constraints) are recorded in `tech-stack.md`
at the project root, not restated per feature. A `plan.md` that deviates
from `tech-stack.md` without first amending it fails the Constitution
Check.

## Development Workflow

- `roadmap.md` at the project root records the milestone sequence and
  each milestone's definition of done.
- `/speckit-analyze` MUST be run before `/speckit-implement` for every
  feature, and any flagged violation of this constitution MUST be
  resolved before implementation proceeds.
- Amendments to this constitution require a written rationale and a
  version bump below.

**Version**: 1.5.0 -- Amended 2026-08-20 (Principle VI extended to
require A2A services authenticate inbound requests before backend-owned
guardrails can be assumed to apply)

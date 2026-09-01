# Phase 0 Research: Prompt Versioning and Regression Testing

**Feature**: `022-prompt-versioning` | **Date**: 2026-09-01

## §1. Prompt-artifact storage mechanism

**Decision**: A prompt stays a Python module-level string constant (or a
template constant + builder function, for prompts that interpolate
per-call parameters), paired with a sibling module-level string constant
whose name contains `VERSION`, in the same file as the prompt. No
database table, no third-party prompt-management tool.

**Rationale**: This is the existing, working pattern for both prompts
that already carry a version identifier today (`GRADING_LOGIC_VERSION`
in `grading-agent/src/agent.py`, paired with `prompt_defense.py`'s
`build_instruction()`; `CLASSIFIER_VERSION` in
`backend/src/services/misconception/classify.py`, though that one
versions a joblib model artifact rather than an LLM prompt). Extending
it to every remaining prompt requires zero new infrastructure and keeps
git as the audit trail, consistent with Constitution Principle IX
(no assumption of persistent runtime state) and this project's existing
"code constant, not a DB row" precedent (`agent.py:31-34`'s own
comment). Resolves `tech-stack.md`'s "Prompt-versioning storage
mechanism... Milestone 12 decision."

**Alternatives considered**:
- *Dedicated Postgres table* (`prompt_versions`, keyed by agent + version):
  rejected -- adds a runtime dependency (a DB read on every agent
  construction, or a caching layer to avoid one) to solve a problem git
  already solves for free, and every other "version" in this codebase
  (`GRADING_LOGIC_VERSION`, `CLASSIFIER_VERSION`) is already a code
  constant, not a row. Would also need its own migration and seed data
  for zero behavioral benefit.
- *Third-party prompt-management tool* (e.g. a hosted prompt registry):
  rejected -- a new external dependency and account for a static-content
  versioning need this project's existing tooling (git + a CI scanner)
  already satisfies; also in tension with Constitution Principle IX's
  Vercel-serverless-first posture (an extra network call to fetch a
  prompt at cold start).
- *A structured `PromptArtifact` dataclass wrapping content+version*:
  rejected as an unrequested abstraction -- every prompt already has a
  perfectly good home (its own module); a wrapper class adds a
  constructor/import ceremony around what is, and remains, "a string and
  a version string," identical in spirit to the existing pattern.

## §2. Prompt inventory (what this milestone migrates)

Full source-grounded inventory (file:line cited against the current
tree):

| # | Prompt | File | Current version const | New version const (this milestone) |
|---|---|---|---|---|
| 1 | Assessment-Gen question prompt | `backend/src/agents/assessment_gen/agent.py:78` (`_INSTRUCTION_TEMPLATE`) | none | `GENERATION_PROMPT_VERSION = "v1"` |
| 2 | Grading Agent scoring prompt | `grading-agent/src/prompt_defense.py:21` / `grading-agent/src/agent.py:37` | `GRADING_LOGIC_VERSION = "v2"` | unchanged (already compliant) |
| 3 | Tutor Agent conversational prompt | `tutor-agent/src/agent.py:97` (`_INSTRUCTION`) | none (docstring at `agent.py:43-45` already flags this gap) | `TUTOR_INSTRUCTION_VERSION = "v1"` |
| 4 | Backend moderation guardrail (shared by grading + tutor paths) | `backend/src/services/grading_client/moderation.py:22` (`_INSTRUCTION`) | none | `MODERATION_INSTRUCTION_VERSION = "v1"` |
| 5 | Grading Agent's in-agent moderation guardrail | `grading-agent/src/guardrails.py:50` (`_MODERATION_INSTRUCTION`) | none | `GRADING_GUARDRAIL_MODERATION_VERSION = "v1"` |
| 6 | Tutor Agent's in-agent moderation guardrail | `tutor-agent/src/guardrails.py:49` (`_MODERATION_INSTRUCTION`) | none | `TUTOR_GUARDRAIL_MODERATION_VERSION = "v1"` |
| 7 | Misconception Classifier's baseline-comparison prompt (eval-only; production classification makes no LLM call) | `backend/src/services/misconception/baseline.py:26` | none | `MISCONCEPTION_BASELINE_PROMPT_VERSION = "v1"` |

Sequencing, Diagnostic, and Recommendation Agents make no LLM call at
all (confirmed via grep across their `agent.py` files) -- out of scope,
consistent with Constitution Principle I.

All seven new version constants start at `"v1"` (or, for #2, are already
past it) -- FR-011 requires the migration itself not to change any
prompt's instructional content, so no bump is warranted at migration
time; a version changes only when content next changes.

## §3. Scanner design (FR-001/FR-003): detecting an unversioned inline prompt

**Decision**: An AST-based scanner (`backend/scripts/check_prompt_versioning.py`,
mirroring `check_no_subject_conditionals.py`'s shape and invoked once
per engine-source tree from each tree's own CI workflow) that:
1. Parses every `.py` file under a given root (`backend/src`,
   `grading-agent/src`, or `tutor-agent/src`, passed as a CLI arg).
2. Finds every `LlmAgent(...)` call and reads its `instruction=` keyword
   argument's AST node.
3. Flags a violation if that node is a raw string/f-string literal
   (`ast.Constant`/`ast.JoinedStr`) rather than a reference (`ast.Name`
   or a `Name`-rooted `ast.Call`, e.g. `build_instruction(...)`) to a
   module-level symbol.
4. For a valid reference, resolves the symbol back to the module that
   defines it and requires that module to also define at least one
   module-level string constant whose name contains `VERSION`
   (case-insensitive) -- if none exists, flags a violation citing the
   prompt's location, not the (already-fine) call site.

**Rationale**: Mirrors `check_no_subject_conditionals.py`'s existing
philosophy -- detect at the actual usage site (there: a literal
subject-id string; here: a literal instruction string) rather than
requiring a rigid naming convention. This works uniformly across the
mixed shapes already in the codebase (bare constants like `_INSTRUCTION`
and template+builder pairs like `build_instruction(...)`) with one
script, no per-agent special-casing (Constitution Principle III's
spirit, applied to tooling: one engine-wide check, not per-agent
conditionals). A `VERSION`-substring match (not a fixed suffix like
`_VERSION` exactly) accepts the existing `GRADING_LOGIC_VERSION` name
as-is rather than forcing a rename.

**Alternatives considered**:
- *Naming-convention-only check* (require every prompt constant to end
  in `_INSTRUCTION`/`_PROMPT` and every version to be
  `<same-prefix>_VERSION`): rejected -- more rigid than necessary, would
  force renaming already-fine constants (`GRADING_LOGIC_VERSION` doesn't
  share a prefix with `prompt_defense.py`'s
  `_GRADING_INSTRUCTION_TEMPLATE`), and doesn't generalize to a prompt
  assembled via a builder function the way call-site detection does.
- *Regex-only scan for suspicious string patterns*: rejected -- LLM
  instruction text has no closed-set signature the way subject ids do
  (`check_no_subject_conditionals.py`'s known-set approach doesn't
  transfer); anchoring on the `LlmAgent(instruction=...)` call site
  itself is precise and has zero false-positive risk from unrelated
  strings elsewhere in a file.

## §4. Version-bump enforcement (FR-008)

**Decision**: The same `check_prompt_versioning.py` script, given a
`--base-ref` (the PR's merge-base commit, available in CI via
`git merge-base origin/<base-branch> HEAD`), additionally: for each
prompt-content assignment/function found in §3, diffs its exact source
line range (via `ast`'s `lineno`/`end_lineno`) between `--base-ref` and
the working tree. If that range changed but the paired `VERSION`
constant's own line range did not, fails citing the file and the prompt.

**Rationale**: Satisfies Edge Case #2 exactly (a diff touching the file
for unrelated reasons -- e.g. a comment fix elsewhere -- must not
require a version bump; only a diff touching the prompt's own content
range does). Reuses the same AST parse pass §3 already does, rather than
a separate mechanism -- one script, two related checks, matching this
script's role as a single blocking CI step (FR-004).

**Alternatives considered**:
- *Whole-file diff* (any change to a file containing a prompt requires a
  version bump): rejected -- explicitly fails Edge Case #2's stated
  requirement.
- *Content hashing stored in a manifest file* (a checked-in
  `prompt_hashes.json` compared against current content): rejected --
  adds a generated artifact that must itself be kept in sync (a new
  place to forget to update), when git's own history already gives the
  base-ref comparison needed; more moving parts for the same guarantee.

## §5. Assessment-Generation regression gate in a stateless CI job (FR-005)

**Decision**: Add a `--fresh` mode to the existing
`backend/scripts/batch_eval_questions.py` (default behavior, sampling
already-persisted `GeneratedQuestion` rows, is unchanged and stays
available for local/manual use against a real dev database). In
`--fresh` mode, the script calls the Assessment-Generation Agent's real
generation path directly (the same function `backend/src/api/routes/questions.py`
and `placement.py` already call) for a small fixed sample across this
project's existing two content-artifact subjects, and validates each
result with the same `_validate_draft` used today -- no database read
at all. `backend-tests.yml` runs it in `--fresh` mode as a new blocking
step, with `ANTHROPIC_API_KEY` supplied the same way
`grading-agent-tests.yml` already supplies it to
`check_grading_agent_eval.py`.

**Rationale**: Directly resolves the gap the spec's own Assumptions
section flags (`batch_eval_questions.py`'s DB-sampling approach assumes
accumulated history that a fresh ephemeral-per-PR Neon branch,
per `tech-stack.md`'s environment-provisioning row, does not have).
A fixture-based ground-truth file (mirroring
`grading_ground_truth.jsonl`) doesn't fit this specific check the way it
fits Grading's: internal-consistency validation has no "expected" label
to compare against -- it re-validates the generation pipeline's own
output shape, which is exactly what generating a fresh sample and
re-validating it exercises, end to end, against the real (possibly
just-changed) prompt. One flag on an existing script is a smaller diff
than a new parallel script.

**Alternatives considered**:
- *New fixture file + ground-truth comparison* (mirroring Grading's
  `grading_ground_truth.jsonl`): rejected -- there is no "expected
  question" to author by hand the way there's an expected
  correct/incorrect grading label; internal consistency is a property of
  the generation pipeline's output, not a comparison against a
  pre-labeled answer.
- *Seed the ephemeral CI branch with pre-generated `GeneratedQuestion`
  rows as fixture data, keep the script unchanged*: rejected -- those
  seeded rows would have been generated by whatever prompt version
  existed at seed-authoring time, not the PR's candidate prompt, so
  re-validating them would not actually exercise the changed prompt --
  defeats the point of a regression gate.

## §6. Grading Agent regression gate trigger (FR-006)

**Decision**: No change needed. `grading-agent-tests.yml`'s existing
`paths: ["grading-agent/**", ...]` filter already matches any change to
`grading-agent/src/prompt_defense.py` or `grading-agent/src/agent.py`
(where `GRADING_LOGIC_VERSION` lives), and it already runs
`check_grading_agent_eval.py` as a blocking step on every such PR. FR-006's
"extending that gate's existing trigger condition... if it does not
already [include changed prompt version]" resolves to: it already does.

**Rationale**: Verified directly against the live workflow file rather
than assumed -- avoids adding a redundant, more specific trigger
condition where a broad, already-correct one exists.

## §7. `GeneratedQuestion` schema change (FR-009)

**Decision**: Add `generation_prompt_version: str | None` (nullable, no
default -- every code path that creates a *new* `GeneratedQuestion` is
updated to pass a real version string explicitly; `None` is reserved for
rows that predate this migration) as a new column on the existing
`generated_questions` table, via a standard Alembic migration. Set from
`GENERATION_PROMPT_VERSION` (§2) at the same call sites that already
construct a `GeneratedQuestion` (`backend/src/api/routes/questions.py:100`,
`backend/src/api/routes/placement.py:79`).

**Rationale**: The spec (FR-009, User Story 3) is explicit that the
*record itself* carries the version -- unlike `grading_logic_version`
(which lives in the `answer_submitted` audit-event payload because
grading is a discrete, repeatable event per question), a
`GeneratedQuestion` row already *is* the durable record of one
generation event, so the version belongs directly on it, not on a
separate new `AssessmentEventType`. No existing version-like field
exists on this model today (confirmed by reading
`backend/src/models/generated_question.py`), so this requires a real
migration, not a python-only change. Nullable (not non-nullable) is a
technical necessity, not a preference: `backend-tests.yml`'s ephemeral
CI branch is created with `parent_branch: staging` (a copy-on-write
clone of staging's real accumulated data, not an empty database, per
that workflow's Neon branch-creation step), and `staging`/`main`'s own
`generated_questions` table already holds rows from Milestones 1-11's
live demo/dev usage -- a `NOT NULL` column with no default cannot be
added to a non-empty Postgres table at all, so non-nullable was never
actually buildable here (a gap the original version of this decision,
written before checking that workflow's branch-provisioning step,
missed). `NULL` on a pre-milestone row means exactly "not tracked,"
consistent with FR-009's own "this milestone onward" scoping.

**Alternatives considered**:
- *A new `AssessmentEventType.QUESTION_GENERATED` event carrying the
  version, table unchanged*: rejected -- no such event exists today
  (generation currently only produces the `GeneratedQuestion` row
  itself, plus a separate `NEXT_TOPIC_SELECTED`/`PLACEMENT_QUESTION_SHOWN`
  event that isn't about the generation prompt), and inventing one
  duplicates data already naturally owned by the row being created.
- *Nullable column with a fabricated backfill value (e.g. `"pre-v12"`)
  written to every existing row*: rejected -- FR-009 Acceptance Scenario
  2 only requires new rows carry a real version; there is no requirement
  to retroactively attribute historical rows (which were never versioned
  to begin with, so any backfill value would be a fabrication, not a
  fact) -- SC-003's "100% of questions generated... after this milestone
  ships" is explicit
  about the cutover point.

## §8. CI wiring for the new scanner (FR-004)

**Decision**: Add `check_prompt_versioning.py` as a new step in all
three of `backend-tests.yml`, `grading-agent-tests.yml`, and
`tutor-agent-tests.yml`, each invoking it with that workflow's own
source root (`backend/src`, `grading-agent/src`, `tutor-agent/src`
respectively) and each workflow's path filter gaining
`backend/scripts/check_prompt_versioning.py` as an explicit trigger path
(so a change to the checker itself is caught by CI too) -- the same
pattern `grading-agent-tests.yml` already uses for
`check_grading_agent_eval.py`, a script that also lives outside the
workflow's own path-filtered tree.

**Rationale**: Each engine-source tree already has its own independent
CI workflow (Constitution Principle IV's boundary reflected in tooling);
running the scanner three times, once per tree, from each tree's own
workflow keeps that boundary intact rather than introducing a single
new cross-cutting workflow that would need its own, wider path filter
(and would fire on every PR regardless of which tree it touches).

## §9. No API/contract surface change

**Decision**: No `contracts/` artifact for this feature. Confirmed via
direct inspection of `backend/src/api/routes/questions.py` and
`placement.py` that `generation_prompt_version` is a DB-column-level
addition, not a change to any HTTP response schema returned to the
frontend (mirroring how `grading_logic_version` lives in the
`answer_submitted` audit payload, not the client-facing question
response). This matches the spec's own Assumptions ("No new user-facing
surface... no new UI, API endpoint").

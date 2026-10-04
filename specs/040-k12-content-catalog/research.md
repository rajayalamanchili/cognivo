# Research: Full K-12 Content Catalog

No `NEEDS CLARIFICATION` markers remained in `spec.md`'s Technical Context
after `/speckit-clarify` (grade bands were the one open question, resolved
2026-10-04). Every decision below either outlines the actual content to be
authored, or confirms — by reading the existing engine code, not by new
external research — that a plausible-sounding extra step is not actually
needed.

## Decision 1: Topic outline for Algebra II and Physics

**Decision**: Each new subject gets 8 topics (matching Algebra I's and
Biology's existing count), sequenced prerequisites-before-dependents within
each subject (mirroring `algebra-1/subject.yaml`'s own ordering comment).

Algebra II (`grade_bands: [9, 10]`):
1. `quadratic-equations-and-functions` (9, no prereq)
2. `polynomial-operations` (9, no prereq)
3. `factoring-polynomials` (9, prereq: `polynomial-operations`)
4. `rational-expressions-and-equations` (10, prereq: `factoring-polynomials`)
5. `radical-expressions-and-equations` (10, prereq: `quadratic-equations-and-functions`)
6. `exponential-functions` (10, no prereq)
7. `logarithmic-functions` (10, prereq: `exponential-functions`)
8. `sequences-and-series` (10, no prereq)

Physics (`grade_bands: [9, 10, 11]`):
1. `kinematics-motion-in-one-dimension` (9, no prereq)
2. `forces-and-newtons-laws` (9, prereq: `kinematics-motion-in-one-dimension`)
3. `work-energy-and-power` (10, prereq: `forces-and-newtons-laws`)
4. `momentum-and-collisions` (10, prereq: `forces-and-newtons-laws`)
5. `circular-motion-and-gravitation` (10, prereq: `forces-and-newtons-laws`)
6. `waves-and-sound` (10, no prereq)
7. `electricity-and-circuits` (11, no prereq)
8. `thermodynamics` (11, no prereq)

**Rationale**: This is a standard, defensible scope-and-sequence for both
courses (consistent with how Algebra II and introductory Physics are
actually taught), sized to match the authoring depth this project already
committed to for Algebra I/Biology rather than inventing a new "how many
topics" bar for this feature alone.

**Alternatives considered**: A smaller 4-5 topic "thin slice" per subject
(rejected — would undercut SC-002/SC-003's claim that the new subjects are
real, comparably-complete content, not stub fixtures); a full 15+ topic
deep-dive per subject (rejected — larger than Algebra I/Biology's own
precedent, and this feature is deliberately a pilot, not the final word on
either subject's eventual depth).

## Decision 2: Cross-subject prerequisites are not an engine capability

**Decision**: Algebra II's topics declare no `prerequisites` entry
referencing any Algebra I topic (and likewise Physics declares none
referencing Algebra II). Any real-world dependency (e.g. "Physics' force
problems assume Algebra I's linear-equation solving") is recorded only as
prose in the topic's `skill_definition.summary`, never as a `prerequisites`
list entry.

**Rationale**: Read directly from `src/services/content_artifact/
validator.py` (lines ~132-141): every `prerequisites` entry is checked
against `prereqs_by_topic`, a dict built only from the *current subject's*
topics — a prerequisite entry naming a topic from another subject fails
load-time validation as an unknown prerequisite. This isn't a business
choice to make; it's a hard constraint of how the Sequencing Agent's
per-subject mastery/eligibility model already works (each subject's topic
graph is independent, consistent with Algebra I and Biology never
cross-referencing each other today).

**Alternatives considered**: Extending `prerequisites` to accept a
qualified `subject_id/topic_id` cross-subject reference (rejected outright
— a real engine change, directly contradicting this feature's core claim
of zero engine change, and not requested by spec.md).

## Decision 3: Standards-code format for high-school-level tags

**Decision**: Algebra II cites real Common Core Math high-school strand
codes (e.g. `CCSS.MATH.CONTENT.HSA-REI.B.4`, `CCSS.MATH.CONTENT.HSF-IF.C.8`)
rather than the single-grade-numbered codes Algebra I's grades 6-8 topics
use (e.g. `CCSS.MATH.CONTENT.7.NS.A.1`). Physics cites real NGSS
high-school Physical Science codes (e.g. `HS-PS2-1`, `HS-PS3-2`). Both use
the exact same `{framework, code, title}` shape every existing standards
tag already uses.

**Rationale**: Read directly from `validator.py`'s `_validate_standards`
(lines ~359-403): `code` is only checked for being a non-empty string — no
regex or per-framework format is enforced. Common Core's own high-school
math standards are genuinely organized by strand/cluster rather than a
single discrete grade (unlike grades 6-8, which do have per-grade codes),
so citing the real HS-strand code is both accurate to the actual standard
and requires zero validator change. `Topic.grade` (9 or 10) and the
standard's own code are independent fields already — the validator does
not derive one from the other, so there's no shape conflict to resolve.

**Alternatives considered**: Inventing a synthetic per-grade code to match
Algebra I's pattern cosmetically (rejected — would misrepresent a standard
that doesn't actually exist, and FR-002 requires a *real* standards tag).

## Decision 4: No new or changed API contract

**Decision**: `contracts/` is intentionally left without a new contract
file. No endpoint changes.

**Rationale**: Read `src/services/content_artifact/loader.py` and the
placement/practice/quiz-assignment/instructor-dashboard route handlers —
every one of them resolves `subject_id` against whatever `Subject` rows
exist in the database at request time; none enumerates an allow-list of
known subject IDs anywhere in route or service code. The subject picker on
the frontend likewise renders off a `GET` of loaded subjects, not a
hardcoded list. The two new subjects become reachable the moment their
content artifact is loaded, with no code change on either side.

**Alternatives considered**: None — this was a verification step, not a
design choice with real alternatives.

## Decision 5: Authoring workflow mechanics

**Decision**: "LLM-assisted draft" (FR-004) means the implementing agent
session itself drafts each `subject.yaml` directly during
`/speckit-implement` — the same way this feature's own spec/plan/research
were produced — not a new script, endpoint, or tool that the codebase
ships. The human review step is the normal reviewed pull request every
other content or code change in this repository already goes through
(Constitution Principle X); no new in-app review queue or workflow state
is built.

**Rationale**: `spec.md`'s own FR-004/Assumptions already settled this
("no new UI, workflow state, or authoring tool is built by this feature");
recorded here explicitly so `/speckit-tasks` doesn't accidentally invent a
drafting-tool task that the spec deliberately ruled out.

**Alternatives considered**: A dedicated `backend/scripts/draft_subject_
content.py` that calls an LLM at authoring time to generate a candidate
YAML file (rejected — spec.md's FR-001 clarification picked the two-subject
pilot specifically to avoid building new tooling before the authoring
*approach itself* (not its tooling) is proven; a drafting script is exactly
the kind of "dedicated authoring pipeline/tool" the original `/speckit-
specify` clarification (Q2, Option C) rejected in favor of Option B).

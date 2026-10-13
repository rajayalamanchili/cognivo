# Research: STEM Catalog Expansion (Remaining Six Subjects)

No `[NEEDS CLARIFICATION]` markers remained in `spec.md` -- scope (which
six subjects, what counts as "full catalog") was resolved by this
project's own prior roadmap decision rather than a new clarification
session. Every decision below either outlines the actual content to be
authored, or confirms -- by reading the existing engine code, not new
external research -- that a plausible-sounding extra step is not
actually needed. This feature reuses every mechanism Milestone 040
(Algebra II/Physics pilot) already proved; where a decision below is
identical in kind to one 040 made, that is noted rather than re-argued.

## Decision 1: Topic outline for all six subjects

**Decision**: Each new subject gets 8 topics, matching the depth bar
Algebra I, Biology, Algebra II, and Physics already established
(research.md Decision 1 in `specs/040-k12-content-catalog/`),
sequenced prerequisites-before-dependents within each subject.

**Pre-Algebra** (`grade_bands: [6, 7]`):
1. `ratios-and-proportional-relationships` (6, no prereq)
2. `percentages-and-applications` (6, prereq: `ratios-and-proportional-relationships`)
3. `rational-numbers-and-operations` (6, no prereq)
4. `expressions-and-one-step-equations` (7, prereq: `rational-numbers-and-operations`)
5. `exponents-and-scientific-notation` (7, no prereq)
6. `geometry-area-and-volume` (7, no prereq)
7. `statistics-and-probability-intro` (7, no prereq)
8. `introduction-to-linear-equations` (7, prereq: `expressions-and-one-step-equations`)

**Geometry** (`grade_bands: [9, 10]`):
1. `points-lines-and-planes` (9, no prereq)
2. `angle-relationships` (9, prereq: `points-lines-and-planes`)
3. `triangle-congruence` (9, prereq: `angle-relationships`)
4. `triangle-similarity` (9, prereq: `triangle-congruence`)
5. `the-pythagorean-theorem` (9, prereq: `triangle-similarity`)
6. `quadrilaterals-and-polygons` (10, prereq: `angle-relationships`)
7. `circles-arcs-and-angles` (10, prereq: `angle-relationships`)
8. `area-and-volume-of-solids` (10, prereq: `quadrilaterals-and-polygons`)

**Chemistry** (`grade_bands: [9, 10]`):
1. `matter-and-measurement` (9, no prereq)
2. `atomic-structure` (9, prereq: `matter-and-measurement`)
3. `the-periodic-table` (9, prereq: `atomic-structure`)
4. `chemical-bonding` (10, prereq: `the-periodic-table`)
5. `chemical-reactions-and-equations` (10, prereq: `chemical-bonding`)
6. `stoichiometry` (10, prereq: `chemical-reactions-and-equations`)
7. `gas-laws` (10, prereq: `matter-and-measurement`)
8. `acids-and-bases` (10, prereq: `chemical-reactions-and-equations`)

**Earth Science** (`grade_bands: [6]`):
1. `earths-layers-and-plate-tectonics` (6, no prereq)
2. `rocks-and-the-rock-cycle` (6, prereq: `earths-layers-and-plate-tectonics`)
3. `weathering-erosion-and-deposition` (6, prereq: `rocks-and-the-rock-cycle`)
4. `earths-atmosphere-and-weather` (6, no prereq)
5. `climate-patterns` (6, prereq: `earths-atmosphere-and-weather`)
6. `the-water-cycle` (6, no prereq)
7. `earths-place-in-the-solar-system` (6, no prereq)
8. `natural-resources-and-human-impact` (6, prereq: `weathering-erosion-and-deposition`)

**Elementary Math** (`grade_bands: [1, 2, 3, 4, 5]`):
1. `counting-and-number-sense` (1, no prereq)
2. `addition-and-subtraction-within-20` (1, prereq: `counting-and-number-sense`)
3. `place-value-and-multi-digit-addition` (2, prereq: `addition-and-subtraction-within-20`)
4. `multiplication-and-division-basics` (3, prereq: `place-value-and-multi-digit-addition`)
5. `fractions-as-numbers` (3, prereq: `multiplication-and-division-basics`)
6. `multi-digit-multiplication-and-division` (4, prereq: `multiplication-and-division-basics`)
7. `decimals-and-fraction-operations` (5, prereq: `fractions-as-numbers`)
8. `measurement-and-data` (5, no prereq)

**Elementary Science** (`grade_bands: [1, 2, 3, 4, 5]`):
1. `observing-the-natural-world` (1, no prereq)
2. `plant-and-animal-life-cycles` (1, no prereq)
3. `weather-and-seasons` (2, no prereq)
4. `states-of-matter` (2, no prereq)
5. `forces-and-motion-basics` (3, prereq: `states-of-matter`)
6. `ecosystems-and-habitats` (3, prereq: `plant-and-animal-life-cycles`)
7. `earth-moon-and-sun` (4, no prereq)
8. `energy-and-simple-machines` (5, prereq: `forces-and-motion-basics`)

**Rationale**: 8 topics per subject matches the authoring depth every
prior subject in this catalog (including Milestone 040's pilot) already
committed to -- this feature does not invent a new "how many topics" bar.
Grade spreads follow standard US/Canada course sequencing: Pre-Algebra
immediately precedes this project's own Algebra I band (6-8); Geometry
and Chemistry sit alongside Algebra II/Physics's existing 9-10/9-11
bands; Earth Science uses the common US middle-school (grade 6)
Earth/Space-Science slot; the two elementary subjects span the full
grade 1-5 range in one artifact each, rather than one artifact per
grade, matching how Algebra I already spans three grades (6-8) in a
single subject.

**Alternatives considered**: A thin 4-5 topic slice per subject
(rejected -- would undercut SC-002/SC-003's completeness claim, same
reasoning Milestone 040 gave); splitting each elementary subject into
five single-grade subjects (rejected -- no existing subject in this
catalog is single-grade, and splitting would need five times the
`Subject`/`GradeBand` row overhead for no behavioral gain, since
`Topic.grade` already carries the per-topic grade distinction within
one subject).

## Decision 2: Cross-subject prerequisites remain not an engine capability

**Decision**: No new subject's topics declare a `prerequisites` entry
referencing another subject (e.g. Geometry does not reference
Pre-Algebra; Chemistry does not reference Elementary Science). Any
real-world dependency is recorded only as prose in the topic's
`skill_definition.summary`.

**Rationale**: Identical constraint to Milestone 040's Decision 2, for
the identical reason -- `src/services/content_artifact/validator.py`
validates every `prerequisites` entry only against the current
subject's own `prereqs_by_topic`. Unchanged by this feature; re-stated
here rather than silently assumed, so `/speckit-tasks` doesn't treat it
as an open question.

**Alternatives considered**: None new -- Milestone 040 already
evaluated and rejected a cross-subject-reference engine change.

## Decision 3: Standards-code format per subject

**Decision**: Each subject cites real, per-framework standards codes in
the exact `{framework, code, title}` shape every existing standards tag
already uses:
- Pre-Algebra: Common Core Math grade-numbered codes (e.g.
  `CCSS.MATH.CONTENT.6.RP.A.1`, `CCSS.MATH.CONTENT.7.EE.B.3`) --
  Pre-Algebra sits at grades 6-7, which (like Algebra I's 6-8 band) have
  real per-grade Common Core codes, not high-school strand codes.
- Geometry: Common Core Math high-school Geometry strand codes (e.g.
  `CCSS.MATH.CONTENT.HSG-CO.B.7`, `CCSS.MATH.CONTENT.HSG-SRT.B.5`) --
  same strand-code pattern Milestone 040 used for Algebra II.
- Chemistry: NGSS high-school Physical Science codes (e.g. `HS-PS1-2`,
  `HS-PS1-7`) -- the same NGSS framework Milestone 040 used for Physics,
  since US/Canada chemistry content is organized under the same
  `HS-PS1`/`HS-PS3` performance expectations.
- Earth Science: NGSS middle-school Earth and Space Science codes (e.g.
  `MS-ESS2-1`, `MS-ESS3-1`) -- matching its grade-6 band.
- Elementary Math: Common Core Math grade-numbered codes (e.g.
  `CCSS.MATH.CONTENT.1.OA.A.1`, `CCSS.MATH.CONTENT.3.NF.A.1`) -- the
  same per-grade pattern Algebra I already uses, extended down to
  grades 1-5.
- Elementary Science: NGSS elementary codes (e.g. `1-LS1-1`, `3-PS2-1`)
  -- the first elementary-grade NGSS codes in this catalog.

**Rationale**: Identical validator behavior to Milestone 040's Decision
3 -- `_validate_standards` only checks `code` is a non-empty string, no
per-framework regex. Each subject's real grade band determines whether
real-world standards are organized by single grade (Pre-Algebra,
Elementary Math, Earth Science, Elementary Science) or by high-school
strand/performance-expectation (Geometry, Chemistry) -- citing the
format that actually exists for that grade band, not inventing a
synthetic one for cosmetic consistency.

**Alternatives considered**: None new beyond what Milestone 040 already
rejected (inventing synthetic per-grade codes where none exist).

## Decision 4: No new or changed API contract

**Decision**: `contracts/` documents zero new contract. No endpoint
changes.

**Rationale**: Unlike Milestone 040 (which found and built FR-009's
roster-grade validation as a necessary new contract field), this
feature needs no new engine capability at all -- FR-009 (this spec)
explicitly reuses Milestone 040's existing `grade` field and validation
unchanged. Confirmed by re-reading `src/services/roster/enrollment.py`
and `src/api/routes/rosters.py`: both already handle an arbitrary
subject's `grade_bands`, not a hardcoded list of the four subjects that
existed when FR-009 was built.

**Alternatives considered**: None -- this was a verification step.

## Decision 5: Authoring workflow mechanics

**Decision**: Identical to Milestone 040's Decision 5 -- "LLM-assisted
draft" means the implementing agent session drafts each `subject.yaml`
directly during `/speckit-implement`, reviewed via a normal PR
(Constitution Principle X). No new drafting tool, script, or workflow
state is built by this feature either.

**Rationale**: `spec.md`'s own FR-004 restates Milestone 040's settled
decision verbatim for consistency; recorded here so `/speckit-tasks`
doesn't invent authoring-tooling tasks this feature deliberately
doesn't need, matching Milestone 040's own reasoning for recording this
explicitly.

**Alternatives considered**: None new.

## Decision 6: Elementary grades (1-5) require zero new engine code

**Decision**: Elementary Math and Elementary Science -- the first
subjects in this catalog's history to declare `grade_bands` below 6 --
need no new validation, migration, or adaptive-UI logic.

**Rationale**: Confirmed by reading the actual code, not assumed by
analogy:
1. `GradeBand.__table_args__`'s `ck_grade_bands_grade_range` constraint
   is `grade BETWEEN 1 AND 12` (`src/models/grade_band.py`) -- grades
   1-5 are already a legal range, not an edge case the schema needs
   widening for.
2. `services/roster/enrollment.py`'s `_check_grade_matches_subject`
   (Milestone 040's FR-009) compares a roster's declared `grade` against
   whatever `GradeBand` rows exist for the chosen subject -- it contains
   no lower bound of its own beyond the column constraint above.
3. Milestone 19's `services/mediation/tier.py` `determine_mediation_tier`
   already branches `unlocked_grade <= 2` -> `CO_PRESENT` and
   `unlocked_grade <= 5` -> `CHECK_IN`, both real, already-shipped tiers
   -- not placeholder branches added speculatively for a future subject
   that didn't exist yet. Elementary Math/Science simply exercises these
   branches for the first time with real content.

**Alternatives considered**: None -- this was a verification step, the
same kind Milestone 040's Decision 4 performed for contract changes.

# Grounding Test-Question Set (SC-002)

**Feature**: `012-tutor-agent` | **Purpose**: The fixture SC-002 ("at
least 90% of answers are verified to cite or ground in a specific
retrieved passage relevant to the question") is measured against --
without this, SC-002 has no defined denominator to compute a rate over
(`/speckit-analyze` finding H1). Mirrors Milestone 3's
personalization-eval precedent: a fixture checked into the spec
directory, not generated ad hoc at verification time.

**How to use this fixture (T038)**: for each row, `POST
/api/tutor/sessions` for the given `subject_id` (demo learner is
sufficient), then `POST .../messages` with `question`, then `GET
/api/tutor/exchanges/{id}` and confirm:

1. `grounded: true`.
2. `retrieved_passages` includes at least one passage whose `topic_id`
   matches this row's **Expected Topic**.

A row that fails either check counts against the 90% threshold. Every
question below has real, known coverage in the currently-loaded
`biology`/`algebra-1` content artifacts (`backend/content/*/subject.yaml`)
-- this is the "known content-artifact coverage" SC-002's wording
requires, not an arbitrary question list.

Content artifacts must have passage embeddings generated first
(`scripts/load_content_artifact.py`, research.md §5) -- an empty
`content_passage_embeddings` table would fail every row here for a
reason unrelated to the Tutor Agent itself.

## Biology (`subject_id: biology`)

| # | Question | Expected Topic | Expected Field |
|---|---|---|---|
| B1 | What organelles are found in a eukaryotic cell? | `cell-structure-and-function` | `skill_summary` |
| B2 | Can you identify a single organelle just from what it does? | `cell-structure-and-function` | `difficulty_easy` |
| B3 | What are the four major classes of biomolecules? | `biomolecules` | `skill_summary` |
| B4 | Is glucose a carbohydrate, lipid, protein, or nucleic acid? | `biomolecules` | `difficulty_easy` |
| B5 | Which direction does osmosis move water across a membrane? | `cell-transport` | `skill_summary` |
| B6 | What happens to a cell placed in a hypertonic solution? | `cell-transport` | `difficulty_hard` |
| B7 | What are the three stages of cellular respiration? | `cellular-respiration` | `skill_summary` |
| B8 | How much net ATP does glycolysis produce? | `cellular-respiration` | `difficulty_medium` |
| B9 | How do I predict offspring ratios from a Punnett square? | `mendelian-genetics` | `skill_summary` |
| B10 | What's the genotype ratio when you cross Aa x Aa? | `mendelian-genetics` | `difficulty_easy` |
| B11 | How does transcription turn a gene into a protein? | `dna-replication-and-protein-synthesis` | `skill_summary` |
| B12 | Which DNA base pairs with adenine? | `dna-replication-and-protein-synthesis` | `difficulty_easy` |
| B13 | What happens during the light-dependent reactions of photosynthesis? | `photosynthesis` | `skill_summary` |
| B14 | Why does photosynthesis need light? | `photosynthesis` | `skill_summary` |
| B15 | How does the Hardy-Weinberg equation relate to allele frequencies? | `natural-selection-and-evolution` | `skill_summary` |
| B16 | If the recessive allele frequency q is known, how do I get the recessive phenotype frequency? | `natural-selection-and-evolution` | `difficulty_easy` |

## Algebra I (`subject_id: algebra-1`)

| # | Question | Expected Topic | Expected Field |
|---|---|---|---|
| A1 | How do I add and subtract negative integers? | `integers-and-operations` | `skill_summary` |
| A2 | What's -3 + 7? | `integers-and-operations` | `difficulty_easy` |
| A3 | How do I combine like terms in an expression? | `variables-and-expressions` | `skill_summary` |
| A4 | How do I evaluate 3x + 2 if x is given? | `variables-and-expressions` | `difficulty_easy` |
| A5 | What's the order of operations for evaluating an expression? | `order-of-operations` | `skill_summary` |
| A6 | How do exponents and parentheses interact in order of operations? | `order-of-operations` | `difficulty_medium` |
| A7 | How do I solve a one-step equation like x + 5 = 12? | `solving-one-step-equations` | `skill_summary` |
| A8 | How do I solve an equation that needs two or more steps? | `solving-multi-step-equations` | `skill_summary` |
| A9 | How do I solve a multi-step equation with variables on both sides? | `solving-multi-step-equations` | `difficulty_hard` |
| A10 | What happens to the inequality sign when I multiply by a negative number? | `linear-inequalities` | `skill_summary` |
| A11 | How do I find the slope and y-intercept of a linear equation? | `graphing-linear-equations` | `skill_summary` |
| A12 | How do I tell if a point lies on a given line? | `graphing-linear-equations` | `difficulty_medium` |
| A13 | How do I solve a system of two linear equations? | `systems-of-linear-equations` | `skill_summary` |
| A14 | When should I use elimination instead of substitution for a system? | `systems-of-linear-equations` | `skill_summary` |

**Total**: 30 questions (16 biology + 14 algebra), comfortably above the
">= 20 questions across both subjects" this task requires.

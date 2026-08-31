# Quickstart: Multimodal Question Stimuli

**Feature**: `003-multimodal-question-stimuli` | **Date**: 2026-08-30

Validates that a topic's bundled image renders alongside a generated
question, that grading is unaffected, that a second subject proves the
capability is genuinely engine-agnostic, and that the same flow works
against the live Vercel deployment. See `data-model.md` for entity
detail and `contracts/api.md` for exact request/response shapes.

## Prerequisites

- Same as `specs/001-domain-agnostic-core/quickstart.md` (Postgres,
  seeded `DemoLearnerProfile`) -- plus this feature's migration
  (`Topic.image_asset`, `GeneratedQuestion.image_url`/`image_alt_text`)
  applied via `alembic upgrade head`.
- At least one topic in `content/algebra-1/subject.yaml` and one topic
  in `content/biology/subject.yaml` carry an `image_asset` entry
  (data-model.md), each with a real image file under that subject's
  `content/<subject_id>/images/` directory, reloaded via
  `scripts/load_content_artifact.py`.
- `frontend/public/content-images/` populated by running the frontend's
  `predev`/`prebuild` sync script (research.md §1) -- `npm run dev` or
  `npm run build` from `frontend/` triggers this automatically; no
  manual step needed in the normal flow.

## Run locally

Same as `specs/001-domain-agnostic-core/quickstart.md`'s Run locally
section.

## Validation scenario: an image-based question end to end

Maps directly to spec.md's User Stories and Success Criteria.

1. **Image renders alongside a generated question** (User Story 1,
   FR-004, SC-001)
   `GET /api/learners/{learner_id}/next-question?subject_id=algebra-1`
   for the image-bearing topic -> confirm the response's `image_url`
   and `image_alt_text` are both non-`null`, and that
   `GET {image_url}` against the running frontend returns the image
   file with a `200`.

2. **Grading is unchanged** (User Story 1 Acceptance Scenario 2,
   FR-004, SC-001)
   `POST /api/questions/{question_id}/answer` against the image-based
   question from step 1 -> confirm the response shape and grading
   behavior are identical to a text-only question of the same
   `question_type` (same deterministic answer-key comparison, no new
   fields, no new error cases).

3. **A topic with no image stays text-only** (User Story 1 Acceptance
   Scenario 3)
   Request a question for a topic with no `image_asset` -> confirm
   `image_url`/`image_alt_text` are both `null`.

4. **Missing alt text fails at load time** (User Story 3, FR-003,
   SC-002)
   Reload a content artifact with an `image_asset` entry missing
   `alt_text` -> confirm `scripts/load_content_artifact.py` exits
   non-zero and `Subject.validated_at` is not updated.

5. **Missing, oversized, or wrong-format image fails at load time**
   (Edge Cases, FR-002, SC-003)
   Reload a content artifact whose `image_asset.filename` doesn't
   exist under `images/`, then one exceeding 1 MB, then one with a
   `.gif` extension -> confirm each fails validation with a specific
   error message and no partial write.

6. **Second subject, zero engine changes** (User Story 2, FR-006,
   SC-004)
   Run `backend/tests/integration/test_second_subject.py` (extended to
   cover the biology subject's image-bearing topic) -> confirm it
   passes with no changes to any file outside
   `content/biology/subject.yaml` and `content/biology/images/`.

7. **Live Vercel deployment** (User Story 4, SC-005)
   Repeat step 1 against the deployed `staging` URL -> confirm the
   image loads from the live frontend deployment, not a local dev
   server.

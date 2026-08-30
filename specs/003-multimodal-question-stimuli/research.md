# Research: Multimodal Question Stimuli

## 1. Where image files physically live, and how they reach the learner

**Decision**: Image files live at `backend/content/<subject_id>/images/<filename>`,
git-versioned alongside that subject's `subject.yaml` (FR-005). A tiny
Node script (`frontend/scripts/sync-content-images.mjs`, using only
`node:fs`/`node:path` -- no new dependency) copies every subject's
`images/` directory into `frontend/public/content-images/<subject_id>/`
before Next.js builds. It's wired in as an npm `prebuild`/`predev` hook
(npm runs these automatically before `build`/`dev` without editing
those scripts themselves), so `next build`'s existing static-asset
pipeline picks the copied files up with zero new frontend code beyond
an `<img src="/content-images/{subject_id}/{filename}">` tag. The
public URL is computed once, at question-generation time, as
`/content-images/{subject_id}/{filename}` and stored directly on the
`GeneratedQuestion` row (see data-model.md) -- no runtime path-building
logic needed anywhere else.

**Rationale**: FR-005 locks "served as Next.js static assets... never
written to or read from a local filesystem at runtime, and never
requiring an external storage service or upload step." Next.js's
built-in `public/` static serving satisfies that directly (rung 4 of
the lazy ladder: native platform feature over a new service). The only
gap is that the image's authoritative, git-versioned home
(`backend/content/`) is a different Vercel Service's root
(`vercel.json`'s `services.backend.root`) than the one that serves it
(`services.frontend.root`) -- a one-way build-time copy closes that
gap without introducing a second storage system or a cross-service
runtime call.

**Alternatives considered**:
- *A new FastAPI static route on the backend* (`GET
  /api/content/{subject_id}/images/{filename}`) -- rejected: directly
  contradicts the locked clarification ("served as Next.js static
  assets"), and would require the backend to read from its local
  filesystem at request time, which the Vercel serverless deployment
  model (tech-stack.md) treats as unreliable for anything not baked
  into the deployed function bundle at build time.
- *Vercel Blob or another external storage service* -- explicitly
  rejected by FR-005 itself ("never requiring an external storage
  service").
- *Storing images directly in `frontend/public/`, authored there
  instead of under `backend/content/`* -- rejected: breaks FR-005's
  "bundled inside that subject's own content-artifact directory"
  requirement, and would let a content author add an image without
  touching the artifact that's supposed to be its single source of
  truth (Constitution Principle III).

**Known unverified risk** (documented rather than silently assumed,
matching this project's existing practice for Vercel monorepo
unknowns -- see tech-stack.md's A2A deployment rows): whether Vercel's
build for a `root: "frontend/"` Service in this multi-service project
checks out the full monorepo (making `../backend/content` visible to
the sync script) or only the `frontend/` subtree. If the latter, the
sync script will fail loudly at build time (missing source directory)
rather than silently ship a broken image -- to be confirmed the first
time this milestone actually deploys, the same way Milestone 6 and 9
each discovered a real Vercel-specific gap only at live-deploy time.

## 2. Image format/size validation: extension check, not content sniffing

**Decision**: FR-002's format check (PNG/JPEG/SVG) is a case-insensitive
file-extension check (`.png`, `.jpg`, `.jpeg`, `.svg`) against the
resolved file path; the size check (FR-002, 1 MB) is `Path.stat().st_size`.
Both run in `services/content_artifact/loader.py` (which already touches
the filesystem to read the YAML file itself), not in `validator.py`.

**Rationale**: `validator.py`'s module docstring is explicit that it
"never touches the database or the filesystem" -- every existing caller
and test relies on that separation (schema/graph validation is pure;
loading is impure). Splitting the new checks this way keeps that
invariant intact: `validator.py` still only checks that `image_asset`,
if present, is a mapping with non-empty `filename` and `alt_text`
strings (FR-003, no FS access needed for that); `loader.py` adds the
missing-file/oversized/wrong-format checks that do need FS access.
Content-artifact images are authored, trusted content (the same trust
tier as the YAML topic graph itself, reviewed the same way), not
learner-submitted or otherwise untrusted input -- so a magic-byte
content sniff buys correctness against a threat model (a malicious or
corrupted file pretending to be a PNG) that doesn't apply here, at the
cost of a new dependency (`Pillow`, `python-magic`, or similar) neither
this repo nor its lockfiles currently include for any other purpose.

**Alternatives considered**: `Pillow`-based image verification (`Image.open(...).verify()`,
also confirms real dimensions) -- rejected as a new dependency for a
low-value threat model at this trust tier; revisit if content review
ever needs real image dimensions or a corrupted-file class of bug
actually shows up (`ponytail:` upgrade path, noted in the loader code
itself once written).

## 3. Whether the LLM needs to know an image exists

**Decision**: `agents/assessment_gen/agent.py`'s `generate_question()`
gains one new optional parameter, `image_alt_text: str | None = None`.
When set, the instruction template gets one extra paragraph telling the
model an image will be displayed alongside the question (given only its
alt-text description, never the pixels) and to phrase the stem so it
reads naturally next to that image (e.g. "the diagram below" rather
than re-describing it from scratch). The image reference on the
resulting `GeneratedQuestion` (its URL + alt text) is attached
separately, by the calling code, from `Topic.image_asset` -- not
something the model produces or can omit.

**Rationale**: User Story 1's own examples ("label the parts of this
diagram", "what value does this chart show") only make sense if the
generated stem is actually written with the image in mind, not a
generic stem that happens to have an unrelated picture bolted on next
to it. Keeping the actual image attachment (URL, alt text) entirely
outside the LLM's structured output -- sourced deterministically from
the topic's own content-artifact data -- preserves FR-004's
requirement that grading stay an unchanged, deterministic
answer-key comparison: nothing about *whether* a question has an image
or *what* that image is ever depends on a model call succeeding.

**Alternatives considered**: Not telling the model about the image at
all (attach it purely as decoration) -- rejected, produces exactly the
disconnected-stem failure mode above and doesn't satisfy the "includes
a reference to that image" language in FR-004/Acceptance Scenario 1 in
spirit, even if a bare attachment would satisfy it literally.

## 4. Which topics get an image, and how often

**Decision**: Whether a topic has an image is a fixed, per-topic
content-authoring choice (`Topic.image_asset` is present or absent,
set once at content-artifact load time). Every question generated for
an image-bearing topic includes that topic's image; there is no
per-question randomization of whether to show it.

**Rationale**: FR-004 requires the *capability* to exist, not that
images appear probabilistically. A fixed per-topic association is the
simplest design that satisfies every acceptance scenario (an
image-bearing topic's questions always show it; a topic with no image
is always text-only, User Story 1 Acceptance Scenario 3) and keeps the
existing FR-008 near-duplicate check correct for free: since the image
never varies for a given topic, the pre-existing
`services/dedup/checker.py` stem-similarity check over that topic's
recent questions already fully covers the "avoid showing an
image+near-duplicate-stem pairing" edge case named in spec.md's Edge
Cases section -- no new dedup logic needed.

**Alternatives considered**: Randomly deciding per-generation whether
to include a topic's image -- rejected as unrequested complexity with
no stated requirement driving it (YAGNI), and it would reintroduce a
dedup gap (two generations of the same topic, one with the image and
one without, aren't distinguished by the current stem-only similarity
check) that the fixed-per-topic design avoids entirely.

## 5. Threading the image reference through three response-building call sites

**Decision**: `Topic.image_asset` (a nullable JSON column, mirroring
the existing `skill_definition`/`difficulty_calibration` pattern) is
read once per question-generation call, in the two existing dataclasses
that already carry a `topic`-derived result forward:
`agents/sequencing/agent.py`'s `NextQuestionResult` and
`services/quiz/session.py`'s `QuizQuestionResult` each gain
`image_url: str | None` and `image_alt_text: str | None` fields,
computed via one small shared helper (`services/content_artifact/image_asset.py`'s
`content_image_url(subject_id, filename) -> str`). The three places
that currently build a `GeneratedQuestion` row or a question response
Pydantic model (`routes/questions.py`'s inline construction,
`services/quiz/session.py`'s `persist_quiz_question`, and the
`NextQuestionOut`/`QuizQuestionOut` response models) each gain the same
two fields, copied straight through.

**Rationale**: Both dataclasses already exist specifically to carry a
generated question's derived fields from a `Topic` lookup through to
persistence and the API response -- adding two more fields to an
existing carrier is the smallest diff, and reuses the same shape both
the non-quiz and quiz paths already share (`draft_to_answer_key`,
`ValidationStatus.VALID`, `shown_at`), rather than inventing a
parallel "does this question have an image" side-channel.

**Alternatives considered**: Looking up the image fresh from `Topic` at
API-response time instead of snapshotting it onto `GeneratedQuestion` --
rejected: every other per-question field this project persists
(`stem`, `answer_key`) is snapshotted at generation time so a
previously-shown question's content can never silently change under a
learner mid-session if the content artifact is reloaded; the image
reference should have the same stability guarantee.

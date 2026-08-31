# Feature Specification: Multimodal Question Stimuli -- Image-Based Questions

**Feature Branch**: `003-multimodal-question-stimuli`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Image-based question stimuli: content
artifacts can bundle images as question context, assessment generation
can produce structured questions that display them, grading stays
deterministic and unchanged"

## Clarifications

### Session 2026-08-28

- Q: How should image assets be stored and served? (FR-005) → A: Static files bundled inside each subject's content-artifact directory, served as Next.js static assets (git-versioned, no new service).
- Q: What's the actual maximum file size for an image asset? (FR-002 / SC-003) → A: 1 MB per image.
- Q: Which image file formats are allowed for an image asset? (FR-002) → A: PNG, JPEG, and SVG.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Answer a question that shows an image, not just text (Priority: P1)

A learner receives a structured question that displays a bundled image
alongside the question text -- e.g. "label the parts of this diagram" or
"what value does this chart show" -- and answers it the same way as any
other structured question.

**Why this priority**: This is the entire point of the milestone -- an
image-displaying question is the smallest genuinely multimodal capability
worth proving before considering anything more ambitious (audio,
learner-submitted images, generated images).

**Independent Test**: Given a content artifact with a topic that
includes a bundled image asset, request a question for that topic and
confirm the resulting question includes a reference to the image and
displays correctly.

**Acceptance Scenarios**:

1. **Given** a topic in a content artifact has an associated image
   asset, **When** the Assessment-Generation Agent produces a question
   for that topic, **Then** the question includes a reference to that
   image, and the image renders alongside the question text and answer
   choices.
2. **Given** an image-based question has been generated, **When** the
   learner submits a structured answer, **Then** grading proceeds
   exactly as it does for a text-only question -- a deterministic
   comparison against the generated answer key (Constitution Principle
   II, unchanged from Milestone 1's FR-009). This milestone introduces
   no new grading logic.
3. **Given** a topic has no associated image asset, **When** a question
   is generated for it, **Then** the question is text-only, exactly as
   before this milestone -- images are additive, never required.

---

### User Story 2 - Add image-based questions to a subject without touching engine code (Priority: P1)

A content author adds an image asset to a subject's content artifact and
confirms image-based questions work for it, with zero changes to any
engine file.

**Why this priority**: Directly extends Constitution Principle III
(domain-agnostic core) to cover this new content type -- the same proof
required of every other capability added to this platform.

**Independent Test**: Add an image asset to a second subject's content
artifact, with zero edits to any file outside that artifact's own
directory, and confirm image-based question generation works correctly
for it.

**Acceptance Scenarios**:

1. **Given** a second subject's content artifact includes an image
   asset for one of its topics, **When** the full question-generation
   flow runs against it, **Then** it behaves correctly with no
   engine-file changes -- verified by extending the same automated
   extensibility check established in Milestone 1 (FR-012/SC-004) to
   cover image-referencing content artifacts.

---

### User Story 3 - Every image-based question is accessible (Priority: P1)

A learner using a screen reader, or any learner in a context where the
image doesn't load, still gets a meaningful description of what the
image shows.

**Why this priority**: An image-based question with no accessible
fallback actively excludes learners rather than serving them --
non-negotiable from the same milestone that introduces the capability,
not a follow-up.

**Independent Test**: Attempt to define a content artifact's image asset
without an alt-text/description field and confirm content-artifact
validation rejects it at load time.

**Acceptance Scenarios**:

1. **Given** an image asset definition in a content artifact, **When**
   the artifact is validated, **Then** validation fails if the image
   asset has no non-empty alt-text/description field -- mirroring
   Milestone 1's FR-002 pattern of failing at artifact-load time, not at
   question-display time.

---

### User Story 4 - Images work correctly on the live Vercel deployment (Priority: P2)

The same image-based questions that work in local development also work
correctly once deployed -- images load, and no request depends on local
filesystem state that a serverless function can't guarantee.

**Why this priority**: Directly required by Constitution Principle IX --
scoped below User Stories 1-3 because the capability has to exist and be
correct locally before its deployed behavior is worth testing in
isolation.

**Independent Test**: Deploy to Vercel and confirm an image-based
question renders correctly end to end against the live deployment.

**Acceptance Scenarios**:

1. **Given** the live Vercel deployment, **When** a learner requests a
   question for a topic with a bundled image, **Then** the image loads
   correctly -- verified by extending Milestone 1's post-deploy smoke
   test (SC-007) to cover an image-based question.

**Verified (2026-08-31, staging)**: confirmed against the real
deployed `staging` URL after PR #48's merge. A live,
Assessment-Generation-Agent-produced question for algebra-1's
`systems-of-linear-equations` topic returned a resolving `image_url`
(HTTP 200, correct `image/svg+xml` content-type), the model's stem
naturally referenced "the diagram below," grading via
`POST .../answer` was unaffected, and biology's image asset also
resolved live. Two things surfaced (neither is new production code):
the content-artifact reload needed an explicit manual run against
staging's database, which is expected (always a manual step); the
schema migration also needed a manual re-trigger, which is *not*
expected -- tech-stack.md commits `staging`/`main` to an automated
migration deploy hook, so why it didn't apply on this deploy is an
open follow-up (roadmap.md's Milestone 10 status), not something
resolved here.

---

### Edge Cases

- What happens if a content artifact references an image asset file that
  doesn't exist? (Must fail content-artifact validation at load time,
  the same as any other structural problem with the artifact -- never
  discovered only when a learner happens to be served that question.)
- What happens if an image asset exceeds 1 MB? (Content-artifact
  validation must enforce and report this limit at load time, not let
  an oversized asset risk deployment or page-load issues discovered
  later.)
- What happens if an image asset is not a PNG, JPEG, or SVG file?
  (Content-artifact validation must reject it at load time, the same
  as a missing or oversized asset.)
- Does allowing SVG (an XML format that can embed `<script>` content)
  introduce a script-execution risk? (No new validation is required:
  every image asset is rendered via a plain `<img>` tag, never inlined
  as `<svg>` markup or injected via `dangerouslySetInnerHTML` -- an
  `<img>`-loaded SVG is treated by every browser as non-scriptable
  "image mode," so embedded script content never executes. This is a
  property of how images are rendered, not something content-artifact
  validation needs to separately scan for.)
- What happens if two topics -- in the same subject or different ones --
  reference an identically-named image file but supply different
  alt-text? (No conflict: alt-text is authored per topic, not derived
  from the file, so this is simply two topics each describing the same
  underlying image in whatever way fits their own question. See Key
  Entities.)
- What happens if two different subjects reference the same image asset
  (e.g. a generic diagram reused across subjects)? (Duplicate references
  are acceptable in this milestone -- a shared/deduplicated asset
  library is a possible future optimization, not required now; see
  Assumptions. This requires zero subject-aware logic: each subject's
  images live under its own directory and are served under its own
  `/content-images/<subject_id>/...` URL path, so an identical filename
  reused in two subjects' own directories never collides.)
- What happens if an image fails to load for a learner in production
  (a transient network failure, or a deploy where the image sync step
  didn't run)? (No new fallback behavior is needed: a standard `<img>`
  element with its required `alt` text (FR-003) already shows a
  browser's native broken-image indicator together with the alt text
  when the image itself fails to load -- the same required field that
  serves screen-reader accessibility also serves as the load-failure
  fallback.)
- What happens if the Assessment-Generation Agent is asked for a
  question on a topic where every existing image asset has already been
  shown to this learner recently? (Already covered by Milestone 1's
  FR-008 stem-similarity check, unmodified: a topic's image asset is
  fixed and never varies independently of its stem (see Assumptions),
  so avoiding a near-duplicate stem for that topic already avoids
  re-showing a near-duplicate image+question pairing. No new
  dedup logic is introduced by this milestone.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The content-artifact schema MUST support an optional image
  asset reference per topic, stored as a static file under that
  subject's own content-artifact directory (in an `images/`
  subdirectory alongside its `subject.yaml`, see FR-005), never as
  inline base64 data embedded in the topic-graph document itself.
- **FR-002**: Content-artifact validation MUST fail at load time (not at
  question-display time) if a referenced image asset is missing,
  exceeds 1 MB (1,048,576 bytes), or is not a PNG, JPEG, or SVG file.
- **FR-003**: Every image asset definition MUST include a required
  alt-text/description field that is non-empty after trimming
  whitespace (a value consisting only of spaces/tabs does not satisfy
  this); content-artifact validation MUST reject a definition missing
  one. This is a syntactic floor, not a content-quality bar -- whether
  the text actually describes the image is a content-authoring/review
  concern, not something validation mechanically checks.
- **FR-004**: The Assessment-Generation Agent MUST be able to produce a
  structured (multiple-choice or numeric) question whose stem is
  phrased with the topic's bundled image asset in mind (e.g. referring
  to "the diagram below"), not merely a generic stem with an unrelated
  image attached, with grading remaining an unchanged, deterministic
  answer-key comparison -- this milestone introduces no new grading
  logic (Constitution Principle II is unaffected, not extended).
- **FR-005**: Image assets MUST be static files bundled inside their
  subject's own content-artifact directory (git-versioned alongside
  that subject's topic graph), served as static Next.js assets --
  built into the frontend's static output ahead of time, never read
  from a local filesystem while handling a learner-facing request, and
  never requiring an external storage service (e.g. Vercel Blob) or
  upload step.
- **FR-006**: The extensibility check established in Milestone 1 MUST be
  extended to verify image-based questions work correctly for at least
  two subjects with zero engine-code changes beyond each subject's own
  content artifact.
- **FR-007**: Learner-submitted images (e.g. a photograph of handwritten
  work submitted as an answer) and audio or video modalities MUST NOT be
  accepted anywhere in this milestone -- explicitly out of scope (see
  Assumptions), and the system must not silently accept an image upload
  as an answer submission.

### Key Entities *(include if feature involves data)*

- **ImageAsset**: a static file path (relative to its subject's own
  content-artifact directory) associated with a topic, plus its
  required alt-text/description. File size is checked against the 1 MB
  limit (FR-002) at load time from the file itself -- it is not a
  stored attribute of the persisted ImageAsset. Alt-text is an
  attribute of the *topic's use of the image*, not of the file itself:
  two topics (in the same or different subjects) may reference an
  identically-named image file while each supplying its own alt-text,
  with no conflict -- there is exactly one ImageAsset per topic, never
  a shared record keyed by filename. If a topic's alt-text is edited
  and the content artifact reloaded, only questions generated *after*
  the reload get the new text; a question already shown to a learner
  keeps the alt-text (and image reference) it was generated with,
  exactly as Milestone 1 already treats a question's `stem` as fixed at
  generation time.
- **GeneratedQuestion** (extended from Milestone 1): now optionally
  includes a reference to an `ImageAsset` -- the question's answer key
  and grading behavior are otherwise unchanged from Milestone 1's
  definition. This reference (an image URL plus its alt-text) is
  represented identically across every endpoint that returns a
  generated question (next-question, quiz start, quiz next-question) --
  no endpoint-specific divergence is intended, and the two fields are
  always either both present or both absent together, never one
  without the other.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a content artifact with an image-bearing topic, the
  Assessment-Generation Agent produces a question displaying that image,
  and grading of the resulting structured answer is verified to use the
  exact same deterministic comparison logic as a text-only question --
  no separate code path.
- **SC-002**: 100% of image-based questions in the test suite include
  non-empty alt text, verified by an automated check that rejects any
  without it.
- **SC-003**: A content artifact referencing a missing image asset, one
  exceeding 1 MB, or one that isn't a PNG, JPEG, or SVG file, fails
  validation at load time, verified by a specific test.
- **SC-004**: Image-based questions work correctly for at least two
  subjects with zero engine-code changes beyond each subject's own
  content artifact, verified by the extended extensibility check.
- **SC-005**: An image-based question renders correctly end to end
  against the live Vercel deployment, verified by an extension of
  Milestone 1's post-deploy smoke test with an objective, automatable
  pass condition: an HTTP `GET` of the question's returned `image_url`
  against the live deployment returns `200` with image content --
  not a subjective/visual judgment call.

## Assumptions

- This milestone covers image stimuli only -- a question that displays
  an existing, pre-supplied image to the learner. Audio, video, and
  learner-submitted images (e.g. photographing handwritten work for
  grading) are explicitly out of scope and would each need their own
  future milestone: audio introduces playback UX and possibly
  speech-to-text; learner-submitted images for grading would require
  real vision-based grading, a substantially larger lift than adding an
  image to an already-deterministic structured question.
- Images are authored and bundled as part of a subject's content
  artifact by whoever creates that content. The Assessment-Generation
  Agent selects among existing, pre-supplied images -- it does not
  generate new images via an image-generation model. Generating novel
  images is a separate, higher-risk future capability (the correctness
  of an AI-generated diagram is much harder to validate than reusing a
  vetted, pre-supplied one) deliberately not included here.
- Whether a topic has an image, and which one, is a fixed per-topic
  content-authoring choice, not randomized per question generation:
  every question generated for an image-bearing topic includes that
  topic's image, and a topic with no image asset is always text-only.
  This keeps FR-008's existing near-duplicate check (see Edge Cases)
  sufficient without any image-aware extension to it.
- Duplicate image assets referenced across multiple subjects are
  acceptable in this milestone; a shared, deduplicated asset library is
  a possible future optimization, not required now.
- This milestone depends only on Milestone 1's content-artifact schema
  and Assessment-Generation Agent. It does not require the
  Recommendation Agent, the personalization-evaluation harness,
  free-text grading, classroom features, or the Tutor Agent -- but is
  sequenced after all of them on the roadmap because it extends platform
  capability breadth rather than deepening the core personalization
  thesis those milestones establish.
- Placement questions (produced by the Diagnostic Agent, Milestone 1)
  never carry an image -- this milestone touches only the
  Assessment-Generation Agent's question-returning endpoints
  (next-question, quiz start, quiz next-question), and placement's own
  question shape is intentionally left unmodified, not merely
  unaddressed.

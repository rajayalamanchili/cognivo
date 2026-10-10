# Quickstart: Guardian Multi-Subject Cards & Practice/Tutor Shortcuts

Validation scenarios proving each user story end-to-end. Run after
`/speckit-implement`, against a local dev environment. **No migration to
apply** -- this feature has zero schema change.

## Prerequisites

- `backend/` running locally (`uvicorn` dev server).
- `frontend/` running locally (`next dev`).
- A real guardian account with at least one added learner.
- At least one open-enrollment, listed class per subject to join (spec
  041's class directory) -- enough to enroll one learner in two different
  subjects for Story 1, and at least one graded subject (declared
  `GradeBand` rows) for Story 5.

## Story 1 -- Multi-subject cards

1. As a guardian, enroll one learner in two different classes (two
   different subjects, via the class directory or a join code).
2. Open Guardian · My learners -- confirm the learner's card shows two
   tabs, one per class.
3. Click each tab -- confirm its own stat tiles, assigned quizzes, and
   standards update to that subject's data (not a combined view of both).
4. Click "Add a subject" and join a third class -- confirm a third tab
   appears, selected, with the first two still present and unchanged.
5. Confirm a different, single-enrollment learner's card shows no tab
   chrome at all -- just that one class's progress directly.

## Story 2 -- One-click 15-minute practice shortcut

1. On a learner's card, click "Start practice" on one of their subject
   tiles.
2. Confirm the very next screen is an already-running practice question
   with a visible 15-minute countdown, for that tile's subject -- no
   subject-or-time-limit picker in between.
3. Let the countdown reach zero (or use a short dev-only override if one
   exists) -- confirm the end-of-session summary matches what a session
   started through Practice's own picker would show.
4. Repeat for a learner who has **never** answered a question in that
   subject before (zero `MasteryState` rows) -- confirm it still works
   (research.md §1's bypass), not a 404.
5. Navigate to `/practice` directly, or via Dashboard's/Mastery's/
   Placement's own links -- confirm the ordinary picker still appears,
   unchanged.

## Story 3 -- Inline AI Tutor hint on Practice

1. Start practicing (ordinary or Story 2's shortcut); while a question is
   on screen, click "Stuck? Ask the AI Tutor for a hint."
2. Confirm a side panel opens next to the question (the question stays
   visible, no page navigation to `/tutor`) with a tutor response already
   addressing that specific question -- no typing required.
3. Type a follow-up into the panel's own input -- confirm it streams a
   response exactly like the dedicated Tutor page would.
4. Submit the question's answer; on the result screen, click "Talk it
   through with the AI Tutor" -- confirm the same inline-panel behavior.
5. Confirm the Tutor's own nav link and Dashboard's "Ask the AI Tutor
   first" link still navigate to the full `/tutor` page, unchanged.

## Story 4 -- Context-relevant suggested prompts

1. From Dashboard, click a specific subject's "Ask the AI Tutor first"
   link -- confirm chat opens directly (no subject-picker step) and the
   three suggested-prompt pills reference that subject's current topic.
2. Open the Tutor via its plain nav link instead -- confirm the subject-
   picker still appears; after picking a subject, confirm the same
   topic-worded prompts appear once chatting starts.
3. For a subject with no resolvable topic recommendation, confirm the
   pills fall back to today's generic wording, not blank/broken prompts.

## Story 5 -- Guardian-initiated real placement

1. On a learner's card, find a graded-subject tile with no starting grade
   yet -- confirm "Take placement" is offered.
2. Click it -- confirm it opens directly into that subject's placement
   flow (today's existing placement UI, unchanged).
3. Complete placement (answer or skip each question) -- confirm a
   starting grade gets assigned (check `GET /api/learners/{id}/
   enrollments` or the card's own displayed grade), and "Take placement"
   no longer appears for that subject.
4. Confirm a different learner who never takes placement in a graded
   subject can still practice it normally, with their grade unlocking
   organically exactly as before this feature.
5. Confirm an ungraded subject's tile never offers "Take placement."

## Story 6 -- Warning before losing unsubmitted progress

1. Start a practice question (don't submit it); click any Nav link (e.g.
   "Dashboard").
2. Confirm a confirmation appears stating that leaving starts over with
   new questions, before any navigation happens; cancel it -- confirm you
   remain on the same question, untouched.
3. Click the same link again and confirm leaving this time -- confirm
   navigation proceeds normally.
4. Submit the current question (viewing its result), then navigate away
   -- confirm no warning appears (nothing unsubmitted).
5. Repeat steps 1-3 on Placement with at least one (but not all) shown
   questions answered.
6. Click "Next question" (Practice) or skip a question (Placement) --
   confirm neither ever shows the warning; they're progressing within the
   same page, not navigating away.

## Regression check

Run the full existing Vitest + pytest suites -- expect 100% pass. Spot-
check that a single-enrollment learner's card, the demo learner's own
Practice/Placement/Tutor flows, and assigned-quiz questions all behave
exactly as they did before this feature (SC-005).

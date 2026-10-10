# Feature Specification: Guardian Multi-Subject Cards & Practice/Tutor Shortcuts

**Feature Branch**: `044-guardian-learner-shortcuts`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "1. update guardian learner screen to show all enrolled subjects in learner tile with ability to add more subjects after enrollment, new mockup '041 · Guardian · My learners-html (1).zip'. 2. practice screen to skip landing screen when clicked from learner subject tile and start from subject 15 min timed session. 3. clicking ask tutor in practice page should start tutor chat with current question hint rather than new chat."

## Context

This feature closes five small, already-in-view gaps on top of
`specs/041-guardian-public-ui-redesign`, using a second, updated "Guardian ·
My learners" mockup (`GuardianLearners.v041.dc.html`) plus four
frictionless-navigation/capability requests the user raised directly, not
sourced from any mockup.

**Gap 1 -- multi-subject cards.** The updated mockup's own in-file comment is
explicit: "Each learner can be in several classes, one per subject or more,"
with a per-subject tab row ("SUBJECTS & CLASSES") and an "Add a subject"
control on every card, including ones that already have an enrollment. The
live app does not support this today. `backend/src/api/routes/learners.py`'s
`list_my_learners_route` carries its own `ponytail:` comment marking the
exact gap: "a learner enrolled in more than one roster at once collapses to
whichever row the query returns first -- the product UI (Guardian · My
learners' single 'class' per card) has no multi-class display today;
revisit if/when it does." `MyLearnerOut.enrollment` is a single nullable
`MyLearnerEnrollmentOut`, and `GuardianLearnerCard.tsx` renders exactly one
enrollment. The data model underneath already allows it --
`backend/src/models/enrollment.py`'s `Enrollment` has a
`UniqueConstraint("learner_id", "roster_id")`, not `(learner_id,
subject_id)`, and `ClassDirectoryBrowse`/`JoinRosterForm` (already shown
today only when a learner has *zero* enrollments) already surface the
"already in a `{subject}` class, this would be a second one" note for a
second roster of the same subject. This is purely a response-shape and
display gap, not a new backend capability.

**Gap 2 -- a one-click 15-minute practice shortcut.** `frontend/src/app/
practice/practice-flow.tsx`'s `phase === "start"` screen always requires
picking a subject and a time limit before a session begins, even when
arriving with a subject already known (`?subject=` is read today by
`DashboardSubjectSection.tsx`, `mastery-flow.tsx`, and
`placement-flow.tsx`'s existing "Start practicing"/"Practice now" links, all
of which still land on that picker because no time limit is implied). The
user wants a learner's enrolled-subject tile (Gap 1's new per-subject tab)
to instead jump straight into a running 15-minute timed session
(`startPracticeSession(subjectId, 900)`, spec 022-timed-practice-quiz-
mode's existing mechanic) for that subject, with no picker screen in
between. That mechanic turned out to need its own fix first, found while
tracing it for this spec: `backend/src/api/routes/practice_sessions.py`'s
`start_practice_session` (and its sibling next-question/end/summary
routes) hardcode `get_demo_learner(db)`, with no `learner_id` accepted at
all -- spec 041's FR-016 extended real-learner access to *untimed*
practice (`next-question`) only, never to this timed-session endpoint
family. FR-008 closes that gap the same way FR-025 closes the identical
one for placement.

**Gap 3 -- a scoped tutor hint, inline, not a separate page.** Practice's two
"Ask the AI Tutor" links (the in-question footer's "Stuck? Ask the AI Tutor
for a hint" and the post-answer result screen's "Talk it through with the
AI Tutor") both plain-navigate to `/tutor` today. `frontend/src/app/tutor/
tutor-flow.tsx` always starts on its own `phase === "picking"` subject
selector, and once a chat opens, `TutorChat.tsx` starts empty --
`SUGGESTED_PROMPTS` only *pre-fill* the input on a click, they don't
auto-send. A learner who was mid-question in Practice loses that context
entirely, leaves the practice flow, and has to re-pick a subject, then type
their own question. Per Clarifications, the fix keeps the learner on
Practice entirely: both links open `TutorChat.tsx` inline, in a collapsible
side panel next to the question, with an already-sent hint message. The
`NextQuestion` type already fetched by Practice (`frontend/src/services/
api.ts`) carries `topic_id` and `stem`, enough to ask the already-existing
Tutor Agent for a hint on that specific question with no new backend
endpoint -- and `TutorChat.tsx` itself is reused as-is (same streaming,
same multi-turn input, same grounded-sources display), just mounted on
Practice's own page instead of `/tutor`'s.

**Gap 4 -- suggested prompts don't reflect how the learner got there.**
`TutorChat.tsx`'s `SUGGESTED_PROMPTS` is one static, subject-agnostic array
("Give me a hint, not the answer", "Can you explain that differently?",
"Show me a similar example") shown no matter how the chat was reached.
`DashboardSubjectSection.tsx`'s "Ask the AI Tutor first" link is also
`href="/tutor"` with no subject param today -- unlike its own sibling links
("Start practicing", "Practice now") a few lines above it, which already
pass `?subject=${subjectId}`. A learner who clicks it from a specific
subject's dashboard section, and a learner who clicks the plain "Tutor"/"AI
Tutor" entries in `Nav.tsx` (truly no subject context at all), land on an
identical blank picker today. Meanwhile `tutor-flow.tsx` already fetches
`getTopicPriorityPreview(learnerId, selectedSubjectId)` once chatting (for
its "You're working on" sidebar card) -- the exact topic context needed to
make suggested prompts relevant, already in hand with no new request.

**Gap 5 -- real placement for guardian-managed learners.** A real learner
has no way to take placement at all today: `Nav.tsx`'s Placement link only
exists in `DEMO_LEARNER_LINKS`, and `backend/src/api/routes/placement.py`'s
`start_placement` doesn't even accept a `learner_id` -- it calls
`get_demo_learner(db)` unconditionally. Spec 041's Clarifications
explicitly declined wiring this up ("real placement stays demo-only...
that would be new product scope"), reasoning that real learners already
practice and take assigned quizzes without it, via organic grade-unlocking
through practice answers (spec 019's `GradeProgress`/`unlocked_grade`
mechanism -- null until the Sequencing Agent's own unlock check first
raises it). Revisiting that decision here: `submit_placement` and
`skip_placement_question` already derive `learner_id`/`subject_id` from
the `GeneratedQuestion` row a prior `start_placement` call created, so
neither needs any change -- `start_placement` is the only endpoint that
needs a real `learner_id`, gated the same way `questions.py`'s
`get_next_question_route` already gates a real learner's own endpoints
(`require_learner_ownership_if_real`). `_assign_starting_grade_if_graded`
is already a no-op whenever a `GradeProgress` row exists or a subject has
no declared `GradeBand` rows (ungraded subjects, e.g. Biology in the
mockup) -- both guards this feature needs already exist, with nothing to
duplicate. `ClassroomRoster.grade` (spec 040's roster-level grade band,
shown as "Grade {enrollment.grade}" on a guardian's card) and
`GradeProgress.unlocked_grade` (the content-unlock signal placement sets)
are already two separate, non-interacting concepts for the demo learner
today -- adding a real learner's `GradeProgress` row changes nothing about
how `grade` is read or displayed elsewhere.

**Gap 6 -- no warning before losing unsaved progress.** Neither Practice
nor Placement persists an in-progress question across navigation (see
Assumptions): leaving mid-question and coming back always starts over
with a freshly-fetched/generated question, with no indication to the
learner beforehand that this will happen. The user wants a warning shown
before that loss occurs, specifically when leaving the page without
having submitted the current question(s).

## Clarifications

### Session 2026-10-10

- Q: Does the inline-hint change apply to both of Practice's "Ask the AI Tutor" links -- the mid-question one and the post-answer "Talk it through" one -- or only the mid-question one? → A: Both. Mid-question and post-answer links both show the hint inline on Practice, not a navigation to a separate Tutor page.
- Q: Should the inline hint panel be a full back-and-forth chat, or a single auto-generated hint with no further typing? → A: Full multi-turn chat, reusing the existing `TutorChat` component and session exactly as the dedicated Tutor page already does -- the learner can keep asking follow-ups without leaving Practice.
- Q: How should the inline chat be laid out relative to the question -- alongside it (split view) or as an overlay that covers it? → A: A collapsible side panel alongside the question. The question stays visible the whole time; no overlay ever hides it.
- Q: Should Dashboard's "Ask the AI Tutor first" link start passing its subject into Tutor (skipping the subject-picker, the same way Practice's shortcut does), or should the picker stay and only the prompts shown afterward become relevant? → A: Skip the picker too. The link now carries `?subject=`, same pattern as its sibling "Start practicing"/"Practice now" links, and lands directly in chat for that subject.
- Q: Should relevant prompts be tied to the subject only, or to the learner's current recommended topic within that subject? → A: Topic-level, reusing `getTopicPriorityPreview` (already fetched for the "You're working on" sidebar card) -- no new request.
- Q: Should a guardian-managed learner be required to complete placement before practicing a graded subject, or is it an optional fast-track alongside today's organic grade-unlock-through-practice? → A: Optional fast-track. Practice stays available exactly as today regardless of whether placement was ever taken; "Take placement" is an extra, skippable shortcut a guardian can choose instead, with zero regression risk for already-enrolled real learners who never had this option.
- Q: Story 2's "Start practice" shortcut needs a real `learner_id` to reach the timed practice-session endpoints, which turned out to be demo-learner-only today -- should this feature extend real-learner support to them (the same pattern Story 5 uses for placement), since FR-009 can't work without it? → A: Yes. Extend `start_practice_session`/`get_practice_next_question`/`end_practice_session`/`get_practice_session_summary` to accept and act on a real `learner_id`, gated with `require_learner_ownership_if_real` the same way other real-learner endpoints already are.
- Q: Since browsers ignore custom `beforeunload` text for an actual tab-close/URL-bar/back-button navigation (only their own generic wording ever shows), should the "you'll get new questions" warning cover only in-app navigation, or also attempt a native browser-level prompt for true browser navigation? → A: In-app only. Intercept in-app navigation (Nav links, Practice's own "End session" link, etc.) while a question is unanswered and show a real custom confirmation; no native `beforeunload` handler is added for actual browser-level navigation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A guardian sees and manages every class a learner is in, not just one (Priority: P1)

A guardian on Guardian · My learners sees each of their learner's current
enrollments (one tab per class) on that learner's card, can switch between
them to see that class's own progress, assigned quizzes, standards, and
career connections, and can add the learner to another class at any time --
whether the learner currently has zero, one, or several classes already.

**Why this priority**: This is the data-correctness gap: a guardian whose
child is in two classes today cannot see or manage the second one at all.
Everything else in this feature builds on a card that already shows every
enrollment.

**Independent Test**: As a guardian with a learner enrolled in two different
classes (seed or join two rosters for the same learner), load Guardian · My
learners and confirm both classes appear as separate tabs on that learner's
one card, each showing that class's own progress and quizzes; join a third
class via "Add a subject" and confirm all three now appear with no loss of
the first two.

**Acceptance Scenarios**:

1. **Given** a learner enrolled in two classes, **When** their guardian
   opens Guardian · My learners, **Then** the learner's card shows one tab
   per class, and selecting a tab shows that class's own stat tiles,
   assigned quizzes, and standards.
2. **Given** a learner already enrolled in at least one class, **When** the
   guardian uses "Add a subject" on that learner's card and joins another
   open, listed class, **Then** a new tab for that class appears on the
   same card, is selected, and every previously-visible tab is still
   present and unchanged.
3. **Given** a learner not yet enrolled anywhere, **When** their guardian
   views that learner's card, **Then** it still shows today's "Not in a
   class yet" / join-a-class state (unchanged by this feature).
4. **Given** a learner with exactly one class, **When** their guardian
   views that learner's card, **Then** no tab-switcher chrome is shown
   (same single-item convention `DashboardSubjectSection`/`PracticeFlow`
   already use for a one-subject learner) -- the card simply shows that
   one class's progress directly.

---

### User Story 2 - A guardian starts a learner's timed practice in one step from a subject tile (Priority: P2)

From a learner's card, a guardian clicks a specific enrolled-subject tile's
"Start practice" action and lands directly on a running 15-minute timed
practice session for that subject and that learner -- no subject picker, no
time-limit picker.

**Why this priority**: A real friction-reduction improvement on top of
Story 1's new per-subject tiles, but it depends on those tiles existing
first and doesn't fix a correctness gap the way Story 1 does.

**Independent Test**: As a guardian, click "Start practice" on one of a
learner's subject tiles and confirm the very next screen is an in-progress
practice question with a visible countdown, for the tile's subject, with no
intermediate form; let the countdown reach zero and confirm it ends exactly
like any other timed session (spec 022's existing end-of-session summary).

**Acceptance Scenarios**:

1. **Given** a learner's card showing one or more subject tiles, **When**
   the guardian clicks a tile's "Start practice" action, **Then** the
   learner's real session opens (same hand-off `GuardianLearnerCard.tsx`'s
   "Open {name}'s learning" already performs) directly into an active
   15-minute timed practice session for that tile's subject.
2. **Given** that same shortcut, **When** the session is running, **Then**
   its countdown, end-of-session summary, and mastery updates behave
   identically to a 15-minute session started the ordinary way from
   Practice's own picker.
3. **Given** Practice reached by any other existing path (navigating to
   `/practice` directly, or via Dashboard's/Mastery's/Placement's existing
   "Start practicing"/"Practice now" links), **When** it loads, **Then** it
   still shows today's subject-and-time-limit picker, unchanged.

---

### User Story 3 - An inline AI Tutor hint stays alongside the practice question, without leaving Practice (Priority: P2)

While answering a practice question, or right after submitting one, a
learner clicks "Ask the AI Tutor" and a tutor chat opens in a side panel
right on the Practice screen -- the question stays visible the whole time --
already scoped to the current subject, with a hint about that specific
question already waiting for them. The learner can keep chatting (ask
follow-ups, request a different hint) without ever navigating to a
separate Tutor page.

**Why this priority**: Closes real friction in an already-working feature
(the Tutor Agent); independently valuable and testable without Stories 1-2,
but ranked alongside Story 2 since both are UX shortcuts rather than
correctness fixes.

**Independent Test**: While answering a practice question, click "Stuck?
Ask the AI Tutor for a hint" and confirm a side panel opens next to the
(still-visible) question, already showing a tutor response addressing that
question's topic, with no subject-picker screen, no page navigation, and no
empty chat requiring the learner to type first. Confirm the learner can type
a follow-up into that same panel and get a response without leaving
Practice. Repeat from the post-answer result screen's "Talk it through with
the AI Tutor" link.

**Acceptance Scenarios**:

1. **Given** a learner mid-question in Practice, **When** they click "Ask
   the AI Tutor for a hint", **Then** a collapsible side panel opens
   alongside the question (the question itself never gets hidden), already
   scoped to Practice's current subject (no subject-picker step, no page
   navigation to `/tutor`), with a hint request about that exact question
   already sent and a tutor response appearing without the learner typing
   anything.
2. **Given** a learner who just answered a practice question, **When** they
   click "Talk it through with the AI Tutor" on the result screen, **Then**
   the same inline side-panel behavior applies (not a navigation to
   `/tutor`), scoped to the question just answered.
3. **Given** the inline panel is open, **When** the learner types and sends
   a follow-up message, **Then** it behaves exactly like the dedicated
   Tutor page's chat today -- streaming response, suggested prompts,
   grounded-sources display -- just rendered inside Practice.
4. **Given** the hint request sent on the learner's behalf, **When** the
   Tutor responds, **Then** the response is a hint, not the literal answer
   -- the same framing the Tutor's existing suggested prompts already use
   ("Give me a hint, not the answer").
5. **Given** the Tutor reached via its own plain nav link (`Nav.tsx`'s
   "Tutor"/"AI Tutor" entries, which carry no subject context), **When** it
   loads, **Then** it still shows today's blank subject-picker start
   screen, unchanged.

---

### User Story 4 - Suggested prompts reflect where the learner came from (Priority: P3)

A learner who opens the Tutor from a specific subject's "Ask the AI Tutor
first" link on Dashboard lands directly in a chat for that subject, with
its three suggested-prompt pills already worded around the topic they're
currently working on in that subject -- not the same generic three prompts
shown to a learner who opened the Tutor cold, from the plain nav link, with
no subject chosen yet.

**Why this priority**: A worthwhile relevance improvement on an
already-working feature, but the lowest-impact of this feature's four
asks -- nothing is broken today, prompts are just generic.

**Independent Test**: As a learner with an active topic recommendation in a
subject, click that subject's "Ask the AI Tutor first" link on Dashboard
and confirm chat opens immediately (no subject-picker step) with suggested
prompts worded around that topic. Separately, open the Tutor from its plain
nav link, confirm the subject-picker still appears, and confirm that once a
subject is chosen (and its topic recommendation loads), the same
topic-worded prompts appear there too.

**Acceptance Scenarios**:

1. **Given** a learner on Dashboard viewing a specific subject, **When**
   they click that subject's "Ask the AI Tutor first" link, **Then** Tutor
   opens directly in chat for that subject (no subject-picker step),
   mirroring how Practice's own subject-tile shortcut (User Story 2) skips
   its picker.
2. **Given** that chat is open and a topic recommendation exists for the
   subject, **When** the suggested-prompt pills render, **Then** their
   wording references that specific topic rather than the generic,
   subject-agnostic wording shown today.
3. **Given** the Tutor opened via its plain nav link with no subject
   context, **When** it loads, **Then** the subject-picker still appears
   exactly as today; once the learner picks a subject, the resulting chat's
   suggested prompts become topic-worded the same way Scenario 2 describes.
4. **Given** no topic recommendation can be resolved for the active subject
   (e.g., the lookup fails or returns none), **When** the suggested-prompt
   pills render, **Then** they fall back to today's generic, subject-
   agnostic wording rather than showing broken or blank prompts.
5. **Given** Practice's inline tutor panel (User Story 3), **When** its
   suggested-prompt pills render, **Then** the same topic-worded behavior
   applies there too -- one consistent rule for wherever `TutorChat.tsx`
   is mounted, not a special case for Dashboard's entry point alone.

---

### User Story 5 - A guardian can take placement for a learner in a graded subject (Priority: P2)

From a learner's card, a guardian who hasn't yet seen the learner placed
into a subject can click "Take placement" on that subject's tile to open
the learner's real session directly into the placement flow (the same
flow the demo learner already uses), hand the device over, and once it's
complete, the learner's starting grade for that subject is set exactly
the way it already is for the demo learner. A guardian who skips this
entirely sees no change: that subject's grade still unlocks organically
through ordinary practice, exactly as it does today.

**Why this priority**: A real, previously out-of-scope gap (spec 041
explicitly declined it), but it's additive and optional -- nothing already
working changes for a guardian who never touches it -- so it's ranked with
Practice's/Tutor's other shortcut improvements rather than above the
correctness-fixing Story 1.

**Independent Test**: As a guardian with a learner enrolled in a graded
subject with no starting grade yet, click "Take placement" on that
subject's tile, complete the placement flow (answer or skip each
question), and confirm the learner's `GradeProgress.unlocked_grade` for
that subject is set, matching what `determine_starting_grade` would
produce from those same answers for the demo learner. Confirm a second
learner in the same subject who never takes placement can still practice
normally and unlock grades organically, unaffected.

**Acceptance Scenarios**:

1. **Given** a learner enrolled in a graded subject with no `GradeProgress`
   row yet for it, **When** their guardian views that subject's tile on
   the learner's card, **Then** a "Take placement" action is offered.
2. **Given** the guardian clicks "Take placement", **When** the resulting
   session loads, **Then** it opens the learner's real session directly
   into that subject's placement flow (today's existing placement UI),
   with no change to the placement flow itself.
3. **Given** the learner (handed the device, per this app's existing
   guardian-hand-off model) completes placement, **When** it finishes,
   **Then** their starting grade for that subject is assigned exactly as
   it already is for the demo learner, and the "Take placement" action no
   longer appears on that subject's tile.
4. **Given** a subject with no declared grade bands (ungraded, e.g.
   Biology), **When** the guardian views that subject's tile, **Then** no
   "Take placement" action is offered -- placement has nothing to assign
   there, matching today's demo-learner behavior for an ungraded subject.
5. **Given** a learner who never takes placement in a graded subject,
   **When** they practice that subject normally, **Then** their grade
   still unlocks organically exactly as it does today -- placement is
   never required to use Practice, Dashboard, Mastery, or assigned
   quizzes.

---

### User Story 6 - A learner is warned before losing an unanswered question (Priority: P3)

While a question is on screen and not yet submitted on Practice, or while
Placement's shown questions aren't yet fully submitted, clicking any
in-app link that would leave the page (a Nav link, Practice's own "End
session" link, or a guardian's "Exit learner view"/"End session, back to
my learners" action) shows a confirmation first, explaining that leaving
now means starting over with a new set of questions -- not the ones on
screen. Confirming proceeds with the navigation; canceling stays on the
page with nothing lost.

**Why this priority**: A real, previously-undisclosed loss of progress
(Gap 6), but purely a warning -- it doesn't fix the underlying lack of
persistence (Assumptions), so it's ranked alongside this feature's other
smaller UX improvements rather than above the correctness-fixing Story 1.

**Independent Test**: Start a practice question (or start Placement) but
don't submit it, then click a Nav link. Confirm a warning appears
explaining the new-questions consequence before navigating; canceling
keeps the same question/questions on screen untouched; confirming
navigates away as normal. Repeat with the current question already
submitted (or, for Placement, with no questions shown yet) and confirm no
warning appears -- there's nothing to lose.

**Acceptance Scenarios**:

1. **Given** a learner on Practice with the current question unanswered,
   **When** they click any in-app link that would navigate away, **Then**
   a confirmation appears stating that leaving starts over with new
   questions, before any navigation happens.
2. **Given** a learner on Placement with at least one shown question
   answered but the set not yet submitted, **When** they click an in-app
   link that would navigate away, **Then** the same confirmation appears.
3. **Given** that confirmation, **When** the learner confirms leaving,
   **Then** navigation proceeds exactly as it would have without this
   feature; **When** they cancel instead, **Then** they remain on the same
   page with their in-progress question/answers untouched.
4. **Given** a learner on Practice who has already submitted the current
   question (viewing its result) or is still on the subject/time-limit
   picker, **When** they navigate away, **Then** no confirmation appears
   -- nothing unsubmitted exists to lose.
5. **Given** Practice's inline tutor panel (Story 3) is open, **When** the
   warning's trigger condition is evaluated, **Then** it depends only on
   whether the underlying question has been submitted, not on whether the
   panel happens to be open.
6. **Given** a learner attempts to leave via an actual browser action
   (closing the tab, typing a new URL, browser back), **When** that
   happens, **Then** no custom warning is shown (Clarifications) -- this
   feature does not add a native browser-level prompt.

---

### Edge Cases

- A learner with zero enrollments has no subject tile at all, so Story 2's
  "Start practice" shortcut and Story 1's tab row both stay absent -- the
  card keeps today's join-a-class-only state (Story 1, Scenario 3).
- Joining a second class in the *same* subject the learner is already in
  (e.g., two different Biology sections) keeps today's existing "this would
  be a second one" note (`ClassDirectoryBrowse`'s already-built behavior) --
  both appear as separate tabs with no deduplication.
- If the Tutor Agent errors out (rate-limited, unavailable, moderation-
  rejected) when answering the auto-sent hint request, the learner sees the
  exact same inline error states `TutorChat.tsx` already renders for a
  manually-typed question -- no new error handling is introduced.
- If a learner already has an open Tutor Session for the practice subject,
  the hint request is sent as the next message in that existing session
  (today's get-or-create behavior, spec 012 FR-015) rather than always
  forcing a brand-new one.
- The practice-shortcut and tutor-hint-handoff behaviors in this feature
  apply only to the free/timed Practice screen's own question flow --
  assigned-quiz questions (`LearnerAssignments.tsx`) are out of scope and
  keep today's behavior.
- Closing the inline tutor panel MUST NOT discard the learner's in-progress
  answer, flag state, or read-aloud state on the question underneath it --
  the panel is purely additive screen real estate, not a separate phase.
- Advancing to the next question while the panel is open leaves the same
  Tutor Session's chat history in place (it's one ongoing conversation for
  the subject); a fresh hint request for the new question is sent into that
  same session rather than starting a new one, consistent with FR-017's
  existing get-or-create behavior.
- While the topic-priority lookup for suggested prompts is still in flight
  (or if it fails), the prompts shown are today's generic, subject-agnostic
  wording -- the chat is never blocked or left promptless waiting on that
  lookup.
- A learner with no current topic recommendation at all for a subject (for
  example, a subject with no enrollment-driven next topic yet) sees the
  same generic fallback prompts, not an empty or broken suggested-prompts
  row.
- A learner who already has a `GradeProgress` row for a subject (whether
  from already having taken placement, or from organically unlocking a
  grade through ordinary practice) never sees "Take placement" for that
  subject -- the existing idempotency guard (`_assign_starting_grade_if_
  graded`'s own `db.get(GradeProgress, ...)` check) already prevents a
  second assignment from ever being attempted, so this is enforced for
  free, not newly built.
- If a guardian starts placement for a learner and the learner abandons it
  partway (closes the tab, device goes to sleep), today's existing
  partial-session handling applies unchanged -- a resumed/restarted
  placement session behaves exactly as it already does for the demo
  learner, since nothing about `start_placement`/`submit_placement`/
  `skip_placement_question`'s own session logic changes.
- A learner enrolled in more than one graded subject (Story 1) sees "Take
  placement" independently on each graded subject's own tile, scoped to
  that subject only -- taking placement in one subject has no effect on
  any other subject's tile.
- Clicking "Next question" or "Practice again" (Practice's own in-page
  flow-advancing actions, not a navigation to another page) never shows
  the Story 6 warning -- it only guards in-app navigation to a *different*
  page, not progressing within the same one.
- A learner who skips a Placement question (`skip_placement_question`)
  has that question replaced, not submitted -- skipping does not clear
  the "unsubmitted" state Story 6 checks, so the warning still applies
  until the whole set is actually submitted.
- The warning fires at most once per navigation attempt -- canceling it
  and immediately clicking the same link again shows it again each time,
  with no "don't ask again" suppression (not requested, and would let a
  learner silence a real loss-of-progress warning permanently by
  accident).

## Requirements *(mandatory)*

### Functional Requirements

**Multi-subject guardian cards (User Story 1)**

- **FR-001**: `GET /api/learners/mine` MUST return every roster a learner is
  currently enrolled in, not just one.
- **FR-002**: Guardian · My learners MUST render one tab per enrollment on a
  learner's card when the learner has two or more enrollments; selecting a
  tab MUST switch which enrollment's stat tiles, assigned quizzes, and
  standards are shown on that same card.
- **FR-003**: A learner's card MUST offer an "Add a subject" action
  regardless of how many enrollments that learner already has (today it is
  offered only when the learner has zero).
- **FR-004**: Successfully joining an additional class via "Add a subject"
  MUST add a new tab for it to the learner's card and select it, while
  leaving every one of the learner's existing enrollments visible and
  unaffected.
- **FR-005**: A learner with exactly one enrollment MUST NOT show
  tab-switcher chrome -- that one class's progress is shown directly, the
  same single-item convention already used elsewhere in this app.
- **FR-006**: A learner with zero enrollments keeps today's "Not in a class
  yet" / join-a-class-only card state, unchanged.

**One-click 15-minute practice shortcut (User Story 2)**

- **FR-007**: Each enrolled-subject tab on a learner's card MUST offer a
  "Start practice" action for that specific subject.
- **FR-008**: The timed practice-session endpoint family (start/next-
  question/end/summary) MUST accept and act on a real `learner_id`, gated
  the same way `require_learner_ownership_if_real` already gates other
  real-learner endpoints -- today it is demo-learner-only (`get_demo_
  learner(db)`, unconditional), the same gap class FR-025 closes for
  placement, and FR-009 cannot function without this fix.
- **FR-009**: Activating "Start practice" MUST open that learner's real
  session (the same hand-off already used by "Open {name}'s learning") and
  navigate directly into an already-running 15-minute timed practice
  session for that subject, with no intermediate subject-or-time-limit
  picker screen shown.
- **FR-010**: The resulting timed session MUST behave identically in every
  other respect (countdown, end-of-session summary, mastery updates, "End
  practice now") to a 15-minute session started through Practice's existing
  picker.
- **FR-011**: Every other existing way of reaching Practice (direct
  navigation, or the existing `?subject=`-carrying links from Dashboard,
  Mastery, and Placement) MUST continue to show today's subject-and-
  time-limit picker, unchanged.

**Scoped, inline tutor hint from Practice (User Story 3)**

- **FR-012**: Practice's in-question "Ask the AI Tutor" link and its
  post-answer "Talk it through with the AI Tutor" link MUST both open a
  tutor chat inline, in a collapsible side panel on the Practice screen
  itself, already scoped to Practice's current subject -- neither link MUST
  navigate to a separate page or show the Tutor's own subject-picker start
  screen.
- **FR-013**: The inline panel's layout MUST keep the current practice
  question visible at all times; it MUST NOT be an overlay or modal that
  covers the question.
- **FR-014**: The inline panel MUST be a full, multi-turn chat -- reusing
  `TutorChat.tsx` as-is (streaming responses, suggested prompts,
  grounded-sources display, free-form follow-up input) -- not a one-shot
  hint with no further input.
- **FR-015**: The inline chat MUST have an initial message already sent on
  the learner's behalf, asking for a hint about the specific question they
  were just on in Practice (identified by its topic and question text) --
  the learner MUST see a tutor response without typing or submitting
  anything themselves first.
- **FR-016**: The auto-sent hint request MUST ask for a hint, not the
  answer, matching the framing the Tutor's existing suggested prompts
  already use.
- **FR-017**: If the learner already has an open Tutor Session for that
  subject, the hint request MUST be sent into that existing session (today's
  get-or-create resume behavior) rather than always starting a new one.
- **FR-018**: The learner MUST be able to close the inline panel and return
  to the single-column practice view without losing their in-progress
  answer, flag state, or read-aloud state on the question underneath it.
- **FR-019**: Reaching the Tutor via its own plain nav link (`Nav.tsx`'s
  "Tutor"/"AI Tutor" entries, which carry no subject context) MUST continue
  to open today's dedicated `/tutor` page with its blank subject-picker
  start screen, unchanged.

**Context-relevant suggested prompts (User Story 4)**

- **FR-020**: Dashboard's "Ask the AI Tutor first" link MUST carry its
  subject (the same `?subject=` pattern its sibling "Start practicing"/
  "Practice now" links already use) and, on arrival, MUST skip the Tutor's
  subject-picker start screen and open directly into chat for that subject
  -- mirroring how Practice's subject-tile shortcut (FR-009) skips its own
  picker.
- **FR-021**: Wherever `TutorChat.tsx`'s suggested-prompt pills are shown
  (the dedicated `/tutor` page or Practice's inline panel) and a topic
  recommendation is available for the active subject, the pills' wording
  MUST reference that specific topic rather than today's fixed,
  subject-agnostic wording.
- **FR-022**: When no topic recommendation is available for the active
  subject (lookup still pending, failed, or none exists), the pills MUST
  fall back to today's generic, subject-agnostic wording -- the chat MUST
  NOT be blocked, left promptless, or shown broken prompts while waiting.
- **FR-023**: Reaching the Tutor via its own plain nav link (FR-019) MUST
  still show the subject-picker first; once the learner picks a subject
  there, the resulting chat's suggested prompts follow FR-021/FR-022 the
  same as any other entry point.

**Guardian-initiated real placement (User Story 5)**

- **FR-024**: A learner's enrolled-subject tab on their card MUST offer a
  "Take placement" action whenever that subject has declared grade bands
  and no `GradeProgress` row yet exists for the learner in it; the action
  MUST NOT appear for an ungraded subject or once a `GradeProgress` row
  exists (whether from a prior placement or from organic unlocking).
- **FR-025**: `start_placement` MUST accept and act on a real `learner_id`,
  gated the same way `require_learner_ownership_if_real` already gates
  other real-learner endpoints -- today it is demo-learner-only
  (`get_demo_learner(db)`, unconditional), the same gap class FR-008
  closes for timed practice sessions. Once reachable, activating "Take
  placement" MUST open the learner's real session (the same hand-off
  already used by "Open {name}'s learning" and "Start practice") directly
  into that subject's existing placement flow, with the placement flow
  itself behaving identically to how it already does for the demo
  learner.
- **FR-026**: Completing placement for a real learner MUST assign a
  starting grade the same way it already does for the demo learner, using
  the same existing computation (`determine_starting_grade`) with no new
  grading logic.
- **FR-027**: Taking placement MUST remain entirely optional -- a learner
  who never takes it MUST continue to unlock grades organically through
  ordinary practice, exactly as today, with no feature in this app
  (Practice, Dashboard, Mastery, assigned quizzes) gated on placement
  having been completed.

**Warning before losing unsaved progress (User Story 6)**

- **FR-028**: Clicking any in-app link that would navigate away from
  Practice while the current question is unsubmitted, or away from
  Placement while its shown questions aren't yet fully submitted, MUST
  show a confirmation before the navigation proceeds.
- **FR-029**: That confirmation MUST state that leaving now means
  returning to a new set of questions, not the ones currently on screen.
- **FR-030**: Confirming MUST proceed with the original navigation
  exactly as it would have without this feature; canceling MUST keep the
  learner on the same page with their in-progress question/answers
  untouched.
- **FR-031**: This warning MUST cover in-app navigation only (Nav links,
  Practice's own "End session" link, and the guardian real-learner-
  session nav actions) -- it MUST NOT add a native `beforeunload` handler
  for actual browser-level navigation (tab close, URL bar, browser back),
  per Clarifications.
- **FR-032**: Navigating away from Practice once the current question has
  already been submitted (viewing its result) or while still on the
  subject/time-limit picker, or away from Placement before any question
  has been shown, MUST NOT trigger this warning -- there is nothing
  unsubmitted to lose in either case.
- **FR-033**: Progressing within the same page (Practice's "Next
  question"/"Practice again", Placement's skip) MUST NOT trigger this
  warning -- it guards navigation to a different page only.

### Key Entities

No new entities. This feature reuses, and changes only the surfaced shape
of, existing ones:

- **Enrollment** (`backend/src/models/enrollment.py`): already supports a
  learner holding more than one at once (`UniqueConstraint("learner_id",
  "roster_id")`); FR-001 stops collapsing a learner's enrollments down to
  one before they reach the frontend.
- **ClassroomRoster**: unchanged; each enrollment's roster is what a
  learner-card tab (FR-002) and "Start practice" (FR-007) are scoped to.
- **PracticeSession** (`backend/src/models/practice_session.py`): unchanged
  shape; FR-008 lets a real `learner_id` reach the same row-creation path
  (`start_practice_session`) the demo learner already uses, rather than
  adding a second way to start a timed session.
- **Tutor Session / Exchange** (spec 012): unchanged mechanism; FR-015's
  hint request is sent through the exact same message-send path a
  learner's own typed question already uses -- only where `TutorChat.tsx`
  is mounted (inline on Practice vs. the dedicated `/tutor` page) changes.
- **Topic priority preview** (the Sequencing Agent's existing next-topic
  pick, already surfaced via `getTopicPriorityPreview` for tutor-flow.tsx's
  "You're working on" sidebar card): unchanged computation; FR-021 reads
  the same already-fetched result to word suggested prompts, rather than
  computing or requesting anything new.
- **GradeProgress** (`backend/src/models/grade_progress.py`): unchanged
  shape and monotonic-high-water-mark semantics; FR-025/FR-026 let a real
  `learner_id` reach the exact same row-creation path
  `_assign_starting_grade_if_graded` already uses for the demo learner,
  rather than adding a second way to assign a starting grade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A guardian whose learner is enrolled in two or more classes
  can see and open every one of them from that learner's single card, with
  zero classes hidden.
- **SC-002**: A guardian can add a learner to a new class without losing
  access to, or visibility of, any class the learner was already in.
- **SC-003**: A guardian reaches a running, countable-down 15-minute
  practice session for a chosen subject in exactly one action from that
  subject's tile, with no picker screens in between.
- **SC-004**: A learner who asks the AI Tutor for help while in Practice
  sees a tutor response addressing their actual current question within one
  click, without ever leaving the Practice screen or losing sight of the
  question, and with zero additional subject-selection or typing required
  to get that first response.
- **SC-005**: Every screen and link not named by Stories 1-6 (Tutor's plain
  nav-link entry, single-enrollment learner cards, zero-enrollment learner
  cards, assigned-quiz questions, Practice/Dashboard/Mastery for a learner
  who never takes placement, actual browser-level navigation) shows no
  behavioral change from before this feature.
- **SC-006**: A learner who opens the Tutor from a subject's Dashboard link
  reaches chat in one click, with suggested prompts already worded around
  their current topic in that subject -- no subject-picker step, and no
  generic placeholder prompts when a topic recommendation exists.
- **SC-007**: A guardian can get a learner a placement-determined starting
  grade for a graded subject in one action from that subject's tile, with
  that learner's ability to practice, view their dashboard, or take an
  assigned quiz in the meantime completely unaffected by whether they've
  done so.
- **SC-008**: No learner ever loses an in-progress, unsubmitted Practice
  question or Placement answer set to in-app navigation without first
  being told it's about to happen and given the choice to stay.

## Assumptions

- The updated mockup's always-visible two-tab placeholder
  (`hint-placeholder-count="2"`) is a design-tool rendering artifact, not a
  literal requirement to always show tab chrome for a single-subject
  learner -- FR-005 instead follows this app's own established
  one-subject-means-no-switcher convention (`DashboardSubjectSection.tsx`,
  `PracticeFlow`'s subject `<select>`).
- "Learner subject tile" (the user's phrase) refers to the per-enrollment
  tab this feature adds to a learner's card on Guardian · My learners
  (FR-002), not the Dashboard's own subject-pill switcher -- no FR in
  this spec touches that switcher at all; it is simply never mentioned
  by any of Stories 1-6, so it keeps its current behavior by omission,
  not by any explicit "unchanged" requirement.
- The practice-shortcut's time limit is fixed at 15 minutes, per the user's
  literal request -- it does not expose a different time-limit choice; a
  guardian who wants a different limit, or untimed practice, still uses
  Practice's existing ordinary picker (reachable via "Open {name}'s
  learning" → Practice's own nav).
- The auto-sent hint request includes the current question's topic and
  stem text (both already fetched by Practice) as plain context in a
  message asking for a hint -- no new backend endpoint or Tutor Agent
  prompt change is required; the Tutor Agent's existing RAG-grounded,
  hint-oriented response behavior (spec 012, spec 016) applies to it
  exactly as it would to a learner's own typed question.
- This feature does not change how a learner's own enrollment is selected
  or defaulted for Dashboard/Mastery once a guardian opens the learner's
  session (`enterRealLearnerSession`) -- those pages keep showing their
  own existing subject pickers/pills unchanged by omission (no FR in this
  spec touches them, same as the previous Assumption's point about
  Dashboard's switcher); Practice's picker specifically stays unchanged
  for every entry path besides Story 2's shortcut (FR-011), and the
  Tutor's own blank picker is still shown when reached via its plain nav
  link (FR-019, FR-023). Placement is the one exception by design (Story
  5): it has no
  subject-picker to begin with (it's always reached already scoped to one
  subject, same as the demo learner today), so "skipping a picker" doesn't
  apply to it the way it does for Practice/Tutor. Four explicit entry
  points across Stories 2, 3, 4, and 5 (Practice's subject tile, Practice's
  "Ask the AI Tutor" links, Dashboard's "Ask the AI Tutor first" link, and
  a subject tile's "Take placement" action) now skip a picker screen or
  open a previously-unreachable real-learner flow.
- No change to join-code privacy, roster-listing opt-in, or any other
  spec 041 behavior -- this feature only adds visibility into enrollments
  that already exist and shortcuts into screens that already exist.
- The inline tutor panel (FR-012-FR-018) is additive to Practice's layout,
  not a replacement of the dedicated `/tutor` page -- `tutor-flow.tsx` and
  its own nav entry keep working exactly as before (FR-019) for anyone who
  wants a standalone tutor conversation outside of an in-progress practice
  question.
- Exact responsive behavior for narrow screens, where a true side-by-side
  split may not fit, is left to planning/implementation (e.g., a
  stacked/collapsible layout below the question) -- the one hard constraint
  from Clarifications is that the question is never hidden behind the open
  panel, not any specific breakpoint or pixel layout.
- "Relevant"/topic-worded prompts (FR-021) means the pills' wording
  references the topic's display name (e.g., substituting it into
  existing prompt phrasing) -- this does not require a new Tutor Agent
  capability or LLM call to generate prompts; it is a client-side template
  change using data (`getTopicPriorityPreview`) already fetched for an
  existing sidebar card.
- Dashboard's "Ask the AI Tutor first" link is scoped to whichever subject
  that `DashboardSubjectSection` instance is currently showing (the same
  subject its sibling "Start practicing" link already targets) -- FR-020
  does not change which subject is active on Dashboard, only what the
  Tutor link carries forward.
- "Take placement" (FR-024) checks for an existing `GradeProgress` row the
  same way `_assign_starting_grade_if_graded` already does -- it does not
  distinguish between "never took placement" and "already unlocked a
  grade organically through practice"; either one means the action is no
  longer offered, since both already produce the one `GradeProgress` row
  that matters (spec 019's existing monotonic unlocked-grade model has no
  concept of a placement-specific flag to check instead).
- Reusing today's placement UI (`placement-flow.tsx`) as-is for a real
  learner means its existing copy, pacing, and skip behavior carry over
  unchanged -- this feature does not revisit any of placement's own
  existing UX decisions (spec 025), only who can reach it.
- This feature does not backfill placement for already-enrolled real
  learners retroactively or prompt a guardian to take it -- "Take
  placement" simply becomes visible wherever the existing `GradeProgress`-
  absence check already happens to be true, with no migration or batch
  job needed.
- Neither Practice nor Placement persists "where the learner was" across
  a navigation away and back today (confirmed by investigation: both
  always start a fresh session/question set on mount, with no resume
  check) -- for a timed Practice session specifically, this means
  navigating away and starting again via FR-009 creates a second,
  independent `PracticeSession` row rather than resuming the first, which
  keeps ticking down unattended server-side until it naturally expires.
  This is pre-existing behavior the demo learner already has today, not a
  regression introduced by FR-008/FR-009 -- adding real-learner support to
  resume-detection/session-concurrency handling is out of scope for this
  feature; FR-010 only requires the shortcut's session to behave
  identically to one started the ordinary way, and today's ordinary way
  has this same characteristic.
- Story 6 addresses the above gap with a warning, not a fix -- it does
  not add persistence, resume, or session-concurrency handling of any
  kind; it only tells the learner what will happen before it happens, so
  leaving is a choice rather than an accidental loss.
- "Without submitting answers" (FR-028) is read the same way for both
  pages: Practice's current question has not yet received a response the
  server has graded; Placement's shown question set has not yet had
  `submit_placement` called on it, regardless of how many individual
  `responses` entries are locally filled in. Skipping a Placement question
  (`skip_placement_question`) does not count as submitting it (Edge
  Cases).
- The confirmation itself is an in-app UI element (e.g., a modal), not a
  second native browser dialog -- "in-app only" (Clarifications) means
  this feature adds no `window.confirm`/`beforeunload` call at all, only a
  route-change interception within the app's own navigation.

# Phase 0 Research: Guardian Multi-Subject Cards & Practice/Tutor Shortcuts

No open `[NEEDS CLARIFICATION]` markers remain in `spec.md` -- three
`/speckit-clarify` rounds resolved every product-decision ambiguity. The
decisions below are implementation-level findings made while tracing the
spec's requirements against the real codebase, each a direct application
of an already-established pattern rather than a new product decision.

## 1. Real-learner gating for the timed practice-session endpoints (FR-008)

**Decision**: Add `learner_id: uuid.UUID` and `claims: SessionClaims |
None = Depends(optional_session_claims)` to `start_practice_session`,
`get_practice_next_question`, `end_practice_session`, and
`get_practice_session_summary` (`backend/src/api/routes/
practice_sessions.py`). Each calls `require_learner_ownership_if_real(db,
learner_id=learner_id, claims=claims)` first, exactly as `questions.py`'s
`get_next_question` already does. `start_practice_session`'s existing
`has_placement_data(...)` 404 guard gets the identical bypass
`get_next_question` already has:

```python
if (learner is None or learner.is_demo) and not has_placement_data(
    db, learner_id=learner_id, subject_id=body.subject_id
):
    raise NotFoundError(...)
```

**Rationale**: `has_placement_data` actually checks for *any*
`MasteryState` row, not literally "took placement" -- `get_next_question`
already established that a non-demo real learner bypasses this gate
entirely (its own comment: "real placement stays explicitly out of
scope... a real learner can never satisfy this gate"). Without mirroring
that exact bypass, a real learner who has never answered a question in a
subject yet would 404 on Story 2's own shortcut the first time they ever
use it -- the single most common case, not an edge case.

**Alternatives considered**: Requiring placement (or at least one
practice answer) before a real learner can start a *timed* session,
leaving the bypass untouched. Rejected -- directly contradicts FR-027
("placement MUST remain entirely optional... no feature in this app... is
gated on placement having been completed") and spec 022's own original
design intent (timed practice has never required prior placement for the
demo learner either, once they have *any* mastery data).

**Call-site shape**: `get_practice_next_question`/`end_practice_session`/
`get_practice_session_summary` already resolve `learner_id` from the
`PracticeSession` row itself (`practice_session.learner_id`) -- they
don't need a new path parameter, only the same ownership check using that
already-resolved id, mirroring how `submit_placement`/
`skip_placement_question` need no change at all (research §2).

## 2. Real-learner gating for `start_placement` (FR-025)

**Decision**: Add the identical `learner_id`/`claims`/
`require_learner_ownership_if_real` pattern to `start_placement`
(`backend/src/api/routes/placement.py`). `submit_placement` and
`skip_placement_question` need **no change** -- both already derive
`learner_id`/`subject_id` from the `GeneratedQuestion` row a prior
`start_placement` call created (`questions[0].learner_id`), which is
already learner-agnostic by construction.

**Rationale**: Spec Context (Gap 5) and FR-025 already call this out
directly; this section exists to confirm there is no third endpoint in
this family needing the same treatment, and that the fix is genuinely
one call site, not three.

**Alternatives considered**: None -- this is the only viable shape given
the existing data model (`GeneratedQuestion.learner_id` already flows
through correctly for the other two endpoints).

## 3. Scoping assigned quizzes to the selected tab (FR-002)

**Decision**: Add an optional `roster_id: uuid.UUID | None = None` query
param to `GET /api/learners/{learner_id}/assignments`
(`quiz_assignments.py`'s `list_learner_assignments_route`), filtering
`.filter(QuizAssignment.roster_id == roster_id)` when provided.
`LearnerAssignments.tsx` gains an optional `rosterId` prop, threaded from
`GuardianLearnerCard.tsx`'s currently-selected tab
(`MyLearnerEnrollmentOut.roster_id`, already fetched).

**Rationale**: `GET /api/learners/{learner_id}/assignments` has no
subject/roster filter today -- every assignment across every one of a
learner's rosters is returned combined, which was invisible before this
feature (a learner only ever had one enrollment). Spec FR-002 requires
assigned quizzes to "switch per tab" once a learner has more than one;
without this filter, every tab would show the same combined list,
silently violating FR-002 the moment Story 1 ships. `QuizAssignment.
roster_id` already exists (non-nullable FK) -- every assignment is
already roster-scoped at creation time (`POST /api/rosters/{roster_id}/
assignments`), so this is a pure filter addition, not a new column or a
backfill.

**Alternatives considered**: Filtering client-side by deriving each
assignment's subject from its `topic_ids`. Rejected -- `topic_id` values
are plain content-artifact slugs (e.g. `quadratic-equations-and-
functions`), not subject-prefixed or guaranteed globally unique across
subjects (Constitution Principle III keeps them subject-agnostic by
design); reconstructing a subject from a topic id client-side would be
fragile and would need a new lookup anyway, with no corresponding
reduction in backend change.

## 4. Scoping standards/career-connections to the selected tab (FR-002)

**Decision**: Add an optional `subjectId?: string` prop to
`GuardianLearnerStandards.tsx` and `GuardianLearnerCareerConnections.tsx`.
When provided, filter the already-fetched `listLearnerEnrollments(...)`
result down to that one subject before computing mastery-state-per-
subject, instead of aggregating every enrollment's subject combined.

**Rationale**: Both components already fetch every enrollment and
combine their mastery-state-derived standards/career-connections into one
list -- correct behavior when a learner had at most one enrollment, but
it now mixes multiple classes' content together on a single tab, the same
FR-002 violation as research §3's assignments case. Filtering an
already-fetched array client-side needs no new request.

**Alternatives considered**: A new subject-scoped endpoint. Rejected --
both components already fetch everything they need; filtering client-side
is strictly simpler and the per-subject `getMasteryState` calls underneath
are unchanged either way.

## 5. In-app leave-guard mechanism (Story 6)

**Decision**: A new, tiny frontend-only module, `frontend/src/lib/
leave-guard.ts`, mirroring `visitor-state.ts`'s existing subscriber-
callback shape (`setGuard(message)` / `clearGuard()` / `onGuardChange(cb)`)
but held in a plain in-memory module-level variable, not `localStorage` --
a leave-guard is only ever meaningful within the current page's lifetime,
unlike session state that must survive a reload. `practice-flow.tsx`/
`placement-flow.tsx` call `setGuard(...)` on entering an unsubmitted state
and `clearGuard()` once submitted, matching FR-032/FR-033's exact trigger
conditions. `Nav.tsx`'s links and `router.push` call sites, plus Practice's
own "End session" link, check the guard before navigating and show
`LeaveGuardDialog.tsx` (a small, new, app-root-mounted confirmation modal)
instead of navigating immediately when a guard is active; confirming
calls through to the original navigation, canceling does nothing further.

**Rationale**: Next.js 16's App Router has no `router.events`-style
navigation-interception hook (that was Pages Router); intercepting
`<Link>`/`router.push` calls at each specific guarded site is the only
mechanism available, so a small shared module both sides (Nav, Practice,
Placement) can agree on is the minimum machinery that works, consistent
with this codebase's own existing `visitor-state.ts` precedent for
small, cross-component UI state that doesn't belong in a fetched API
response.

**Alternatives considered**: A native `beforeunload` listener. Rejected
by Clarifications (FR-031) -- browsers ignore its custom message text for
an actual browser-level navigation, so it would only ever show a
misleading generic prompt for no benefit. A full client-side router/
middleware library. Rejected -- massive overkill for guarding ~6 known
navigation sites in one app; no such dependency is in `tech-stack.md` and
none is needed here.

## 6. Mounting the inline tutor panel (Story 3)

**Decision**: `practice-flow.tsx`'s "answering"/"result" phase renders
`TutorChat.tsx` directly, inside a collapsible side-panel `<aside>`
alongside the question card (CSS grid/flex split, matching `tutor-
flow.tsx`'s own existing `lg:grid-cols-[1fr_320px]` sidebar precedent),
toggled open by the "Ask the AI Tutor" / "Talk it through" actions.
Opening it opens (or resumes) a Tutor Session for Practice's current
subject via the same `openTutorSession` call `tutor-flow.tsx` already
uses, then sends one auto-composed message -- "I'm stuck on this
question: '{question.stem}'. Can you give me a hint, not the answer?" --
through `TutorChat`'s existing `streamTutorMessage` path (no new prop on
`TutorChat` beyond the one added in research §7).

**Rationale**: `TutorChat.tsx` is already a fully self-contained,
reusable component (owns its own message list/streaming lifecycle,
documented in its own top comment as designed for exactly this kind of
reuse) -- mounting it a second time, in a second location, with a
different `sessionId`, is the entire integration; no new chat UI is
built.

**Alternatives considered**: A separate, trimmed-down "hint-only" widget.
Rejected by Clarifications (FR-013 requires the full multi-turn chat, not
a one-shot hint).

## 7. Topic-worded suggested prompts (Story 4)

**Decision**: `TutorChat.tsx`'s `SUGGESTED_PROMPTS` becomes a function
`suggestedPrompts(topicDisplayName?: string)` taking the already-fetched
topic name (from `tutor-flow.tsx`'s existing `getTopicPriorityPreview`
call, or Practice's own current question's topic for the inline panel)
and substituting it into the existing three prompts' wording (e.g. "Give
me a hint about {topic}, not the answer") when present, falling back to
today's exact generic wording when absent (`topicDisplayName` undefined).
`TutorChat` gains one new optional prop; no new fetch.

**Rationale**: Matches FR-020/FR-021 exactly -- client-side template
substitution over already-fetched data, no new Tutor Agent capability or
LLM call.

**Alternatives considered**: None -- the spec's Assumptions already ruled
out an LLM-generated prompt set ("this does not require a new Tutor Agent
capability or LLM call to generate prompts").

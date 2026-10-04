# Quickstart: Validating the Learner-Facing UI Redesign

## Prerequisites

- `frontend/` dependencies installed (`npm install`, if not already).
- The six reference mockups available locally at
  `/home/raja/cognivo_learner_screens/extracted/<Screen>-html/*.dc.html`
  (serve with `python3 -m http.server` from that folder per each export's own
  `README.md`, then open in a browser) for side-by-side comparison.
- A demo-learner session available locally (`npm run dev` in `frontend/`,
  backend running per its own quickstart) so each of the six live screens can
  be reached.

## Scenario 1 -- Visual match (SC-001)

1. Open each live screen (Dashboard, Practice, Mastery, Placement, AI Tutor,
   Answer Result) next to its corresponding mockup.
2. Confirm: primary/background colors, heading (Baloo 2) and body (Nunito)
   type, card corner radii, and pill-shaped nav/buttons match.
3. Expected: no unintentional deviation. Any deliberate deviation (e.g. a
   state the mockup doesn't depict) is a noted exception, not a silent gap.

## Scenario 2 -- Behavioral parity (FR-002, FR-003, SC-005)

For each of the five core flows, confirm the outcome is identical to
pre-redesign behavior (only presentation differs):

1. **Start practicing** from the Dashboard's "Up next" card → lands on
   Practice with the same next-selected question as before.
2. **Ask the AI Tutor** a question → same grounded/streamed answer behavior,
   same shielding behavior on an open question (spec 016).
3. **View Mastery** → same per-topic effective/peak mastery values, same
   sparkline data (spec 025 US2/US5), same "last practiced" elapsed-time text.
4. **Take Placement** → same per-question grading detail and refreshed
   acknowledgment behavior (spec 025 US3/US4).
5. **View an Answer Result** → same per-rubric-criterion detail (spec 025
   US3).

## Scenario 3 -- Safeguards survive the restyle (FR-004, FR-005, SC-003, SC-004)

1. Confirm the "DEMO ACCOUNT" badge is visible, in the new style, on every
   one of the six screens while signed in as the demo learner.
2. Confirm a topic with a warm "last practiced" indicator still shows its
   elapsed-time text label, not color alone.
3. Confirm an image-bearing question still renders non-empty alt text.

## Scenario 4 -- No regression outside scope (FR-007)

1. Load the instructor dashboard and a guardian/auth page.
2. Confirm neither changed visually as a side effect of this feature.

## Automated regression (SC-002)

```bash
cd frontend
npm run test
```

Expected: full suite passes. Any failing test must fail only because it
asserted a now-superseded visual class/style string (acceptable, update the
assertion) -- never because a data, navigation, or interaction outcome
changed.

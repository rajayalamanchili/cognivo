import { test, expect } from "@playwright/test";

// T057: guardian+instructor round trip against the live dev deployment
// (PLAYWRIGHT_BASE_URL, playwright.config.ts) -- register both, create
// a roster, join it, view the dashboard.
//
// "Flag and resolve a question" (tasks.md's literal T057 wording) is
// NOT exercised here -- traced while writing this spec, not assumed:
// every question-generating endpoint (`POST /api/subjects/{subject_id}/
// placement/start`, `GET /api/learners/{learner_id}/next-question`)
// resolves its learner via `services/demo_learner.get_demo_learner`
// internally rather than accepting an arbitrary `learner_id`, so a
// guardian-created real learner has no path -- through the UI or the
// API -- to ever generate a question to flag. The seeded demo learner
// *can* generate questions, but can't be enrolled into a roster by a
// guardian (`POST /api/rosters/join` requires `learner.guardian_id ==
// guardian.guardian_id`, and the demo learner's `guardian_id` is
// always null). Closing this gap is real-learner practice UI, which is
// outside all five of spec 010's user stories -- not something to
// silently route around here. This spec instead visits
// `/instructor/review` and confirms its empty state loads cleanly.

function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

const PASSWORD = "correct horse battery staple";

test("guardian and instructor round trip: register, roster, join, dashboard", async ({ page }) => {
  const instructorEmail = uniqueEmail("e2e-instructor");
  const guardianEmail = uniqueEmail("e2e-guardian");

  // Instructor: register, create an open roster.
  await page.goto("/instructor/register");
  await page.getByLabel("Email").fill(instructorEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "You're signed in" })).toBeVisible();

  await page.goto("/instructor/rosters");
  await page.getByRole("button", { name: "Create roster" }).click();
  await expect(page.getByTestId("roster-list")).toContainText("open");

  const rosterListText = await page.getByTestId("roster-list").innerText();
  const joinCodeMatch = rosterListText.match(/code:\s*(\S+)/);
  expect(joinCodeMatch, `no join code found in roster list: ${rosterListText}`).not.toBeNull();
  const joinCode = joinCodeMatch![1];

  // Guardian: register, add a learner, join the roster by code.
  await page.goto("/guardian/register");
  await page.getByLabel("Email").fill(guardianEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/guardian\/learners/);

  await page.getByLabel("Learner's name").fill("E2E Learner");
  await page.getByRole("button", { name: "Add learner" }).click();
  const addedLearner = page.getByTestId("added-learner").first();
  await expect(addedLearner).toContainText("E2E Learner added.");

  await addedLearner.getByPlaceholder("Join code").fill(joinCode);
  await addedLearner.getByRole("button", { name: "Join roster" }).click();
  await expect(addedLearner).toContainText("Joined the roster.");

  // Instructor: sign back in (guardian actions above overwrote the
  // session cookie) and confirm the learner shows up on the dashboard.
  await page.goto("/instructor/sign-in");
  await page.getByLabel("Email").fill(instructorEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.goto("/instructor/dashboard");
  await expect(page.getByTestId("dashboard-learners")).toContainText("E2E Learner");
  await expect(page.getByTestId("dashboard-learners")).toContainText(
    "Not enough data yet to confidently flag weak areas.",
  );

  // Content-review page loads cleanly (no flagged content exists for
  // this learner -- see the module doc comment above for why).
  await page.goto("/instructor/review");
  await expect(page.getByText("Nothing to review right now.")).toBeVisible();
});

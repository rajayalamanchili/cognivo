import { test, expect, type Locator, type Page } from "@playwright/test";

// Playwright E2E: instructor assigns a quiz -> the targeted learner's
// own guardian starts and completes it -> the instructor views the
// per-student result (spec 011, T034; quickstart.md's full round
// trip). Extends instructor-classroom-round-trip.spec.ts's register/
// roster/join pattern with this feature's assign/start/results steps.
//
// Uses two separate browser contexts (one per actor) rather than
// signing in and out on a single page, unlike
// instructor-classroom-round-trip.spec.ts: `/guardian/learners` has no
// "list my existing learners" fetch on mount (Milestone 7's page only
// ever shows a learner added in the *current* render, `page.tsx`'s
// `addedLearners` state), so a guardian who signs back in after the
// instructor creates the assignment would have no way to find their
// already-added learner again through the UI. Keeping the guardian's
// tab on `/guardian/learners` for the whole test sidesteps that
// pre-existing, out-of-scope gap; the new "Refresh" button (added
// alongside this spec) is what picks up the assignment the instructor
// creates in their own tab meanwhile.
//
// Question content is LLM-generated per run -- answers generically
// (first radio option / an arbitrary number), mirroring
// quiz-session.spec.ts's own convention. Assumes the roster-creation
// form's default (first) subject is "algebra-1" (`GET /api/subjects`
// orders by `subject_id`, and "algebra-1" < "biology"), so
// "integers-and-operations" -- this codebase's standard entry-level
// algebra topic, used throughout `backend/tests/integration/` -- is a
// valid `topic_id` for the created roster's subject.

const ENTRY_TOPIC = "integers-and-operations";
const PASSWORD = "correct horse battery staple";

function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function answerVisibleQuestion(page: Page, root: Page | Locator = page): Promise<void> {
  const firstRadio = root.locator('input[type="radio"]').first();
  const numericInput = root.locator('input[type="number"]').first();

  if (await firstRadio.isVisible().catch(() => false)) {
    await firstRadio.check();
    return;
  }
  await numericInput.waitFor({ state: "visible" });
  await numericInput.fill("1");
}

test("assign a quiz -> guardian completes it -> instructor sees the per-student result", async ({
  browser,
}) => {
  const instructorContext = await browser.newContext();
  const guardianContext = await browser.newContext();
  const instructorPage = await instructorContext.newPage();
  const guardianPage = await guardianContext.newPage();

  try {
    const instructorEmail = uniqueEmail("e2e-assign-instructor");
    const guardianEmail = uniqueEmail("e2e-assign-guardian");

    // Instructor: register (redirects straight to rosters), create an
    // open roster.
    await instructorPage.goto("/instructor/register");
    await instructorPage.getByLabel("Email").fill(instructorEmail);
    await instructorPage.getByLabel("Password").fill(PASSWORD);
    await instructorPage.getByRole("button", { name: "Create account" }).click();
    await expect(instructorPage).toHaveURL(/\/instructor\/rosters/);

    await instructorPage.getByRole("button", { name: "Create roster" }).click();
    await expect(instructorPage.getByTestId("roster-list")).toContainText("open");

    const rosterListText = await instructorPage.getByTestId("roster-list").innerText();
    const joinCodeMatch = rosterListText.match(/code:\s*(\S+)/);
    expect(joinCodeMatch, `no join code found in roster list: ${rosterListText}`).not.toBeNull();
    const joinCode = joinCodeMatch![1];

    // Guardian: register, add a learner, join the roster by code. Stays
    // on this page for the rest of the test (see module doc comment).
    await guardianPage.goto("/guardian/register");
    await guardianPage.getByLabel("Email").fill(guardianEmail);
    await guardianPage.getByLabel("Password").fill(PASSWORD);
    await guardianPage.getByRole("button", { name: "Create account" }).click();
    await expect(guardianPage).toHaveURL(/\/guardian\/learners/);

    await guardianPage.getByLabel("Learner's name").fill("E2E Assigned Learner");
    await guardianPage.getByRole("button", { name: "Add learner" }).click();
    const addedLearner = guardianPage.getByTestId("added-learner").first();
    await expect(addedLearner).toContainText("E2E Assigned Learner added.");

    await addedLearner.getByPlaceholder("Join code").fill(joinCode);
    await addedLearner.getByRole("button", { name: "Join roster" }).click();
    await expect(addedLearner).toContainText("Joined the roster.");

    const learnerAssignments = addedLearner.getByTestId("learner-assignments");
    await expect(learnerAssignments).toContainText("No assignments yet.");

    // Instructor: manage the roster, assign a one-question quiz to
    // everyone currently enrolled.
    await instructorPage.getByRole("button", { name: "Manage" }).click();
    const assignForm = instructorPage.getByTestId("assign-quiz-form");
    await expect(assignForm).toBeVisible();
    await assignForm.getByTestId("assign-topic-ids").fill(ENTRY_TOPIC);
    await assignForm.getByTestId("assign-question-count").fill("1");
    await assignForm.getByText("Assign quiz").click();

    const assignmentList = instructorPage.getByTestId("assignment-list");
    await expect(assignmentList).toContainText(ENTRY_TOPIC);
    await expect(assignmentList).toContainText("1 questions");

    // Guardian: refresh to pick up the new assignment, start it, and
    // answer its one question to completion.
    await learnerAssignments.getByText("Refresh").click();
    await expect(learnerAssignments).toContainText("Not started");
    await learnerAssignments.getByText("Start").click();

    const questionCard = addedLearner.getByTestId("question-card");
    await expect(questionCard).toBeVisible({ timeout: 30_000 });
    await answerVisibleQuestion(guardianPage, questionCard);
    await guardianPage.getByRole("button", { name: /submit answer/i }).click();

    const summary = addedLearner.getByTestId("quiz-summary");
    await expect(summary).toBeVisible({ timeout: 30_000 });
    await expect(summary).toContainText("Quiz completed");
    await expect(summary).toContainText("Score:");

    // Instructor: view the per-student result -- completed, with a
    // real score, broken out by learner rather than an aggregate.
    await instructorPage.getByText("View results").click();
    const results = instructorPage.getByTestId("assignment-results");
    await expect(results).toBeVisible();
    await expect(results).toContainText("E2E Assigned Learner");
    await expect(results).toContainText("completed");
    await expect(results).toContainText("1 / 1");
  } finally {
    await instructorContext.close();
    await guardianContext.close();
  }
});

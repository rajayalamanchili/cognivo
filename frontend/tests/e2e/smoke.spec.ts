import { test, expect, type Locator, type Page } from "@playwright/test";

// Deployment smoke test (SC-007), T062. Drives the actual deployed
// frontend URL through quickstart.md's placement-through-first-question
// flow via the browser -- not direct API calls -- against
// PLAYWRIGHT_BASE_URL (playwright.config.ts). Run after every deploy to
// `staging` and `main` (tech-stack.md's Testing & evaluation table).
//
// Question content/type is LLM-generated per run, so this answers
// generically (first option for multiple_choice, an arbitrary number for
// numeric) rather than asserting exact question text.

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

test("demo badge, placement, and first follow-up question all work end to end", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("demo-badge")).toBeVisible();

  await page.goto("/placement?subject=algebra-1");
  await expect(page.getByTestId("demo-badge")).toBeVisible();

  const questionFieldsets = page.locator("fieldset");
  await expect(questionFieldsets.first()).toBeVisible({ timeout: 30_000 });
  const questionCount = await questionFieldsets.count();
  for (let i = 0; i < questionCount; i++) {
    await answerVisibleQuestion(page, questionFieldsets.nth(i));
  }

  await page.getByRole("button", { name: "Submit Placement" }).click();

  await expect(page.getByTestId("mastery-view")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Placement Results" })).toBeVisible();

  await page.getByRole("link", { name: "Start Practicing" }).click();
  await expect(page).toHaveURL(/\/practice/);
  await expect(page.getByTestId("demo-badge")).toBeVisible();

  const questionCard = page.getByTestId("question-card");
  await expect(questionCard).toBeVisible({ timeout: 30_000 });
  await answerVisibleQuestion(page, questionCard);

  await page.getByRole("button", { name: "Submit Answer" }).click();

  await expect(
    page.getByRole("heading", { name: /Correct!|Not quite\./ }),
  ).toBeVisible({ timeout: 30_000 });
});

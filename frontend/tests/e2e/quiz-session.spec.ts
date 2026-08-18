import { test, expect, type Locator, type Page } from "@playwright/test";

// Playwright E2E: start a quiz via the UI, answer several questions,
// reach completion, confirm the score/summary render (T029).
//
// Question content/type is LLM-generated per run, so this answers
// generically (first option for multiple_choice, an arbitrary number
// for numeric) rather than asserting exact question text -- mirrors
// smoke.spec.ts's own convention.

const QUESTION_COUNT = 3;

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

test("a learner can take a full adaptive quiz to completion via the UI", async ({ page }) => {
  await page.goto("/quiz");

  const startForm = page.getByTestId("quiz-start-form");
  await expect(startForm).toBeVisible({ timeout: 30_000 });

  const firstTopicCheckbox = startForm.locator('input[type="checkbox"]').first();
  await firstTopicCheckbox.waitFor({ state: "visible", timeout: 30_000 });
  await firstTopicCheckbox.check();

  const questionCountInput = startForm.locator('input[type="number"]');
  await questionCountInput.fill(String(QUESTION_COUNT));

  await page.getByRole("button", { name: "Start Quiz" }).click();

  for (let i = 0; i < QUESTION_COUNT; i++) {
    const questionCard = page.getByTestId("question-card");
    await expect(questionCard).toBeVisible({ timeout: 30_000 });
    await answerVisibleQuestion(page, questionCard);
    await page.getByRole("button", { name: /submit answer/i }).click();
  }

  const summary = page.getByTestId("quiz-summary");
  await expect(summary).toBeVisible({ timeout: 30_000 });
  await expect(summary).toContainText(/completed|ended early/i);
  await expect(summary).toContainText("Score:");
});

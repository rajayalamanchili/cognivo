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
  // The bare landing page is neutral (no demo/login choice made yet) --
  // the badge only appears once actually on a demo page.
  await page.goto("/");
  await expect(page.getByTestId("demo-badge")).not.toBeVisible();

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

test("an image-bearing topic's image_url resolves against the live deployment", async ({
  request,
}) => {
  // Directly checks the live deployment's build-time image-sync
  // pipeline (research.md §1's flagged risk, SC-005) rather than
  // driving the practice flow to organically land on this topic: the
  // Sequencing Agent only selects systems-of-linear-equations once its
  // prerequisites are mastered, which the shared demo learner's actual
  // mastery state doesn't control run-to-run -- backend/tests/integration/
  // test_next_question_image.py already covers "the API response's
  // image_url is exactly this value" with a deterministic mastery
  // fixture. `content_image_url()` (image_asset.py) makes this URL a
  // fixed, known value regardless of which learner/run reaches it, so
  // hitting it directly is equivalent to fetching the same URL a real
  // question response would return.
  const response = await request.get("/content-images/algebra-1/systems-of-equations-graph.svg");
  expect(response.status()).toBe(200);
});

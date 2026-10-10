import { test, expect } from "@playwright/test";

// SC-005 (added post-/speckit-analyze finding G3): the report page
// renders whatever the latest evaluation run's state actually is --
// a published headline comparison, or a clear "no evaluation has run
// yet" message -- within one screen, no login required. Matches this
// project's existing unmocked E2E precedent (smoke.spec.ts): drives the
// real running app, no API mocking, since the published/unpublished
// state depends on whether backend/evaluation/reports/latest.json has
// been committed.
//
// The nav link to this page is temporarily hidden everywhere (user
// request, see Nav.tsx) -- the page itself is still reachable by direct
// URL, which is what this test now exercises instead of a nav click.

test("personalization evidence page renders its current state within one screen when reached directly", async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/personalization-eval");
  await expect(page).toHaveURL(/\/personalization-eval/);

  await expect(page.getByRole("heading", { name: "Personalization Evidence" })).toBeVisible();

  // Whichever state the currently-published report is in, the headline
  // (published) or the explicit not-yet-published message must appear --
  // never a stuck loading state or a blank page.
  const headline = page.getByText(/reached full mastery in/i);
  const unpublishedMessage = page.getByText(/no evaluation has run yet/i);
  await expect(headline.or(unpublishedMessage)).toBeVisible({ timeout: 15_000 });

  // No additional navigation/pagination required to see the result --
  // it's on the same screen this test navigated directly to.
  await expect(page).toHaveURL(/\/personalization-eval/);

  expect(consoleErrors).toEqual([]);
});

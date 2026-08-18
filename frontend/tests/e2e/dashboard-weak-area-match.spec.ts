import { test, expect } from "@playwright/test";
import { ensurePlacementCompleted, getDemoLearnerId } from "./helpers";

// Playwright E2E: calls GET /api/learners/{learner_id}/recommendations
// directly for algebra-1 and compares its weak_areas/next_step/
// data_sufficiency/broad_review_needed content against that subject's
// rendered weak-area section on /dashboard for the same learner --
// confirms an exact match (SC-003, hard gate per roadmap.md). T016.

const DATA_SUFFICIENCY_LABEL: Record<string, string> = {
  confident: "Confident",
  insufficient_data: "Not enough data yet to confidently flag weak areas.",
};

test("dashboard weak-area section matches a direct recommendations call exactly (SC-003)", async ({
  page,
  request,
}) => {
  const learnerId = await getDemoLearnerId(request);
  const subjectId = "algebra-1";

  await ensurePlacementCompleted(request, subjectId);

  const direct = await request.get(
    `/api/learners/${learnerId}/recommendations?subject_id=${subjectId}`,
  );
  expect(direct.ok(), await direct.text()).toBeTruthy();
  const expected = await direct.json();

  await page.goto("/dashboard");

  const section = page.getByTestId(`dashboard-subject-section-${subjectId}`);
  const weakAreaSlot = section.getByTestId("dashboard-weak-area-slot");
  await expect(weakAreaSlot.getByTestId("data-sufficiency-framing")).toBeVisible({
    timeout: 30_000,
  });

  await expect(weakAreaSlot.getByTestId("data-sufficiency-framing")).toHaveText(
    DATA_SUFFICIENCY_LABEL[expected.data_sufficiency],
  );

  if (expected.broad_review_needed) {
    await expect(weakAreaSlot.getByTestId("broad-review-framing")).toBeVisible();
  } else {
    await expect(weakAreaSlot.getByTestId("broad-review-framing")).toHaveCount(0);
  }

  const items = weakAreaSlot.locator("ul > li");
  await expect(items).toHaveCount(expected.weak_areas.length);
  for (let i = 0; i < expected.weak_areas.length; i++) {
    const flag = expected.weak_areas[i];
    const item = items.nth(i);
    await expect(item).toContainText(flag.display_name);
    await expect(item).toContainText(`${Math.round(flag.p_mastery * 100)}%`);
    await expect(item).toContainText(flag.next_step.recommended_display_name);
  }
});

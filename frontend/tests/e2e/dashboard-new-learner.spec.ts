import { test, expect } from "@playwright/test";
import { getDemoLearnerId, getMasteryState } from "./helpers";

// Playwright E2E: loads /dashboard and confirms the "just getting
// started" state for any subject the demo learner has zero
// MasteryState history in -- every topic "not yet assessed," the
// Recommendation Agent's own "insufficient data" framing, and a path
// visualization anchored on entry-level topics with the illustrative
// disclosure visible (SC-002). T027.
//
// Milestone 1-4 has exactly one seeded DemoLearnerProfile (no
// auth/multi-learner support yet -- spec.md Assumptions), so this test
// can't provision a dedicated brand-new learner of its own; other E2E
// specs in this suite (dashboard-freshness.spec.ts,
// dashboard-weak-area-match.spec.ts) deliberately exercise algebra-1
// only, leaving biology untouched by convention. Rather than hardcode
// that assumption, this test discovers at run time which subject(s)
// are still untouched and asserts the brand-new-learner state for
// those -- skipping only if the environment has no untouched subject
// left (e.g. a previous full quickstart.md run already touched both).

const SUBJECT_IDS = ["algebra-1", "biology"];

test("dashboard renders a coherent just-getting-started state for any untouched subject (SC-002)", async ({
  page,
  request,
}) => {
  const learnerId = await getDemoLearnerId(request);

  const untouchedSubjectIds: string[] = [];
  for (const subjectId of SUBJECT_IDS) {
    const topics = await getMasteryState(request, learnerId, subjectId);
    if (topics.every((t) => t.status === "unknown")) {
      untouchedSubjectIds.push(subjectId);
    }
  }

  test.skip(
    untouchedSubjectIds.length === 0,
    "no untouched subject available for the demo learner in this environment",
  );

  await page.goto("/dashboard");

  for (const subjectId of untouchedSubjectIds) {
    const section = page.getByTestId(`dashboard-subject-section-${subjectId}`);

    const masteryView = section.getByTestId("mastery-view");
    await expect(masteryView).toBeVisible({ timeout: 30_000 });
    await expect(masteryView).not.toContainText("Struggling");
    await expect(masteryView).not.toContainText("Developing");
    await expect(masteryView).not.toContainText("Mastered");
    const notYetAssessedCount = await masteryView.getByText("Not yet assessed").count();
    expect(notYetAssessedCount).toBeGreaterThan(0);

    const weakAreaSlot = section.getByTestId("dashboard-weak-area-slot");
    await expect(weakAreaSlot.getByTestId("data-sufficiency-framing")).toHaveText(
      "Not enough data yet to confidently flag weak areas.",
    );
    // insufficient_data is only reported when zero topics were
    // confidently classified weak -- weak_areas is guaranteed empty.
    await expect(weakAreaSlot.locator("ul > li")).toHaveCount(0);

    const pathSlot = section.getByTestId("dashboard-path-slot");
    await expect(pathSlot.getByTestId("path-visualization")).toBeVisible();
    await expect(pathSlot.getByTestId("next-topic")).toBeVisible();
    const upcomingTopics = pathSlot.getByTestId("upcoming-topics");
    if (await upcomingTopics.count()) {
      await expect(pathSlot.getByTestId("illustrative-disclosure")).toBeVisible();
    }
  }
});

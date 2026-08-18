import { test, expect } from "@playwright/test";
import { ensurePlacementCompleted, getDemoLearnerId, getMasteryState } from "./helpers";

// Playwright E2E: answers a question via the API for algebra-1, reloads
// /dashboard, and confirms the displayed mastery value matches the
// updated MasteryState exactly (SC-001; US1 Acceptance Scenario 2's
// freshness requirement) -- and confirms the untouched biology
// section still renders its own "just getting started" state
// correctly alongside the updated one (US1 Acceptance Scenario 3, the
// mixed-subject case). T010.

function formatTopicId(topicId: string): string {
  return topicId
    .split("-")
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

const BAND_LABEL: Record<string, string> = {
  struggling: "Struggling",
  developing: "Developing",
  mastered: "Mastered",
};

test("dashboard mastery value matches a fresh answer exactly, alongside an untouched subject", async ({
  page,
  request,
}) => {
  const learnerId = await getDemoLearnerId(request);

  const algebraSubjectId = "algebra-1";
  const untouchedSubjectId = "biology";

  await ensurePlacementCompleted(request, algebraSubjectId);

  const nextQuestion = await request.get(
    `/api/learners/${learnerId}/next-question?subject_id=${algebraSubjectId}`,
  );
  expect(nextQuestion.ok(), await nextQuestion.text()).toBeTruthy();
  const question = await nextQuestion.json();

  const response = question.question_type === "multiple_choice" ? 0 : 1;
  const answer = await request.post(`/api/questions/${question.question_id}/answer`, {
    data: { response },
  });
  expect(answer.ok(), await answer.text()).toBeTruthy();

  const algebraTopics = await getMasteryState(request, learnerId, algebraSubjectId);
  const answeredTopic = algebraTopics.find((t) => t.topic_id === question.topic_id);
  expect(answeredTopic).toBeDefined();
  expect(answeredTopic!.status).toBe("scored");

  const biologyTopics = await getMasteryState(request, learnerId, untouchedSubjectId);
  expect(biologyTopics.every((t) => t.status === "unknown")).toBe(true);

  await page.goto("/dashboard");

  const algebraSection = page.getByTestId(`dashboard-subject-section-${algebraSubjectId}`);
  await expect(algebraSection.getByTestId("mastery-view")).toBeVisible({ timeout: 30_000 });

  const answeredRow = algebraSection
    .getByTestId("mastery-view")
    .locator("li")
    .filter({ hasText: formatTopicId(question.topic_id) });
  await expect(answeredRow).toContainText(BAND_LABEL[answeredTopic!.band!]);
  await expect(answeredRow).toContainText(`${Math.round(answeredTopic!.p_mastery! * 100)}%`);

  const biologySection = page.getByTestId(`dashboard-subject-section-${untouchedSubjectId}`);
  await expect(biologySection.getByTestId("mastery-view")).toBeVisible({ timeout: 30_000 });
  for (const topic of biologyTopics) {
    const row = biologySection
      .getByTestId("mastery-view")
      .locator("li")
      .filter({ hasText: formatTopicId(topic.topic_id) });
    await expect(row).toContainText("Not yet assessed");
  }
});

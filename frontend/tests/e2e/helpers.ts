import { expect, type APIRequestContext } from "@playwright/test";

// Shared across this feature's E2E specs: completes a placement round
// via the API so the demo learner has real MasteryState/AssessmentEvent
// history for `subjectId` to exercise (mirrors
// backend/tests/integration/test_second_subject.py's placement pattern).
export async function ensurePlacementCompleted(
  request: APIRequestContext,
  subjectId: string,
): Promise<void> {
  const start = await request.post(`/api/subjects/${subjectId}/placement/start`);
  expect(start.ok(), await start.text()).toBeTruthy();
  const { placement_session_id, questions } = await start.json();
  const answers = questions.map((q: { question_id: string }) => ({
    question_id: q.question_id,
    response: 1,
  }));
  const submit = await request.post(`/api/placement/${placement_session_id}/submit`, {
    data: { answers },
  });
  expect(submit.ok(), await submit.text()).toBeTruthy();
}

export interface MasteryTopicEntry {
  topic_id: string;
  status: "unknown" | "scored";
  p_mastery: number | null;
  band: "struggling" | "developing" | "mastered" | null;
}

export async function getMasteryState(
  request: APIRequestContext,
  learnerId: string,
  subjectId: string,
): Promise<MasteryTopicEntry[]> {
  const response = await request.get(
    `/api/learners/${learnerId}/mastery-state?subject_id=${subjectId}`,
  );
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()).topics;
}

export async function getDemoLearnerId(request: APIRequestContext): Promise<string> {
  const response = await request.get("/api/demo-learner");
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()).learner_id;
}

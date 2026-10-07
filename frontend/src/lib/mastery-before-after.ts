import type { QuizAnswerResultEntry } from "@/services/api";

// FR-007: per-topic mastery before→after for the assigned-quiz summary,
// derived purely from `per_question_results` already on hand -- no new
// fetch. "Before" is the first prior_p_mastery seen for a topic in
// question order; "after" is the last posterior_p_mastery.
export interface TopicMasteryBeforeAfter {
  topic_id: string;
  before: number | null;
  after: number;
  question_count: number;
}

export function masteryBeforeAfterByTopic(
  results: QuizAnswerResultEntry[] | undefined,
): TopicMasteryBeforeAfter[] {
  if (!results || results.length === 0) return [];
  const order: string[] = [];
  const before = new Map<string, number | null>();
  const after = new Map<string, number>();
  const questionCount = new Map<string, number>();
  for (const result of results) {
    if (!before.has(result.topic_id)) {
      order.push(result.topic_id);
      before.set(result.topic_id, result.prior_p_mastery);
    }
    after.set(result.topic_id, result.posterior_p_mastery);
    questionCount.set(result.topic_id, (questionCount.get(result.topic_id) ?? 0) + 1);
  }
  return order.map((topic_id) => ({
    topic_id,
    before: before.get(topic_id) ?? null,
    after: after.get(topic_id) as number,
    question_count: questionCount.get(topic_id) as number,
  }));
}

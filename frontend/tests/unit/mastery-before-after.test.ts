import { describe, expect, it } from "vitest";
import { masteryBeforeAfterByTopic } from "@/lib/mastery-before-after";
import type { QuizAnswerResultEntry } from "@/services/api";

function entry(overrides: Partial<QuizAnswerResultEntry>): QuizAnswerResultEntry {
  return {
    question_id: "q",
    topic_id: "linear-equations",
    correct: true,
    prior_p_mastery: 0.3,
    posterior_p_mastery: 0.4,
    ...overrides,
  };
}

describe("masteryBeforeAfterByTopic", () => {
  it("groups by topic, taking the first prior and last posterior", () => {
    const results = masteryBeforeAfterByTopic([
      entry({ question_id: "q1", topic_id: "linear-equations", prior_p_mastery: 0.3, posterior_p_mastery: 0.4 }),
      entry({ question_id: "q2", topic_id: "linear-equations", prior_p_mastery: 0.4, posterior_p_mastery: 0.6 }),
      entry({ question_id: "q3", topic_id: "fractions", prior_p_mastery: 0.1, posterior_p_mastery: 0.2 }),
    ]);
    expect(results).toEqual([
      { topic_id: "linear-equations", before: 0.3, after: 0.6, question_count: 2 },
      { topic_id: "fractions", before: 0.1, after: 0.2, question_count: 1 },
    ]);
  });

  it("returns an empty list when results are absent or empty", () => {
    expect(masteryBeforeAfterByTopic(undefined)).toEqual([]);
    expect(masteryBeforeAfterByTopic([])).toEqual([]);
  });

  it("carries a null prior through as before: null", () => {
    const results = masteryBeforeAfterByTopic([entry({ prior_p_mastery: null })]);
    expect(results[0].before).toBeNull();
  });
});

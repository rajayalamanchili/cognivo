// Unit test: QuizSummary renders score and the per-topic/difficulty
// breakdown (FR-005), T016.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import QuizSummary from "@/components/QuizSummary";
import type { QuizSummaryResponse } from "@/services/api";

const summary: QuizSummaryResponse = {
  quiz_session_id: "quiz-1",
  subject_id: "algebra-1",
  topic_ids: ["linear-equations"],
  question_count: 5,
  status: "completed",
  started_at: "2026-08-18T12:00:00Z",
  completed_at: "2026-08-18T12:03:00Z",
  score: { correct: 4, total: 5 },
  summary: [
    { topic_id: "linear-equations", difficulty: "easy", correct: 1, total: 1 },
    { topic_id: "linear-equations", difficulty: "medium", correct: 2, total: 3 },
    { topic_id: "linear-equations", difficulty: "hard", correct: 1, total: 1 },
  ],
};

describe("QuizSummary", () => {
  it("renders the overall score", () => {
    render(<QuizSummary summary={summary} />);
    expect(screen.getByText(/4/)).toBeInTheDocument();
    expect(screen.getByText(/5/)).toBeInTheDocument();
  });

  it("renders a row per (topic, difficulty) breakdown entry", () => {
    render(<QuizSummary summary={summary} />);
    expect(screen.getAllByText("Linear Equations")).toHaveLength(3);
    expect(screen.getByText("Easy")).toBeInTheDocument();
    expect(screen.getByText("Medium")).toBeInTheDocument();
    expect(screen.getByText("Hard")).toBeInTheDocument();
    expect(screen.getByTestId("quiz-summary")).toHaveTextContent("1 / 1");
    expect(screen.getByTestId("quiz-summary")).toHaveTextContent("2 / 3");
  });

  it("renders an ended_early status distinctly from completed", () => {
    render(<QuizSummary summary={{ ...summary, status: "ended_early" }} />);
    expect(screen.getByTestId("quiz-summary")).toHaveTextContent(/ended early/i);
  });
});

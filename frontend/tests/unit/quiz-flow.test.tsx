// Unit test: the quiz flow renders distinct states for answering,
// completed, and ended_early (T017).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import QuizFlow from "@/app/quiz/quiz-flow";
import * as api from "@/services/api";
import { ApiError } from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getDemoLearner: vi.fn(),
    getSubjects: vi.fn(),
    getMasteryState: vi.fn(),
    startQuiz: vi.fn(),
    answerQuestion: vi.fn(),
    getQuizNextQuestion: vi.fn(),
    getQuizSummary: vi.fn(),
  };
});

const question = {
  question_id: "q1",
  topic_id: "linear-equations",
  difficulty: "easy" as const,
  question_type: "multiple_choice" as const,
  stem: "2 + 2?",
  options: ["3", "4", "5", "6"],
};

async function renderAndStartQuiz() {
  vi.mocked(api.getDemoLearner).mockResolvedValue({
    learner_id: "learner-1",
    display_name: "Demo Learner",
  });
  vi.mocked(api.getSubjects).mockResolvedValue({
    subjects: [{ subject_id: "algebra-1", display_name: "Algebra I" }],
  });
  vi.mocked(api.getMasteryState).mockResolvedValue({
    topics: [
      {
        topic_id: "linear-equations",
        status: "unknown",
        p_mastery: null,
        band: null,
        last_updated_at: null,
      },
    ],
  });

  render(<QuizFlow />);

  const checkbox = await screen.findByLabelText("Linear Equations");
  await userEvent.click(checkbox);
  await userEvent.click(screen.getByRole("button", { name: /start quiz/i }));
}

describe("QuizFlow", () => {
  beforeEach(() => {
    vi.mocked(api.getDemoLearner).mockReset();
    vi.mocked(api.getSubjects).mockReset();
    vi.mocked(api.getMasteryState).mockReset();
    vi.mocked(api.startQuiz).mockReset();
    vi.mocked(api.answerQuestion).mockReset();
    vi.mocked(api.getQuizNextQuestion).mockReset();
    vi.mocked(api.getQuizSummary).mockReset();
  });

  it("renders the answering phase with the reused QuestionCard after starting a quiz", async () => {
    vi.mocked(api.startQuiz).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      question,
    });

    await renderAndStartQuiz();

    expect(await screen.findByTestId("question-card")).toBeInTheDocument();
    expect(screen.queryByTestId("quiz-summary")).not.toBeInTheDocument();
  });

  it("transitions to the completed phase once the last question is answered", async () => {
    vi.mocked(api.startQuiz).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      question,
    });
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: null,
      posterior_p_mastery: 0.5,
      band: "developing",
    });
    vi.mocked(api.getQuizNextQuestion).mockRejectedValue(new ApiError(409, "already completed"));
    vi.mocked(api.getQuizSummary).mockResolvedValue({
      quiz_session_id: "quiz-1",
      subject_id: "algebra-1",
      topic_ids: ["linear-equations"],
      question_count: 1,
      status: "completed",
      started_at: "2026-08-18T12:00:00Z",
      completed_at: "2026-08-18T12:01:00Z",
      score: { correct: 1, total: 1 },
      summary: [
        { topic_id: "linear-equations", difficulty: "easy", correct: 1, total: 1 },
      ],
    });

    await renderAndStartQuiz();
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    const summary = await screen.findByTestId("quiz-summary");
    expect(summary).toHaveTextContent(/completed/i);
    expect(screen.queryByTestId("question-card")).not.toBeInTheDocument();
  });

  it("transitions to the ended_early phase when next-question reports it", async () => {
    vi.mocked(api.startQuiz).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      question,
    });
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: null,
      posterior_p_mastery: 0.5,
      band: "developing",
    });
    vi.mocked(api.getQuizNextQuestion).mockResolvedValue({
      status: "ended_early",
      question: null,
    });
    vi.mocked(api.getQuizSummary).mockResolvedValue({
      quiz_session_id: "quiz-1",
      subject_id: "algebra-1",
      topic_ids: ["linear-equations"],
      question_count: 5,
      status: "ended_early",
      started_at: "2026-08-18T12:00:00Z",
      completed_at: "2026-08-18T12:01:00Z",
      score: { correct: 1, total: 1 },
      summary: [
        { topic_id: "linear-equations", difficulty: "easy", correct: 1, total: 1 },
      ],
    });

    await renderAndStartQuiz();
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    const summary = await screen.findByTestId("quiz-summary");
    expect(summary).toHaveTextContent(/ended early/i);
    expect(screen.queryByTestId("question-card")).not.toBeInTheDocument();
  });

  it("shows the ended_early phase immediately if the very first question can't be generated", async () => {
    vi.mocked(api.startQuiz).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "ended_early",
      question: null,
    });
    vi.mocked(api.getQuizSummary).mockResolvedValue({
      quiz_session_id: "quiz-1",
      subject_id: "algebra-1",
      topic_ids: ["linear-equations"],
      question_count: 5,
      status: "ended_early",
      started_at: "2026-08-18T12:00:00Z",
      completed_at: "2026-08-18T12:00:00Z",
      score: { correct: 0, total: 0 },
      summary: [],
    });

    await renderAndStartQuiz();

    const summary = await screen.findByTestId("quiz-summary");
    expect(summary).toHaveTextContent(/ended early/i);
    await waitFor(() => expect(screen.queryByTestId("question-card")).not.toBeInTheDocument());
  });
});

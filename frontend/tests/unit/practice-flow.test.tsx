// Unit test: the practice flow's start screen (spec 022) -- untimed
// default behaves like before this feature, timed practice uses the
// new session endpoints and shows a countdown.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PracticeFlow from "@/app/practice/practice-flow";
import * as api from "@/services/api";
import { ApiError } from "@/services/api";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getDemoLearner: vi.fn(),
    getSubjects: vi.fn(),
    getNextQuestion: vi.fn(),
    answerQuestion: vi.fn(),
    startPracticeSession: vi.fn(),
    getPracticeNextQuestion: vi.fn(),
    endPracticeSession: vi.fn(),
    getPracticeSessionSummary: vi.fn(),
  };
});

const question = {
  question_id: "q1",
  topic_id: "linear-equations",
  difficulty: "easy" as const,
  question_type: "multiple_choice" as const,
  stem: "2 + 2?",
  options: ["3", "4", "5", "6"],
  image_url: null,
  image_alt_text: null,
  steps: null,
  read_aloud_eligible: false,
  unlocked_grade: null,
};

beforeEach(() => {
  vi.mocked(api.getDemoLearner).mockReset().mockResolvedValue({
    learner_id: "learner-1",
    display_name: "Demo Learner",
  });
  vi.mocked(api.getSubjects).mockReset().mockResolvedValue({
    subjects: [{ subject_id: "algebra-1", display_name: "Algebra I" }],
  });
  vi.mocked(api.getNextQuestion).mockReset();
  vi.mocked(api.answerQuestion).mockReset();
  vi.mocked(api.startPracticeSession).mockReset();
  vi.mocked(api.getPracticeNextQuestion).mockReset();
  vi.mocked(api.endPracticeSession).mockReset();
  vi.mocked(api.getPracticeSessionSummary).mockReset();
});

describe("PracticeFlow start screen", () => {
  it("shows the start form after loading", async () => {
    render(<PracticeFlow />);
    expect(await screen.findByTestId("practice-start-form")).toBeInTheDocument();
  });

  it("clicking Start practicing with Untimed selected uses the ordinary untimed endpoint", async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));

    expect(await screen.findByTestId("question-card")).toBeInTheDocument();
    expect(api.getNextQuestion).toHaveBeenCalledWith("learner-1", "algebra-1");
    expect(api.startPracticeSession).not.toHaveBeenCalled();
    expect(screen.queryByTestId("session-countdown")).not.toBeInTheDocument();
  });

  it("starting a timed session shows a countdown and an End practice now button", async () => {
    vi.mocked(api.startPracticeSession).mockResolvedValue({
      practice_session_id: "practice-1",
      status: "in_progress",
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      question,
    });
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    await userEvent.selectOptions(screen.getByLabelText("Time limit"), "1800");
    await userEvent.click(screen.getByRole("button", { name: /start timed practice/i }));

    expect(await screen.findByTestId("question-card")).toBeInTheDocument();
    expect(screen.getByTestId("session-countdown")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /end practice now/i })).toBeInTheDocument();
  });

  it("shows the ended screen when next-question reports the session has ended (409)", async () => {
    vi.mocked(api.startPracticeSession).mockResolvedValue({
      practice_session_id: "practice-1",
      status: "in_progress",
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      question,
    });
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: null,
      posterior_p_mastery: 0.5,
      band: "developing",
      graduated_score: null,
      criteria_met: null,
      criteria_missed: null,
      grading_logic_version: null,
      first_diverging_step_index: null,
      step_results: null,
    });
    vi.mocked(api.getPracticeNextQuestion).mockRejectedValue(
      new ApiError(409, "session has ended"),
    );
    vi.mocked(api.getPracticeSessionSummary).mockResolvedValue({
      practice_session_id: "practice-1",
      subject_id: "algebra-1",
      status: "ended_early",
      started_at: "2026-09-23T12:00:00Z",
      completed_at: "2026-09-23T12:30:00Z",
      score: { correct: 1, total: 1 },
      time_limit_seconds: 1800,
      elapsed_seconds: 1800,
      end_reason: "timer_expired",
    });

    render(<PracticeFlow />);
    await screen.findByTestId("practice-start-form");
    await userEvent.selectOptions(screen.getByLabelText("Time limit"), "1800");
    await userEvent.click(screen.getByRole("button", { name: /start timed practice/i }));
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
    await userEvent.click(await screen.findByRole("button", { name: /next question/i }));

    // SC-005: the configured time limit, actual time used, and how the
    // session ended are all visible on the ended screen.
    expect(await screen.findByTestId("practice-ended")).toBeInTheDocument();
    expect(screen.getByTestId("session-timing-summary")).toHaveTextContent(/30 min/);
    expect(screen.getByTestId("session-timing-summary")).toHaveTextContent(/time ran out/i);
    expect(screen.getByText(/Score:/).parentElement).toHaveTextContent("Score: 1 / 1");
  });
});

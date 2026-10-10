// Unit test: the practice flow's start screen (spec 022) -- untimed
// default behaves like before this feature, timed practice uses the
// new session endpoints and shows a countdown.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PracticeFlow from "@/app/practice/practice-flow";
import * as api from "@/services/api";
import { ApiError } from "@/services/api";
import { enterRealLearnerSession } from "@/lib/visitor-state";
import { clearGuard, isGuardActive } from "@/lib/leave-guard";

const REAL_LEARNER_SESSION_KEY = "cognivo:real-learner-session";

let mockSearchParams = new URLSearchParams();
const push = vi.fn();
vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ push }),
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getDemoLearner: vi.fn(),
    getSubjects: vi.fn(),
    getNextQuestion: vi.fn(),
    answerQuestion: vi.fn(),
    flagQuestion: vi.fn(),
    startPracticeSession: vi.fn(),
    getPracticeNextQuestion: vi.fn(),
    endPracticeSession: vi.fn(),
    getPracticeSessionSummary: vi.fn(),
    openTutorSession: vi.fn(),
    streamTutorMessage: vi.fn(),
    getTutorExchange: vi.fn(),
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
  mockSearchParams = new URLSearchParams();
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
  vi.mocked(api.flagQuestion).mockReset().mockResolvedValue(undefined);
  vi.mocked(api.openTutorSession).mockReset().mockResolvedValue({
    session_id: "tutor-session-1",
    subject_id: "algebra-1",
    status: "active",
  });
  vi.mocked(api.streamTutorMessage).mockReset().mockImplementation(
    async (_sessionId, _question, onEvent) => {
      onEvent({ delta: "Here's a hint." });
      onEvent({ done: true, exchange_id: "ex-1" });
    },
  );
  vi.mocked(api.getTutorExchange).mockReset().mockResolvedValue({
    exchange_id: "ex-1",
    status: "completed",
    question_text: "unused",
    answer_text: "unused",
    grounded: false,
    retrieved_passages: [],
  });
  window.localStorage.removeItem(REAL_LEARNER_SESSION_KEY);
  push.mockReset();
  clearGuard();
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

  it("ignores a countdown expiry that fires while a submit is already in flight (PR feedback)", async () => {
    vi.mocked(api.startPracticeSession).mockResolvedValue({
      practice_session_id: "practice-1",
      status: "in_progress",
      expires_at: new Date(Date.now() + 1200).toISOString(),
      question,
    });
    let resolveAnswer: (value: Awaited<ReturnType<typeof api.answerQuestion>>) => void;
    vi.mocked(api.answerQuestion).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveAnswer = resolve;
        }),
    );

    render(<PracticeFlow />);
    await screen.findByTestId("practice-start-form");
    await userEvent.selectOptions(screen.getByLabelText("Time limit"), "1800");
    await userEvent.click(screen.getByRole("button", { name: /start timed practice/i }));
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    // "End practice now" is disabled while the submit is in flight.
    expect(screen.getByRole("button", { name: /end practice now/i })).toBeDisabled();

    // Let the real countdown interval fire onExpire while still submitting.
    await new Promise((resolve) => setTimeout(resolve, 1500));
    expect(api.getPracticeNextQuestion).not.toHaveBeenCalled();

    resolveAnswer!({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: null,
      posterior_p_mastery: 0.5,
      refreshed: false,
      band: "developing",
      graduated_score: null,
      criteria_met: null,
      criteria_missed: null,
      grading_logic_version: null,
      first_diverging_step_index: null,
      step_results: null,
    });

    // handleSubmit's own resolution takes it to the "result" phase, not
    // a second automatic next-question fetch -- the guard's job is only
    // to have prevented the countdown's concurrent one above.
    await screen.findByTestId("answer-result-view");
    expect(api.getPracticeNextQuestion).not.toHaveBeenCalled();
  }, 10000);

  it("ignores a countdown expiry that fires while a free-text submission is already in flight (PR feedback)", async () => {
    const freeTextQuestion = {
      ...question,
      question_id: "q1-free",
      question_type: "free_text" as const,
      options: null,
    };
    vi.mocked(api.startPracticeSession).mockResolvedValue({
      practice_session_id: "practice-1",
      status: "in_progress",
      expires_at: new Date(Date.now() + 1200).toISOString(),
      question: freeTextQuestion,
    });
    let resolveAnswer: (value: Awaited<ReturnType<typeof api.answerQuestion>>) => void;
    vi.mocked(api.answerQuestion).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveAnswer = resolve;
        }),
    );

    render(<PracticeFlow />);
    await screen.findByTestId("practice-start-form");
    await userEvent.selectOptions(screen.getByLabelText("Time limit"), "1800");
    await userEvent.click(screen.getByRole("button", { name: /start timed practice/i }));
    await screen.findByTestId("free-text-answer-input");

    await userEvent.type(screen.getByRole("textbox"), "four");
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    // "End practice now" is disabled while the free-text grading call is
    // in flight, even though `phase` itself never left "answering" for
    // this question type (PR feedback: the earlier "submitting"-phase-
    // only guard missed this).
    expect(screen.getByRole("button", { name: /end practice now/i })).toBeDisabled();

    // Let the real countdown interval fire onExpire while still grading.
    await new Promise((resolve) => setTimeout(resolve, 1500));
    expect(api.getPracticeNextQuestion).not.toHaveBeenCalled();

    resolveAnswer!({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: null,
      posterior_p_mastery: 0.5,
      refreshed: false,
      band: "developing",
      graduated_score: null,
      criteria_met: null,
      criteria_missed: null,
      grading_logic_version: null,
      first_diverging_step_index: null,
      step_results: null,
    });

    await screen.findByTestId("answer-result-view");
    expect(api.getPracticeNextQuestion).not.toHaveBeenCalled();
  }, 10000);

  it("ignores an already_answered 409 without treating it as the session having ended (PR feedback)", async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    vi.mocked(api.answerQuestion).mockRejectedValue(
      new ApiError(409, "already answered", {
        error: "already_answered",
        question_id: question.question_id,
      }),
    );

    render(<PracticeFlow />);
    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    await waitFor(() => expect(api.answerQuestion).toHaveBeenCalledTimes(1));
    expect(api.getPracticeSessionSummary).not.toHaveBeenCalled();
    expect(screen.queryByTestId("practice-ended")).not.toBeInTheDocument();
    expect(screen.queryByTestId("answer-result-view")).not.toBeInTheDocument();
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
      refreshed: false,
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

  it("resolves the learner from an active real-learner session instead of the demo learner (spec 041 FR-016)", async () => {
    enterRealLearnerSession("learner-real-1", "Eli");
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));

    expect(await screen.findByTestId("question-card")).toBeInTheDocument();
    expect(api.getNextQuestion).toHaveBeenCalledWith("learner-real-1", "algebra-1");
    expect(api.getDemoLearner).not.toHaveBeenCalled();
  });

  it("passes the real learner id through to a timed session started via the ordinary picker (spec 044 FR-008 fix)", async () => {
    enterRealLearnerSession("learner-real-1", "Eli");
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
    expect(api.startPracticeSession).toHaveBeenCalledWith("algebra-1", 1800, "learner-real-1");
  });
});

describe("PracticeFlow autostart entry (spec 044 FR-009, US2)", () => {
  it("skips the picker and starts a 15-minute timed session directly for a real learner session + subject + autostart", async () => {
    enterRealLearnerSession("learner-real-1", "Eli");
    mockSearchParams = new URLSearchParams("subject=algebra-1&autostart=1");
    vi.mocked(api.startPracticeSession).mockResolvedValue({
      practice_session_id: "practice-1",
      status: "in_progress",
      expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
      question,
    });

    render(<PracticeFlow />);

    expect(await screen.findByTestId("question-card")).toBeInTheDocument();
    expect(screen.queryByTestId("practice-start-form")).not.toBeInTheDocument();
    expect(api.startPracticeSession).toHaveBeenCalledWith("algebra-1", 900, "learner-real-1");
    expect(screen.getByTestId("session-countdown")).toBeInTheDocument();
  });

  it("still shows the ordinary picker for a plain ?subject= link with no autostart (FR-011 regression guard)", async () => {
    enterRealLearnerSession("learner-real-1", "Eli");
    mockSearchParams = new URLSearchParams("subject=algebra-1");

    render(<PracticeFlow />);

    expect(await screen.findByTestId("practice-start-form")).toBeInTheDocument();
    expect(api.startPracticeSession).not.toHaveBeenCalled();
  });

  it("autostart is a no-op for the demo learner (no real-learner session active)", async () => {
    mockSearchParams = new URLSearchParams("subject=algebra-1&autostart=1");

    render(<PracticeFlow />);

    expect(await screen.findByTestId("practice-start-form")).toBeInTheDocument();
    expect(api.startPracticeSession).not.toHaveBeenCalled();
  });
});

describe("PracticeFlow inline Tutor panel (spec 044 FR-012-FR-019, US3)", () => {
  it('opens a side panel with an auto-sent hint on "Stuck? Ask the AI Tutor for a hint", question staying visible', async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByRole("button", { name: /stuck\? ask the ai tutor/i }));

    expect(await screen.findByTestId("tutor-chat")).toBeInTheDocument();
    // The question never got hidden -- FR-013.
    expect(screen.getByTestId("question-card")).toBeInTheDocument();
    expect(api.openTutorSession).toHaveBeenCalledWith("learner-1", "algebra-1");
    await waitFor(() =>
      expect(api.streamTutorMessage).toHaveBeenCalledWith(
        "tutor-session-1",
        expect.stringContaining(question.stem),
        expect.any(Function),
      ),
    );
    expect(screen.getByTestId("tutor-chat-learner-message")).toHaveTextContent(question.stem);
    await waitFor(() =>
      expect(screen.getByTestId("tutor-chat-tutor-message")).toHaveTextContent("Here's a hint."),
    );
  });

  it('opens the same inline panel from the result screen\'s "Talk it through with the AI Tutor"', async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: null,
      posterior_p_mastery: 0.5,
      refreshed: false,
      band: "developing",
      graduated_score: null,
      criteria_met: null,
      criteria_missed: null,
      grading_logic_version: null,
      first_diverging_step_index: null,
      step_results: null,
    });

    render(<PracticeFlow />);
    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
    await screen.findByTestId("answer-result-view");

    await userEvent.click(screen.getByRole("button", { name: /talk it through with the ai tutor/i }));

    expect(await screen.findByTestId("tutor-chat")).toBeInTheDocument();
    expect(api.openTutorSession).toHaveBeenCalledWith("learner-1", "algebra-1");
  });

  it("closing the panel preserves the in-progress answer and flag state underneath (FR-018)", async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByRole("button", { name: /flag this question for review/i }));
    await userEvent.click(screen.getByRole("button", { name: /submit flag/i }));
    await screen.findByText(/thanks — flagged for review/i);

    await userEvent.click(screen.getByRole("button", { name: /stuck\? ask the ai tutor/i }));
    await screen.findByTestId("tutor-chat");
    await userEvent.click(screen.getByRole("button", { name: /^close$/i }));

    expect(screen.queryByTestId("tutor-chat")).not.toBeInTheDocument();
    expect(screen.getByLabelText("4")).toBeChecked();
    expect(screen.getByText(/thanks — flagged for review/i)).toBeInTheDocument();
  });

  it("re-opening the panel resumes the already-open session rather than starting a new one (FR-017)", async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    await screen.findByTestId("question-card");

    await userEvent.click(screen.getByRole("button", { name: /stuck\? ask the ai tutor/i }));
    await screen.findByTestId("tutor-chat");
    await waitFor(() => expect(api.streamTutorMessage).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByRole("button", { name: /^close$/i }));
    await userEvent.click(screen.getByRole("button", { name: /stuck\? ask the ai tutor/i }));
    await screen.findByTestId("tutor-chat");

    // The same Tutor Session is reused -- no second `openTutorSession`
    // call -- even though re-opening sends a fresh hint into it.
    expect(api.openTutorSession).toHaveBeenCalledTimes(1);
  });
});

describe("PracticeFlow leave-guard (spec 044 FR-028/FR-032/FR-033, US6)", () => {
  it("sets the leave guard while a question is unsubmitted, and it is inactive beforehand", async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    expect(isGuardActive()).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    await screen.findByTestId("question-card");

    expect(isGuardActive()).toBe(true);
  });

  it("clears the leave guard once the answer is submitted", async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: 0.5,
      posterior_p_mastery: 0.6,
      refreshed: false,
      graduated_score: null,
      grading_logic_version: null,
      first_diverging_step_index: null,
    });
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    await screen.findByTestId("question-card");
    expect(isGuardActive()).toBe(true);

    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
    await waitFor(() => expect(isGuardActive()).toBe(false));
  });

  it("the untimed-practice End session link defers to the leave-guard confirmation instead of navigating immediately when a guard is active", async () => {
    vi.mocked(api.getNextQuestion).mockResolvedValue(question);
    render(<PracticeFlow />);

    await screen.findByTestId("practice-start-form");
    await userEvent.click(screen.getByRole("button", { name: /start practicing/i }));
    await screen.findByTestId("question-card");
    expect(isGuardActive()).toBe(true);

    await userEvent.click(screen.getByRole("link", { name: /end session/i }));
    expect(push).not.toHaveBeenCalled();
  });
});

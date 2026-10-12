// Unit test: AssignmentFlow (spec 011 US2 origin, moved to its own
// `/assignment` page) -- resolves start-vs-resume-vs-summary from the
// assignment's current status on mount, then answers/paces/summarizes
// identically to the inline flow it replaced.

import { render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AssignmentFlow from "@/app/assignment/assignment-flow";
import * as api from "@/services/api";
import { ApiError } from "@/services/api";
import { enterRealLearnerSession } from "@/lib/visitor-state";

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
    listLearnerAssignments: vi.fn(),
    startAssignment: vi.fn(),
    answerQuestion: vi.fn(),
    getQuizNextQuestion: vi.fn(),
    getQuizSummary: vi.fn(),
    getWhoAmI: vi.fn(),
    flagQuestion: vi.fn(),
  };
});

function assignmentAt(
  status: api.AssignmentStatus,
  quizSessionId: string | null = null,
): api.LearnerAssignment {
  return {
    assignment_id: "a1",
    topic_ids: ["integers-and-operations"],
    question_count: 5,
    due_at: null,
    cancelled_at: null,
    status,
    has_unviewed_activity: false,
    quiz_session_id: quizSessionId,
  };
}

function questionAt(id: string, unlockedGrade: number | null = null) {
  return {
    question_id: id,
    topic_id: "integers-and-operations",
    difficulty: "easy" as const,
    question_type: "multiple_choice" as const,
    stem: "What is 2 + 2?",
    options: ["3", "4", "5", "6"],
    image_url: null,
    image_alt_text: null,
    steps: null,
    read_aloud_eligible: false,
    unlocked_grade: unlockedGrade,
  };
}

beforeEach(() => {
  mockSearchParams = new URLSearchParams({ assignmentId: "a1" });
  vi.mocked(api.listLearnerAssignments).mockReset();
  vi.mocked(api.startAssignment).mockReset();
  vi.mocked(api.answerQuestion).mockReset();
  vi.mocked(api.getQuizNextQuestion).mockReset();
  vi.mocked(api.getQuizSummary).mockReset();
  vi.mocked(api.flagQuestion).mockReset();
  vi.mocked(api.getWhoAmI).mockReset().mockResolvedValue({
    account_type: "guardian",
    identifier: "guardian@example.com",
    read_aloud_default: false,
    pending_deletion_warnings: [],
  });
  window.localStorage.removeItem(REAL_LEARNER_SESSION_KEY);
  push.mockReset();
  enterRealLearnerSession("learner-1", "Riley");
});

describe("AssignmentFlow", () => {
  it("shows an error when no real learner session is present", async () => {
    window.localStorage.removeItem(REAL_LEARNER_SESSION_KEY);
    render(<AssignmentFlow />);
    expect(await screen.findByText(/open this quiz from the learner's card/i)).toBeInTheDocument();
  });

  it("starts a not_started assignment and shows its first question", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [assignmentAt("not_started")],
    });
    vi.mocked(api.startAssignment).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      handoff_token: null,
      question: questionAt("q1"),
    });

    render(<AssignmentFlow />);

    await waitFor(() => expect(api.startAssignment).toHaveBeenCalledWith("a1", "learner-1"));
    expect(await screen.findByText("What is 2 + 2?")).toBeInTheDocument();
    expect(screen.getByTestId("question-card")).toBeInTheDocument();
  });

  it("resumes an in_progress assignment via getQuizNextQuestion, not startAssignment", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [assignmentAt("in_progress", "quiz-stuck")],
    });
    vi.mocked(api.getQuizNextQuestion).mockResolvedValue({
      status: "in_progress",
      question: questionAt("q2"),
    });

    render(<AssignmentFlow />);

    await waitFor(() =>
      expect(api.getQuizNextQuestion).toHaveBeenCalledWith("quiz-stuck", null),
    );
    expect(api.startAssignment).not.toHaveBeenCalled();
    expect(await screen.findByText("What is 2 + 2?")).toBeInTheDocument();
  });

  it("goes straight to the summary for an already-finished assignment", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [assignmentAt("completed", "quiz-done")],
    });
    vi.mocked(api.getQuizSummary).mockResolvedValue({
      quiz_session_id: "quiz-done",
      subject_id: "algebra-1",
      topic_ids: ["integers-and-operations"],
      question_count: 5,
      status: "completed",
      started_at: "2026-09-20T00:00:00Z",
      completed_at: "2026-09-20T00:03:00Z",
      score: { correct: 4, total: 5 },
      summary: [],
    });

    render(<AssignmentFlow />);

    await waitFor(() => expect(api.getQuizSummary).toHaveBeenCalledWith("quiz-done", null));
    expect(await screen.findByTestId("quiz-summary")).toBeInTheDocument();
  });

  it("shows an error when the assignment id is not found in the learner's list", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({ assignments: [] });
    render(<AssignmentFlow />);
    expect(await screen.findByText(/could not be found/i)).toBeInTheDocument();
  });

  it("passes the start response's handoff_token through to next-question and answer calls (spec 019 FR-005b)", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [assignmentAt("not_started")],
    });
    vi.mocked(api.startAssignment).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      handoff_token: "handoff-token-abc",
      question: questionAt("q1"),
    });
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "integers-and-operations",
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
    vi.mocked(api.getQuizNextQuestion).mockResolvedValue({
      status: "in_progress",
      question: questionAt("q2"),
    });

    render(<AssignmentFlow />);
    await screen.findByText("What is 2 + 2?");

    fireEvent.click(screen.getByLabelText("4"));
    fireEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    await waitFor(() =>
      expect(api.answerQuestion).toHaveBeenCalledWith("q1", 1, false, "handoff-token-abc"),
    );
    await waitFor(() =>
      expect(api.getQuizNextQuestion).toHaveBeenCalledWith("quiz-1", "handoff-token-abc"),
    );
  });

  it("shows a stopping-point prompt after the recommended count for the learner's grade band (spec 019 FR-009)", async () => {
    const answerResult = {
      correct: true,
      topic_id: "integers-and-operations",
      prior_p_mastery: null,
      posterior_p_mastery: 0.5,
      refreshed: false,
      band: "developing" as const,
      graduated_score: null,
      criteria_met: null,
      criteria_missed: null,
      grading_logic_version: null,
      first_diverging_step_index: null,
      step_results: null,
    };

    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [assignmentAt("not_started")],
    });
    vi.mocked(api.startAssignment).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      handoff_token: null,
      question: questionAt("q1", 1),
    });
    vi.mocked(api.answerQuestion).mockResolvedValue(answerResult);
    vi.mocked(api.getQuizNextQuestion)
      .mockResolvedValueOnce({ status: "in_progress", question: questionAt("q2", 1) })
      .mockResolvedValueOnce({ status: "in_progress", question: questionAt("q3", 1) });

    render(<AssignmentFlow />);

    // Grade 1's pacing profile recommends a checkpoint at 3 questions
    // (frontend/src/lib/pacing.ts) -- answer three in a row.
    for (let i = 0; i < 3; i++) {
      await screen.findByText("What is 2 + 2?");
      fireEvent.click(screen.getByLabelText("4"));
      fireEvent.click(screen.getByRole("button", { name: /submit answer/i }));
    }

    expect(await screen.findByTestId("quiz-stopping-point")).toBeInTheDocument();
    expect(screen.queryByTestId("question-card")).not.toBeInTheDocument();
    expect(api.getQuizSummary).not.toHaveBeenCalled();
  });

  it("passes the start response's handoff_token to the summary call when the attempt ends early at start (stale-state regression)", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [assignmentAt("not_started")],
    });
    vi.mocked(api.startAssignment).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "ended_early",
      handoff_token: "handoff-token-xyz",
      question: null,
    });
    vi.mocked(api.getQuizSummary).mockResolvedValue({
      quiz_session_id: "quiz-1",
      subject_id: "integers-and-operations",
      topic_ids: ["integers-and-operations"],
      question_count: 5,
      status: "ended_early",
      started_at: "2026-09-20T00:00:00Z",
      completed_at: "2026-09-20T00:00:01Z",
      score: { correct: 0, total: 0 },
      summary: [],
    });

    render(<AssignmentFlow />);

    await waitFor(() =>
      expect(api.getQuizSummary).toHaveBeenCalledWith("quiz-1", "handoff-token-xyz"),
    );
    expect(await screen.findByTestId("quiz-summary")).toBeInTheDocument();
  });
});

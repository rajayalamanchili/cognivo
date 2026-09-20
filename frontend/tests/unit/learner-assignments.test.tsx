// Unit test: LearnerAssignments (spec 011, User Story 2, T028) --
// not_started/in_progress/completed/cancelled rendering and the
// "start" action.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LearnerAssignments from "@/components/LearnerAssignments";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    listLearnerAssignments: vi.fn(),
    startAssignment: vi.fn(),
    answerQuestion: vi.fn(),
    getQuizNextQuestion: vi.fn(),
    getQuizSummary: vi.fn(),
    flagQuestion: vi.fn(),
  };
});

const LEARNER_ID = "learner-1";

describe("LearnerAssignments", () => {
  beforeEach(() => {
    vi.mocked(api.listLearnerAssignments).mockReset();
    vi.mocked(api.startAssignment).mockReset();
    vi.mocked(api.answerQuestion).mockReset();
    vi.mocked(api.getQuizNextQuestion).mockReset();
    vi.mocked(api.getQuizSummary).mockReset();
    vi.mocked(api.flagQuestion).mockReset();
  });

  it("renders each assignment's status and a cancelled badge, with 'start' only for a not-yet-cancelled not_started assignment", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [
        {
          assignment_id: "a-not-started",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "not_started",
          has_unviewed_activity: false,
        },
        {
          assignment_id: "a-in-progress",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "in_progress",
          has_unviewed_activity: false,
        },
        {
          assignment_id: "a-completed",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: "2026-08-01T00:00:00Z",
          status: "completed",
          has_unviewed_activity: false,
        },
        {
          assignment_id: "a-cancelled-not-started",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: "2026-08-01T00:00:00Z",
          status: "not_started",
          has_unviewed_activity: false,
        },
      ],
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} />);

    await waitFor(() => expect(api.listLearnerAssignments).toHaveBeenCalledWith(LEARNER_ID));

    await waitFor(() => expect(screen.getAllByText("Not started")).toHaveLength(2));
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getAllByText("Completed")).toHaveLength(1);

    expect(screen.getByTestId("learner-assignment-cancelled-a-completed")).toBeInTheDocument();
    expect(
      screen.getByTestId("learner-assignment-cancelled-a-cancelled-not-started"),
    ).toBeInTheDocument();

    // Only the not_started, not-cancelled assignment gets a Start button.
    expect(screen.getAllByText("Start")).toHaveLength(1);
    expect(
      screen.getByTestId("learner-assignment-a-not-started").querySelector("button"),
    ).toHaveTextContent("Start");
  });

  it("starts a not_started assignment and shows its first question", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [
        {
          assignment_id: "a1",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "not_started",
          has_unviewed_activity: false,
        },
      ],
    });
    vi.mocked(api.startAssignment).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      handoff_token: null,
      question: {
        question_id: "q1",
        topic_id: "integers-and-operations",
        difficulty: "easy",
        question_type: "multiple_choice",
        stem: "What is 2 + 2?",
        options: ["3", "4", "5", "6"],
        image_url: null,
        image_alt_text: null,
        steps: null,
        read_aloud_eligible: false,
        unlocked_grade: null,
      },
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} />);
    fireEvent.click(await screen.findByText("Start"));

    await waitFor(() => expect(api.startAssignment).toHaveBeenCalledWith("a1", LEARNER_ID));
    expect(await screen.findByText("What is 2 + 2?")).toBeInTheDocument();
    expect(screen.getByTestId("question-card")).toBeInTheDocument();
  });

  it("shows a start error without leaving the list", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [
        {
          assignment_id: "a1",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "not_started",
          has_unviewed_activity: false,
        },
      ],
    });
    vi.mocked(api.startAssignment).mockRejectedValue(new Error("already_attempted"));

    render(<LearnerAssignments learnerId={LEARNER_ID} />);
    fireEvent.click(await screen.findByText("Start"));

    expect(await screen.findByTestId("learner-assignment-start-error")).toHaveTextContent(
      "already_attempted",
    );
    expect(screen.getByTestId("learner-assignments")).toBeInTheDocument();
  });

  it("shows an unviewed-activity badge only when has_unviewed_activity is true", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [
        {
          assignment_id: "a-unviewed",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "completed",
          has_unviewed_activity: true,
        },
        {
          assignment_id: "a-viewed",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "completed",
          has_unviewed_activity: false,
        },
      ],
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} />);

    expect(await screen.findByTestId("learner-assignment-unviewed-a-unviewed")).toBeInTheDocument();
    expect(screen.queryByTestId("learner-assignment-unviewed-a-viewed")).not.toBeInTheDocument();
  });

  it("passes the start response's handoff_token through to next-question and answer calls (spec 019 FR-005b)", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [
        {
          assignment_id: "a1",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "not_started",
          has_unviewed_activity: false,
        },
      ],
    });
    vi.mocked(api.startAssignment).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      handoff_token: "handoff-token-abc",
      question: {
        question_id: "q1",
        topic_id: "integers-and-operations",
        difficulty: "easy",
        question_type: "multiple_choice",
        stem: "What is 2 + 2?",
        options: ["3", "4", "5", "6"],
        image_url: null,
        image_alt_text: null,
        steps: null,
        read_aloud_eligible: false,
        unlocked_grade: null,
      },
    });
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "integers-and-operations",
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
    vi.mocked(api.getQuizNextQuestion).mockResolvedValue({
      status: "in_progress",
      question: {
        question_id: "q2",
        topic_id: "integers-and-operations",
        difficulty: "easy",
        question_type: "multiple_choice",
        stem: "What is 3 + 3?",
        options: ["3", "4", "5", "6"],
        image_url: null,
        image_alt_text: null,
        steps: null,
        read_aloud_eligible: false,
        unlocked_grade: null,
      },
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} />);
    fireEvent.click(await screen.findByText("Start"));
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

  it("refetches the list when 'Refresh' is clicked", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValueOnce({ assignments: [] });
    render(<LearnerAssignments learnerId={LEARNER_ID} />);
    await waitFor(() => expect(api.listLearnerAssignments).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("No assignments yet.")).toBeInTheDocument();

    vi.mocked(api.listLearnerAssignments).mockResolvedValueOnce({
      assignments: [
        {
          assignment_id: "a1",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "not_started",
          has_unviewed_activity: false,
        },
      ],
    });
    fireEvent.click(screen.getByText("Refresh"));

    await waitFor(() => expect(api.listLearnerAssignments).toHaveBeenCalledTimes(2));
    expect(await screen.findByTestId("learner-assignment-a1")).toBeInTheDocument();
  });
});

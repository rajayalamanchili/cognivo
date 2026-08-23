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
        },
        {
          assignment_id: "a-in-progress",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "in_progress",
        },
        {
          assignment_id: "a-completed",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: "2026-08-01T00:00:00Z",
          status: "completed",
        },
        {
          assignment_id: "a-cancelled-not-started",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: "2026-08-01T00:00:00Z",
          status: "not_started",
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
        },
      ],
    });
    vi.mocked(api.startAssignment).mockResolvedValue({
      quiz_session_id: "quiz-1",
      status: "in_progress",
      question: {
        question_id: "q1",
        topic_id: "integers-and-operations",
        difficulty: "easy",
        question_type: "multiple_choice",
        stem: "What is 2 + 2?",
        options: ["3", "4", "5", "6"],
      },
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} />);
    fireEvent.click(await screen.findByText("Start"));

    await waitFor(() =>
      expect(api.startAssignment).toHaveBeenCalledWith("a1", LEARNER_ID),
    );
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
        },
      ],
    });
    fireEvent.click(screen.getByText("Refresh"));

    await waitFor(() => expect(api.listLearnerAssignments).toHaveBeenCalledTimes(2));
    expect(await screen.findByTestId("learner-assignment-a1")).toBeInTheDocument();
  });
});

// Unit test: RostersFlow's "assign a quiz" form (spec 011, T016) --
// confirms subset vs. "all" targeting is sent correctly to
// `createAssignment`, and that submission is blocked (empty-target
// validation, FR-003) when "Choose learners" mode has nothing checked.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RostersFlow from "@/app/instructor/rosters/rosters-flow";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    listRosters: vi.fn(),
    getSubjects: vi.fn(),
    listRosterRequests: vi.fn(),
    listRosterEnrollments: vi.fn(),
    listRosterAssignments: vi.fn(),
    createAssignment: vi.fn(),
    cancelAssignment: vi.fn(),
    getAssignmentDetail: vi.fn(),
  };
});

const ROSTER = { roster_id: "roster-1", subject_id: "algebra-1", enrollment_mode: "open" as const };
const LEARNER_A = { learner_id: "learner-a", display_name: "Learner A" };
const LEARNER_B = { learner_id: "learner-b", display_name: "Learner B" };

async function renderAndSelectRoster() {
  vi.mocked(api.listRosters).mockResolvedValue({ rosters: [ROSTER] });
  vi.mocked(api.getSubjects).mockResolvedValue({
    subjects: [{ subject_id: "algebra-1", display_name: "Algebra I" }],
  });
  vi.mocked(api.listRosterRequests).mockResolvedValue({ requests: [] });
  vi.mocked(api.listRosterEnrollments).mockResolvedValue({
    enrollments: [LEARNER_A, LEARNER_B],
  });
  vi.mocked(api.listRosterAssignments).mockResolvedValue({ assignments: [] });

  render(<RostersFlow />);
  await waitFor(() => expect(api.listRosters).toHaveBeenCalled());
  fireEvent.click(await screen.findByText("Manage"));
  await waitFor(() => expect(api.listRosterEnrollments).toHaveBeenCalledWith("roster-1"));
  await screen.findByTestId("assign-quiz-form");
}

describe("RostersFlow assign-a-quiz form", () => {
  beforeEach(() => {
    vi.mocked(api.listRosters).mockReset();
    vi.mocked(api.getSubjects).mockReset();
    vi.mocked(api.listRosterRequests).mockReset();
    vi.mocked(api.listRosterEnrollments).mockReset();
    vi.mocked(api.listRosterAssignments).mockReset();
    vi.mocked(api.createAssignment).mockReset();
    vi.mocked(api.cancelAssignment).mockReset();
  });

  it("submits 'all' targeting by default", async () => {
    await renderAndSelectRoster();
    vi.mocked(api.createAssignment).mockResolvedValue({
      assignment_id: "assignment-1",
      roster_id: "roster-1",
      subject_id: "algebra-1",
      topic_ids: ["integers-and-operations"],
      question_count: 5,
      due_at: null,
      target_learner_ids: [LEARNER_A.learner_id, LEARNER_B.learner_id],
    });

    fireEvent.change(screen.getByTestId("assign-topic-ids"), {
      target: { value: "integers-and-operations" },
    });
    fireEvent.click(screen.getByText("Assign quiz"));

    await waitFor(() =>
      expect(api.createAssignment).toHaveBeenCalledWith("roster-1", {
        topicIds: ["integers-and-operations"],
        questionCount: 5,
        dueAt: null,
        learnerIds: "all",
      }),
    );
  });

  it("submits only the checked learners in subset mode", async () => {
    await renderAndSelectRoster();
    vi.mocked(api.createAssignment).mockResolvedValue({
      assignment_id: "assignment-2",
      roster_id: "roster-1",
      subject_id: "algebra-1",
      topic_ids: ["integers-and-operations"],
      question_count: 3,
      due_at: null,
      target_learner_ids: [LEARNER_A.learner_id],
    });

    fireEvent.change(screen.getByTestId("assign-topic-ids"), {
      target: { value: "integers-and-operations" },
    });
    fireEvent.change(screen.getByTestId("assign-question-count"), { target: { value: "3" } });
    fireEvent.click(screen.getByTestId("assign-target-subset"));
    fireEvent.click(screen.getByTestId(`assign-learner-${LEARNER_A.learner_id}`));
    fireEvent.click(screen.getByText("Assign quiz"));

    await waitFor(() =>
      expect(api.createAssignment).toHaveBeenCalledWith("roster-1", {
        topicIds: ["integers-and-operations"],
        questionCount: 3,
        dueAt: null,
        learnerIds: [LEARNER_A.learner_id],
      }),
    );
  });

  it("blocks submission when subset mode has no learner checked (FR-003)", async () => {
    await renderAndSelectRoster();

    fireEvent.change(screen.getByTestId("assign-topic-ids"), {
      target: { value: "integers-and-operations" },
    });
    fireEvent.click(screen.getByTestId("assign-target-subset"));

    expect(screen.getByText("Assign quiz")).toBeDisabled();
    expect(api.createAssignment).not.toHaveBeenCalled();
  });

  it("blocks submission when topic ids is empty", async () => {
    await renderAndSelectRoster();

    expect(screen.getByText("Assign quiz")).toBeDisabled();
    expect(api.createAssignment).not.toHaveBeenCalled();
  });
});

describe("RostersFlow per-assignment results view", () => {
  const ASSIGNMENT = {
    assignment_id: "assignment-1",
    topic_ids: ["integers-and-operations"],
    question_count: 5,
    due_at: null,
    cancelled_at: null,
    created_at: "2026-08-23T00:00:00Z",
  };

  beforeEach(() => {
    vi.mocked(api.listRosters).mockReset();
    vi.mocked(api.getSubjects).mockReset();
    vi.mocked(api.listRosterRequests).mockReset();
    vi.mocked(api.listRosterEnrollments).mockReset();
    vi.mocked(api.listRosterAssignments).mockReset();
    vi.mocked(api.getAssignmentDetail).mockReset();
  });

  async function renderWithOneAssignment() {
    vi.mocked(api.listRosters).mockResolvedValue({ rosters: [ROSTER] });
    vi.mocked(api.getSubjects).mockResolvedValue({
      subjects: [{ subject_id: "algebra-1", display_name: "Algebra I" }],
    });
    vi.mocked(api.listRosterRequests).mockResolvedValue({ requests: [] });
    vi.mocked(api.listRosterEnrollments).mockResolvedValue({
      enrollments: [LEARNER_A, LEARNER_B],
    });
    vi.mocked(api.listRosterAssignments).mockResolvedValue({ assignments: [ASSIGNMENT] });

    render(<RostersFlow />);
    await waitFor(() => expect(api.listRosters).toHaveBeenCalled());
    fireEvent.click(await screen.findByText("Manage"));
    await screen.findByTestId(`assignment-${ASSIGNMENT.assignment_id}`);
  }

  it("shows a mixed-status per-student results table on 'View results'", async () => {
    await renderWithOneAssignment();
    vi.mocked(api.getAssignmentDetail).mockResolvedValue({
      assignment_id: ASSIGNMENT.assignment_id,
      topic_ids: ASSIGNMENT.topic_ids,
      question_count: ASSIGNMENT.question_count,
      due_at: null,
      cancelled_at: null,
      learners: [
        {
          learner_id: LEARNER_A.learner_id,
          display_name: "Learner A",
          status: "completed",
          score: { correct: 4, total: 5 },
        },
        {
          learner_id: LEARNER_B.learner_id,
          display_name: "Learner B",
          status: "not_started",
          score: null,
        },
      ],
    });

    fireEvent.click(screen.getByText("View results"));

    await waitFor(() =>
      expect(api.getAssignmentDetail).toHaveBeenCalledWith("roster-1", ASSIGNMENT.assignment_id),
    );
    const table = await screen.findByTestId("assignment-results");
    expect(table).toBeInTheDocument();

    const rowA = screen.getByTestId(`assignment-result-${LEARNER_A.learner_id}`);
    expect(rowA).toHaveTextContent("Learner A");
    expect(rowA).toHaveTextContent("completed");
    expect(rowA).toHaveTextContent("4 / 5");

    const rowB = screen.getByTestId(`assignment-result-${LEARNER_B.learner_id}`);
    expect(rowB).toHaveTextContent("Learner B");
    expect(rowB).toHaveTextContent("not_started");
    expect(rowB).toHaveTextContent("—");
  });

  it("shows an error without crashing when the results fetch fails", async () => {
    await renderWithOneAssignment();
    vi.mocked(api.getAssignmentDetail).mockRejectedValue(new Error("network error"));

    fireEvent.click(screen.getByText("View results"));

    expect(await screen.findByTestId("assignment-results-error")).toHaveTextContent(
      "network error",
    );
  });

  it("closes the results table when 'Close' is clicked", async () => {
    await renderWithOneAssignment();
    vi.mocked(api.getAssignmentDetail).mockResolvedValue({
      assignment_id: ASSIGNMENT.assignment_id,
      topic_ids: ASSIGNMENT.topic_ids,
      question_count: ASSIGNMENT.question_count,
      due_at: null,
      cancelled_at: null,
      learners: [],
    });

    fireEvent.click(screen.getByText("View results"));
    await screen.findByTestId("assignment-results");

    fireEvent.click(screen.getByText("Close"));
    expect(screen.queryByTestId("assignment-results")).not.toBeInTheDocument();
  });
});

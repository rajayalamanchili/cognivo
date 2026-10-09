// Unit test: RostersFlow's "assign a quiz" form (spec 011, T016) --
// confirms subset vs. "all" targeting is sent correctly to
// `createAssignment`, and that submission is blocked (empty-target
// validation, FR-003) when "Choose learners" mode has nothing checked.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RostersFlow from "@/app/instructor/rosters/rosters-flow";
import * as api from "@/services/api";
import { ApiError } from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    listRosters: vi.fn(),
    getSubjects: vi.fn(),
    getWhoAmI: vi.fn(),
    listRosterRequests: vi.fn(),
    listRosterEnrollments: vi.fn(),
    listRosterAssignments: vi.fn(),
    createAssignment: vi.fn(),
    cancelAssignment: vi.fn(),
    getAssignmentDetail: vi.fn(),
    updateRosterListing: vi.fn(),
    updateInstructorDisplayName: vi.fn(),
  };
});

// spec 043 FR-009: every RostersFlow render now also calls `getWhoAmI`
// once (classroom-defaults pre-fill) -- defaulted here so every
// existing test in this file keeps rendering the normal roster UI
// instead of RostersFlow's load-error branch.
const WHOAMI_NO_DEFAULTS = {
  account_type: "instructor" as const,
  identifier: "instructor@example.com",
  pending_deletion_warnings: [],
};

const ROSTER = {
  roster_id: "roster-1",
  subject_id: "algebra-1",
  enrollment_mode: "open" as const,
  is_listed: false,
};
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
    vi.mocked(api.getWhoAmI).mockReset().mockResolvedValue(WHOAMI_NO_DEFAULTS);
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
    vi.mocked(api.getWhoAmI).mockReset().mockResolvedValue(WHOAMI_NO_DEFAULTS);
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

// spec 041 FR-017/FR-018 (T044): the "List in directory" toggle --
// disabled on a closed roster, and the inline display-name prompt
// that appears when the instructor has none set.
describe("RostersFlow 'List in directory' toggle", () => {
  const OPEN_ROSTER = {
    roster_id: "roster-open",
    subject_id: "algebra-1",
    enrollment_mode: "open" as const,
    is_listed: false,
  };
  const CLOSED_ROSTER = {
    roster_id: "roster-closed",
    subject_id: "algebra-1",
    enrollment_mode: "closed" as const,
    is_listed: false,
  };

  beforeEach(() => {
    vi.mocked(api.listRosters).mockReset();
    vi.mocked(api.getSubjects).mockReset();
    vi.mocked(api.getWhoAmI).mockReset().mockResolvedValue(WHOAMI_NO_DEFAULTS);
    vi.mocked(api.updateRosterListing).mockReset();
    vi.mocked(api.updateInstructorDisplayName).mockReset();
    vi.mocked(api.getSubjects).mockResolvedValue({
      subjects: [{ subject_id: "algebra-1", display_name: "Algebra I" }],
    });
  });

  it("disables the toggle on a closed roster", async () => {
    vi.mocked(api.listRosters).mockResolvedValue({ rosters: [CLOSED_ROSTER] });
    render(<RostersFlow />);

    await waitFor(() => expect(api.listRosters).toHaveBeenCalled());
    const checkbox = await screen.findByLabelText("List in directory");
    expect(checkbox).toBeDisabled();
  });

  it("toggling an open roster's listing calls updateRosterListing and reflects the new state", async () => {
    vi.mocked(api.listRosters).mockResolvedValue({ rosters: [OPEN_ROSTER] });
    vi.mocked(api.updateRosterListing).mockResolvedValue({
      roster_id: OPEN_ROSTER.roster_id,
      subject_id: "algebra-1",
      enrollment_mode: "open",
      join_code: "ALG-1234",
      is_listed: true,
    });
    render(<RostersFlow />);

    await waitFor(() => expect(api.listRosters).toHaveBeenCalled());
    const checkbox = await screen.findByLabelText("List in directory");
    fireEvent.click(checkbox);

    await waitFor(() =>
      expect(api.updateRosterListing).toHaveBeenCalledWith(OPEN_ROSTER.roster_id, "open", true),
    );
    await waitFor(() => expect(checkbox).toBeChecked());
  });

  it("shows an inline display-name prompt when the instructor has none set, and retries the toggle after setting it", async () => {
    vi.mocked(api.listRosters).mockResolvedValue({ rosters: [OPEN_ROSTER] });
    vi.mocked(api.updateRosterListing)
      .mockRejectedValueOnce(
        new ApiError(422, "failed", { detail: "instructor_display_name_required" }),
      )
      .mockResolvedValueOnce({
        roster_id: OPEN_ROSTER.roster_id,
        subject_id: "algebra-1",
        enrollment_mode: "open",
        join_code: "ALG-1234",
        is_listed: true,
      });
    vi.mocked(api.updateInstructorDisplayName).mockResolvedValue({
      display_name: "Ms. Rivera",
      theme: null,
      larger_text: null,
      reduce_motion: null,
      notifications_enabled: null,
      default_enrollment_mode: null,
      default_due_date_offset_days: null,
    });
    render(<RostersFlow />);

    await waitFor(() => expect(api.listRosters).toHaveBeenCalled());
    const checkbox = await screen.findByLabelText("List in directory");
    fireEvent.click(checkbox);

    const nameInput = await screen.findByPlaceholderText("Your display name");
    fireEvent.change(nameInput, { target: { value: "Ms. Rivera" } });
    fireEvent.click(screen.getByText("Set your display name"));

    await waitFor(() =>
      expect(api.updateInstructorDisplayName).toHaveBeenCalledWith("Ms. Rivera"),
    );
    await waitFor(() =>
      expect(api.updateRosterListing).toHaveBeenLastCalledWith(
        OPEN_ROSTER.roster_id,
        "open",
        true,
      ),
    );
    await waitFor(() => expect(checkbox).toBeChecked());
    expect(screen.queryByPlaceholderText("Your display name")).not.toBeInTheDocument();
  });
});

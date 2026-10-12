// Unit test: LearnerAssignments (spec 011 US2 origin) -- renders the
// list/status/badges and delegates "Start"/"Resume" to the dedicated
// `/assignment` page via `onOpenAssignment` (the quiz-taking flow
// itself moved to `tests/unit/assignment-flow.test.tsx`).

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LearnerAssignments from "@/components/LearnerAssignments";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    listLearnerAssignments: vi.fn(),
  };
});

const LEARNER_ID = "learner-1";

describe("LearnerAssignments", () => {
  let onOpenAssignment: (assignmentId: string) => void;

  beforeEach(() => {
    vi.mocked(api.listLearnerAssignments).mockReset();
    onOpenAssignment = vi.fn<(assignmentId: string) => void>();
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
          quiz_session_id: null,
        },
        {
          assignment_id: "a-in-progress",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "in_progress",
          has_unviewed_activity: false,
          quiz_session_id: null,
        },
        {
          assignment_id: "a-completed",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: "2026-08-01T00:00:00Z",
          status: "completed",
          has_unviewed_activity: false,
          quiz_session_id: null,
        },
        {
          assignment_id: "a-cancelled-not-started",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: "2026-08-01T00:00:00Z",
          status: "not_started",
          has_unviewed_activity: false,
          quiz_session_id: null,
        },
      ],
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} onOpenAssignment={onOpenAssignment} />);

    await waitFor(() => expect(api.listLearnerAssignments).toHaveBeenCalledWith(LEARNER_ID, undefined));

    await waitFor(() => expect(screen.getAllByText("Not started")).toHaveLength(2));
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getAllByText("Completed")).toHaveLength(1);

    expect(screen.getByTestId("learner-assignment-cancelled-a-completed")).toBeInTheDocument();
    expect(
      screen.getByTestId("learner-assignment-cancelled-a-cancelled-not-started"),
    ).toBeInTheDocument();

    // Only the not_started, not-cancelled assignment gets a Start button
    // (the in_progress one here has no quiz_session_id, so it's not
    // resumable either -- a stuck-without-a-session edge case).
    expect(screen.getAllByText("Start")).toHaveLength(1);
    expect(
      screen.getByTestId("learner-assignment-a-not-started").querySelector("button"),
    ).toHaveTextContent("Start");
  });

  it("calls onOpenAssignment with the assignment id when Start is clicked", async () => {
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
          quiz_session_id: null,
        },
      ],
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} onOpenAssignment={onOpenAssignment} />);
    fireEvent.click(await screen.findByText("Start"));

    expect(onOpenAssignment).toHaveBeenCalledWith("a1");
  });

  it("shows a Resume button (not Start) for a stuck in_progress assignment, calling onOpenAssignment the same way", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValue({
      assignments: [
        {
          assignment_id: "a-stuck",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "in_progress",
          has_unviewed_activity: false,
          quiz_session_id: "quiz-stuck",
        },
      ],
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} onOpenAssignment={onOpenAssignment} />);
    expect(screen.queryByText("Start")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByText("Resume"));

    expect(onOpenAssignment).toHaveBeenCalledWith("a-stuck");
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
          quiz_session_id: null,
        },
        {
          assignment_id: "a-viewed",
          topic_ids: ["integers-and-operations"],
          question_count: 5,
          due_at: null,
          cancelled_at: null,
          status: "completed",
          has_unviewed_activity: false,
          quiz_session_id: null,
        },
      ],
    });

    render(<LearnerAssignments learnerId={LEARNER_ID} onOpenAssignment={onOpenAssignment} />);

    expect(await screen.findByTestId("learner-assignment-unviewed-a-unviewed")).toBeInTheDocument();
    expect(screen.queryByTestId("learner-assignment-unviewed-a-viewed")).not.toBeInTheDocument();
  });

  it("refetches the list when 'Refresh' is clicked", async () => {
    vi.mocked(api.listLearnerAssignments).mockResolvedValueOnce({ assignments: [] });
    render(<LearnerAssignments learnerId={LEARNER_ID} onOpenAssignment={onOpenAssignment} />);
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
          quiz_session_id: null,
        },
      ],
    });
    fireEvent.click(screen.getByText("Refresh"));

    await waitFor(() => expect(api.listLearnerAssignments).toHaveBeenCalledTimes(2));
    expect(await screen.findByTestId("learner-assignment-a1")).toBeInTheDocument();
  });
});

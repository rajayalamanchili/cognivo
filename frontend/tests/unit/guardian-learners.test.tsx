// Unit test: GuardianAssignQuiz (spec 043 FR-017), T023 -- the guardian
// "assign a quiz" action, shown only on a default-instructor-owned
// enrollment card (`is_default_instructor_roster: true`).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GuardianAssignQuiz from "@/components/GuardianAssignQuiz";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    listLearnerEnrollments: vi.fn(),
    assignQuizToOwnLearner: vi.fn(),
  };
});

describe("GuardianAssignQuiz", () => {
  beforeEach(() => {
    vi.mocked(api.listLearnerEnrollments).mockReset();
    vi.mocked(api.assignQuizToOwnLearner).mockReset();
  });

  it("renders nothing when the roster is not default-instructor-owned", async () => {
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({
      enrollments: [
        { roster_id: "roster-1", subject_id: "algebra-1", is_default_instructor_roster: false, has_starting_grade: false },
      ],
    });

    render(<GuardianAssignQuiz learnerId="learner-1" rosterId="roster-1" />);

    await waitFor(() => expect(api.listLearnerEnrollments).toHaveBeenCalled());
    expect(screen.queryByText("Assign a quiz")).not.toBeInTheDocument();
  });

  it("shows the action and submits an assignment on a default-instructor roster", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({
      enrollments: [
        { roster_id: "roster-1", subject_id: "algebra-1", is_default_instructor_roster: true, has_starting_grade: false },
      ],
    });
    vi.mocked(api.assignQuizToOwnLearner).mockResolvedValue({
      assignment_id: "assignment-1",
      roster_id: "roster-1",
      subject_id: "algebra-1",
      topic_ids: ["integers-and-operations"],
      question_count: 5,
      due_at: null,
      target_learner_ids: ["learner-1"],
    });

    render(<GuardianAssignQuiz learnerId="learner-1" rosterId="roster-1" />);

    const summary = await screen.findByText("Assign a quiz");
    await user.click(summary);
    await user.type(screen.getByTestId("guardian-assign-topic-ids"), "integers-and-operations");
    await user.click(screen.getByRole("button", { name: /assign quiz/i }));

    await waitFor(() => expect(api.assignQuizToOwnLearner).toHaveBeenCalledWith(
      "learner-1",
      "roster-1",
      { topicIds: ["integers-and-operations"], questionCount: 5, dueAt: null },
    ));
    expect(await screen.findByTestId("guardian-assign-quiz-success")).toBeInTheDocument();
  });

  it("shows an error message when the assignment request fails", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({
      enrollments: [
        { roster_id: "roster-1", subject_id: "algebra-1", is_default_instructor_roster: true, has_starting_grade: false },
      ],
    });
    vi.mocked(api.assignQuizToOwnLearner).mockRejectedValue(new Error("not_enrolled"));

    render(<GuardianAssignQuiz learnerId="learner-1" rosterId="roster-1" />);

    const summary = await screen.findByText("Assign a quiz");
    await user.click(summary);
    await user.type(screen.getByTestId("guardian-assign-topic-ids"), "integers-and-operations");
    await user.click(screen.getByRole("button", { name: /assign quiz/i }));

    expect(await screen.findByTestId("guardian-assign-quiz-error")).toHaveTextContent(
      "not_enrolled",
    );
  });
});

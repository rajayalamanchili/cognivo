// Unit test: GuardianLearnerCard's multi-subject tab behavior (spec 044
// FR-002-FR-006, US1). Child components that each own their own fetch
// (LearnerAssignments/GuardianAssignQuiz/GuardianLearnerStandards/
// GuardianLearnerCareerConnections/CareerConnectionsToggle/
// ClassDirectoryBrowse/JoinRosterForm) are stubbed to just surface the
// props they were given -- this test is about the card's own tab-
// switching/chrome logic, not re-testing each child's already-tested
// internals.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GuardianLearnerCard from "@/components/GuardianLearnerCard";
import * as api from "@/services/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getMasteryState: vi.fn(),
    getActivitySummary: vi.fn(),
    getTopicPriorityPreview: vi.fn(),
    listLearnerEnrollments: vi.fn(),
  };
});

vi.mock("@/components/LearnerAssignments", () => ({
  default: ({ rosterId }: { rosterId?: string }) => (
    <div data-testid="stub-assignments">{rosterId}</div>
  ),
}));
vi.mock("@/components/GuardianAssignQuiz", () => ({
  default: ({ rosterId }: { rosterId: string }) => <div data-testid="stub-assign-quiz">{rosterId}</div>,
}));
vi.mock("@/components/GuardianLearnerStandards", () => ({
  default: ({ subjectId }: { subjectId?: string }) => (
    <div data-testid="stub-standards">{subjectId}</div>
  ),
}));
vi.mock("@/components/GuardianLearnerCareerConnections", () => ({
  default: ({ subjectId }: { subjectId?: string }) => (
    <div data-testid="stub-careers">{subjectId}</div>
  ),
}));
vi.mock("@/components/CareerConnectionsToggle", () => ({
  default: () => <div data-testid="stub-career-toggle" />,
}));
vi.mock("@/components/ClassDirectoryBrowse", () => ({
  default: ({ onJoined }: { onJoined?: () => void }) => (
    <button data-testid="stub-join-browse" onClick={() => onJoined?.()}>
      join
    </button>
  ),
}));
vi.mock("@/components/JoinRosterForm", () => ({
  default: () => <div data-testid="stub-join-form" />,
}));

describe("GuardianLearnerCard", () => {
  beforeEach(() => {
    push.mockClear();
    vi.mocked(api.getMasteryState).mockReset().mockResolvedValue({
      topics: [],
      unlocked_grade: null,
      recently_refreshed_topic_id: null,
      standards: [],
    });
    vi.mocked(api.getActivitySummary)
      .mockReset()
      .mockResolvedValue({ questions_this_week: 0, questions_correct_this_week: 0 });
    vi.mocked(api.getTopicPriorityPreview).mockReset().mockResolvedValue({
      subject_id: "algebra-1",
      next_topic: { topic_id: "t1", display_name: "Topic One", band: "unknown", p_mastery: 0.5 },
      upcoming_topics: [],
      is_fallback: false,
      next_topic_prerequisite_display_name: null,
    });
    vi.mocked(api.listLearnerEnrollments).mockReset().mockResolvedValue({ enrollments: [] });
  });

  it("shows the join-a-class state and no tab chrome for zero enrollments", () => {
    render(<GuardianLearnerCard learnerId="learner-1" displayName="Eli" enrollments={[]} />);

    expect(screen.getByText("Not in a class yet")).toBeInTheDocument();
    expect(screen.getByText("Join a class")).toBeInTheDocument();
    expect(screen.queryByRole("tablist", { name: /subjects/i })).not.toBeInTheDocument();
  });

  it("shows no tab-switcher chrome for exactly one enrollment, but still offers Add a subject", async () => {
    render(
      <GuardianLearnerCard
        learnerId="learner-1"
        displayName="Eli"
        enrollments={[{ roster_id: "r1", subject_id: "algebra-1", grade: 7 }]}
      />,
    );

    expect(screen.getByText("Grade 7 · Algebra 1")).toBeInTheDocument();
    expect(screen.queryByRole("tablist", { name: /subjects/i })).not.toBeInTheDocument();
    expect(await screen.findByTestId("stub-standards")).toHaveTextContent("algebra-1");

    fireEvent.click(screen.getByText("Add a subject"));
    expect(await screen.findByTestId("stub-join-browse")).toBeInTheDocument();
  });

  it("renders one tab per enrollment, switching updates every scoped child together", async () => {
    render(
      <GuardianLearnerCard
        learnerId="learner-1"
        displayName="Eli"
        enrollments={[
          { roster_id: "r1", subject_id: "algebra-1", grade: 7 },
          { roster_id: "r2", subject_id: "biology", grade: null },
        ]}
      />,
    );

    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(await screen.findByTestId("stub-standards")).toHaveTextContent("algebra-1");
    expect(screen.getByTestId("stub-careers")).toHaveTextContent("algebra-1");
    expect(screen.getByTestId("stub-assignments")).toHaveTextContent("r1");
    expect(screen.getByTestId("stub-assign-quiz")).toHaveTextContent("r1");

    fireEvent.click(screen.getByText("Biology"));

    await waitFor(() => expect(screen.getByTestId("stub-standards")).toHaveTextContent("biology"));
    expect(screen.getByTestId("stub-careers")).toHaveTextContent("biology");
    expect(screen.getByTestId("stub-assignments")).toHaveTextContent("r2");
    expect(screen.getByTestId("stub-assign-quiz")).toHaveTextContent("r2");
  });

  it("Add a subject is offered alongside the tabs when the learner already has enrollments", () => {
    render(
      <GuardianLearnerCard
        learnerId="learner-1"
        displayName="Eli"
        enrollments={[
          { roster_id: "r1", subject_id: "algebra-1", grade: 7 },
          { roster_id: "r2", subject_id: "biology", grade: null },
        ]}
      />,
    );

    expect(screen.getByText("Add a subject")).toBeInTheDocument();
  });

  it("selects the newly-joined tab once the guardian's refreshed enrollments include it, leaving existing tabs untouched", async () => {
    const { rerender } = render(
      <GuardianLearnerCard
        learnerId="learner-1"
        displayName="Eli"
        enrollments={[{ roster_id: "r1", subject_id: "algebra-1", grade: 7 }]}
      />,
    );
    expect(await screen.findByTestId("stub-standards")).toHaveTextContent("algebra-1");

    rerender(
      <GuardianLearnerCard
        learnerId="learner-1"
        displayName="Eli"
        enrollments={[
          { roster_id: "r1", subject_id: "algebra-1", grade: 7 },
          { roster_id: "r2", subject_id: "biology", grade: null },
        ]}
      />,
    );

    await waitFor(() => expect(screen.getByTestId("stub-standards")).toHaveTextContent("biology"));
    expect(screen.getByRole("tab", { name: /algebra 1/i })).toBeInTheDocument();
  });

  it("spec 044 FR-007/FR-009 (US2): Start practice opens the real session and navigates to Practice's autostart entry for the selected tab's subject", async () => {
    render(
      <GuardianLearnerCard
        learnerId="learner-1"
        displayName="Eli"
        enrollments={[
          { roster_id: "r1", subject_id: "algebra-1", grade: 7 },
          { roster_id: "r2", subject_id: "biology", grade: null },
        ]}
      />,
    );
    await screen.findByTestId("stub-standards");

    fireEvent.click(screen.getByRole("button", { name: /start practice/i }));
    expect(push).toHaveBeenCalledWith("/practice?subject=algebra-1&autostart=1");

    fireEvent.click(screen.getByText("Biology"));
    await waitFor(() => expect(screen.getByTestId("stub-standards")).toHaveTextContent("biology"));
    fireEvent.click(screen.getByRole("button", { name: /start practice/i }));
    expect(push).toHaveBeenCalledWith("/practice?subject=biology&autostart=1");
  });

  it("spec 044 FR-024/FR-025 (US5): Take placement appears only for a graded, not-yet-placed tile and opens Placement directly", async () => {
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({
      enrollments: [
        { roster_id: "r1", subject_id: "algebra-1", is_default_instructor_roster: false, has_starting_grade: false },
        { roster_id: "r2", subject_id: "biology", is_default_instructor_roster: false, has_starting_grade: true },
      ],
    });

    render(
      <GuardianLearnerCard
        learnerId="learner-1"
        displayName="Eli"
        enrollments={[
          { roster_id: "r1", subject_id: "algebra-1", grade: 7 },
          { roster_id: "r2", subject_id: "biology", grade: null },
        ]}
      />,
    );
    await screen.findByTestId("stub-standards");

    expect(await screen.findByRole("button", { name: /take placement/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /take placement/i }));
    expect(push).toHaveBeenCalledWith("/placement?subject=algebra-1");

    fireEvent.click(screen.getByText("Biology"));
    await waitFor(() => expect(screen.getByTestId("stub-standards")).toHaveTextContent("biology"));
    expect(screen.queryByRole("button", { name: /take placement/i })).not.toBeInTheDocument();
  });

  it("spec 044 FR-027 regression: a second learner in the same graded subject with no starting grade can still practice normally (no gating outside tile visibility)", async () => {
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({
      enrollments: [
        { roster_id: "r1", subject_id: "algebra-1", is_default_instructor_roster: false, has_starting_grade: false },
      ],
    });

    render(
      <GuardianLearnerCard
        learnerId="learner-2"
        displayName="Sam"
        enrollments={[{ roster_id: "r1", subject_id: "algebra-1", grade: 7 }]}
      />,
    );
    await screen.findByTestId("stub-standards");

    // "Start practice" is unaffected by has_starting_grade either way.
    expect(screen.getByRole("button", { name: /start practice/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /start practice/i }));
    expect(push).toHaveBeenCalledWith("/practice?subject=algebra-1&autostart=1");
  });
});

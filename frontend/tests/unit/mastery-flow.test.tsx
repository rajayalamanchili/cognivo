// Unit tests: Mastery screen's gap-closing pass (027-learner-ui-
// redesign) against Mastery.dc.html -- the master-detail layout
// (clickable topic list + sticky detail panel defaulting to the first
// assessed topic), the legend, and the status-driven note/CTA. All
// derived from the already-fetched mastery-state/mastery-history
// responses -- no new fetch.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MasteryFlow from "@/app/mastery/mastery-flow";
import * as api from "@/services/api";
import { enterRealLearnerSession } from "@/lib/visitor-state";

const REAL_LEARNER_SESSION_KEY = "cognivo:real-learner-session";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("subject=algebra-1"),
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getDemoLearner: vi.fn(),
    getSubjects: vi.fn(),
    getMasteryState: vi.fn(),
    getMasteryHistory: vi.fn(),
  };
});

function masteryState() {
  return {
    unlocked_grade: null,
    recently_refreshed_topic_id: null,
    topics: [
      {
        topic_id: "integers-and-operations",
        status: "scored" as const,
        p_mastery: 0.92,
        band: "mastered" as const,
        last_updated_at: "2026-01-01T00:00:00Z",
        effective_p_mastery: 0.68,
      },
      {
        topic_id: "solving-multi-step-equations",
        status: "scored" as const,
        p_mastery: 0.48,
        band: "developing" as const,
        last_updated_at: "2026-09-01T00:00:00Z",
        effective_p_mastery: 0.48,
      },
      {
        topic_id: "linear-inequalities",
        status: "unknown" as const,
        p_mastery: null,
        band: null,
        last_updated_at: null,
        effective_p_mastery: null,
      },
    ],
  };
}

beforeEach(() => {
  window.localStorage.removeItem(REAL_LEARNER_SESSION_KEY);
  vi.mocked(api.getDemoLearner).mockResolvedValue({
    learner_id: "learner-1",
    display_name: "Sam",
  } as never);
  vi.mocked(api.getSubjects).mockResolvedValue({
    subjects: [{ subject_id: "algebra-1", display_name: "Algebra I" }],
  });
  vi.mocked(api.getMasteryState).mockResolvedValue(masteryState());
  vi.mocked(api.getMasteryHistory).mockImplementation((_learnerId, _subjectId, topicId) =>
    Promise.resolve({
      points:
        topicId === "integers-and-operations"
          ? [
              { recorded_at: "2026-01-01T00:00:00Z", p_mastery: 0.4 },
              { recorded_at: "2026-06-01T00:00:00Z", p_mastery: 0.7 },
              { recorded_at: "2026-10-01T00:00:00Z", p_mastery: 0.92 },
            ]
          : [],
    })
  );
});

describe("MasteryFlow", () => {
  it("shows the subject eyebrow, heading, and legend", async () => {
    render(<MasteryFlow />);
    expect(await screen.findByText(/ALGEBRA I/)).toBeInTheDocument();
    expect(screen.getByText(/3 TOPICS/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Your mastery" })).toBeInTheDocument();
    expect(screen.getByLabelText("Legend")).toBeInTheDocument();
    expect(screen.getByText(/Mastery line/)).toBeInTheDocument();
  });

  it("defaults the detail panel to the first assessed topic, decayed below the mastery line", async () => {
    render(<MasteryFlow />);
    expect(await screen.findByRole("heading", { name: "Integers And Operations" })).toBeInTheDocument();
    const detail = within(screen.getByRole("complementary"));
    expect(detail.getByText("Refresh due")).toBeInTheDocument();
    expect(detail.getByText("68%")).toBeInTheDocument();
    expect(detail.getByText("92%")).toBeInTheDocument();
    expect(detail.getByRole("link", { name: "Refresh this topic" })).toHaveAttribute(
      "href",
      "/practice?subject=algebra-1"
    );
  });

  it("switches the detail panel when a different topic row is picked", async () => {
    const user = userEvent.setup();
    render(<MasteryFlow />);
    await screen.findByRole("heading", { name: "Integers And Operations" });

    await user.click(screen.getByRole("button", { name: /Solving Multi Step Equations/ }));

    const detail = within(screen.getByRole("complementary"));
    expect(
      await detail.findByRole("heading", { name: "Solving Multi Step Equations" })
    ).toBeInTheDocument();
    expect(detail.getByText("In progress")).toBeInTheDocument();
    expect(detail.getByRole("link", { name: "Continue practicing" })).toBeInTheDocument();
  });

  it("shows the not-started note and CTA for an unassessed topic", async () => {
    const user = userEvent.setup();
    render(<MasteryFlow />);
    await screen.findByRole("heading", { name: "Integers And Operations" });

    await user.click(screen.getByRole("button", { name: /Linear Inequalities/ }));

    const detail = within(screen.getByRole("complementary"));
    expect(
      await detail.findByRole("heading", { name: "Linear Inequalities" })
    ).toBeInTheDocument();
    expect(detail.getByText(/practice to get your first mastery estimate/)).toBeInTheDocument();
    expect(detail.getByRole("link", { name: "Start practicing" })).toBeInTheDocument();
  });

  it("renders a per-row sparkline for a topic with recorded history, and none for one without", async () => {
    render(<MasteryFlow />);
    await screen.findByRole("heading", { name: "Integers And Operations" });

    const withHistory = screen.getByTestId("mastery-topic-integers-and-operations");
    expect(
      await within(withHistory).findByTestId("mastery-trend-line")
    ).toBeInTheDocument();

    const withoutHistory = screen.getByTestId("mastery-topic-solving-multi-step-equations");
    expect(within(withoutHistory).queryByTestId("mastery-trend-line")).not.toBeInTheDocument();
  });

  it("resolves the learner from an active real-learner session instead of the demo learner (spec 041 FR-016)", async () => {
    enterRealLearnerSession("learner-real-1", "Eli");
    render(<MasteryFlow />);

    await screen.findByRole("heading", { name: "Integers And Operations" });
    expect(api.getMasteryState).toHaveBeenCalledWith("learner-real-1", "algebra-1");
  });
});

// Unit test: a failed/rejected recommendations fetch renders a
// distinct "couldn't load" state in the weak-area section while the
// mastery view (US1) still renders correctly (FR-007). T012. Extended
// (T025) with the equivalent case for a failed topic-priority-preview
// fetch, isolated to the path-visualization portion only (FR-008).
// Further extended (T031) to confirm FR-007's and FR-008's failure
// states share one presentation pattern rather than two independently-
// styled variants, and that neither auto-retries within a page load
// (FR-010).

import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardSubjectSection from "@/components/DashboardSubjectSection";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getMasteryState: vi.fn(),
    getRecommendations: vi.fn(),
    getTopicPriorityPreview: vi.fn(),
  };
});

const scoredMasteryState = {
  topics: [
    {
      topic_id: "fractions",
      status: "scored" as const,
      p_mastery: 0.8,
      band: "mastered" as const,
      last_updated_at: "2026-01-01T00:00:00Z",
    },
  ],
};

const confidentRecommendations = {
  subject_id: "algebra-1",
  data_sufficiency: "confident" as const,
  broad_review_needed: false,
  weak_areas: [],
  in_progress_topic_ids: [],
  not_yet_assessed_topic_ids: [],
  insufficient_data_topic_ids: [],
};

const topicPriorityPreview = {
  subject_id: "algebra-1",
  next_topic: {
    topic_id: "fractions",
    display_name: "Fractions",
    band: "mastered" as const,
    p_mastery: 0.8,
  },
  upcoming_topics: [],
  is_fallback: false,
};

describe("DashboardSubjectSection failure isolation", () => {
  beforeEach(() => {
    vi.mocked(api.getMasteryState).mockReset();
    vi.mocked(api.getRecommendations).mockReset();
    vi.mocked(api.getTopicPriorityPreview).mockReset();
  });

  it("renders a distinct couldn't-load state for a failed weak-area fetch while mastery still renders (FR-007)", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(scoredMasteryState);
    vi.mocked(api.getRecommendations).mockRejectedValue(new Error("boom"));
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(topicPriorityPreview);

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    const masteryView = await screen.findByTestId("mastery-view");
    expect(within(masteryView).getByText("Fractions")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByTestId("dashboard-weak-area-slot")).toHaveTextContent(/couldn.t load/i),
    );
    expect(screen.queryByTestId("weak-area-section")).not.toBeInTheDocument();
  });

  it("renders a distinct couldn't-load state for a failed path-visualization fetch while mastery and weak-area still render (FR-008)", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(scoredMasteryState);
    vi.mocked(api.getRecommendations).mockResolvedValue(confidentRecommendations);
    vi.mocked(api.getTopicPriorityPreview).mockRejectedValue(new Error("boom"));

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    expect(await screen.findByTestId("mastery-view")).toBeInTheDocument();
    expect(await screen.findByTestId("weak-area-section")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByTestId("dashboard-path-slot")).toHaveTextContent(/couldn.t load/i),
    );
    expect(screen.queryByTestId("path-visualization")).not.toBeInTheDocument();
  });

  it("renders FR-007's and FR-008's failure states via the same shared presentation pattern (FR-010)", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(scoredMasteryState);
    vi.mocked(api.getRecommendations).mockRejectedValue(new Error("boom"));
    vi.mocked(api.getTopicPriorityPreview).mockRejectedValue(new Error("boom"));

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("dashboard-weak-area-slot")).toHaveTextContent(/couldn.t load/i),
    );
    await waitFor(() =>
      expect(screen.getByTestId("dashboard-path-slot")).toHaveTextContent(/couldn.t load/i),
    );

    const weakAreaFailure = screen
      .getByTestId("dashboard-weak-area-slot")
      .querySelector("p")!;
    const pathFailure = screen.getByTestId("dashboard-path-slot").querySelector("p")!;

    // Not two independently-styled "couldn't load" variants -- the
    // same element shape and styling, just a different subject.
    expect(weakAreaFailure.tagName).toBe(pathFailure.tagName);
    expect(weakAreaFailure.className).toBe(pathFailure.className);
  });

  it("does not auto-retry a failed fetch within a single page load (FR-010)", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(scoredMasteryState);
    vi.mocked(api.getRecommendations).mockRejectedValue(new Error("boom"));
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(topicPriorityPreview);

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("dashboard-weak-area-slot")).toHaveTextContent(/couldn.t load/i),
    );
    expect(api.getRecommendations).toHaveBeenCalledTimes(1);

    // No in-page manual or automatic retry mechanism -- the only way to
    // get a fresh attempt is a full reload (FR-002/FR-006), which a
    // still-mounted component never triggers on its own.
    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(api.getRecommendations).toHaveBeenCalledTimes(1);
  });
});

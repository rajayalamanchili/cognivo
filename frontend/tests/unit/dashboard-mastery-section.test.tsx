// Unit test: DashboardSubjectSection fetches its subject's mastery
// state and renders it via the reused MasteryView component (FR-001),
// including "not yet assessed" for untouched topics. T008.

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardSubjectSection from "@/components/DashboardSubjectSection";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getMasteryState: vi.fn(),
  };
});

describe("DashboardSubjectSection mastery", () => {
  beforeEach(() => {
    vi.mocked(api.getMasteryState).mockReset();
  });

  it("fetches the subject's mastery state and renders it via MasteryView", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue({
      topics: [
        {
          topic_id: "fractions",
          status: "scored",
          p_mastery: 0.8,
          band: "mastered",
          last_updated_at: "2026-01-01T00:00:00Z",
        },
        {
          topic_id: "geometry",
          status: "unknown",
          p_mastery: null,
          band: null,
          last_updated_at: null,
        },
      ],
    });

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    await waitFor(() =>
      expect(api.getMasteryState).toHaveBeenCalledWith("learner-1", "algebra-1"),
    );

    expect(await screen.findByTestId("mastery-view")).toBeInTheDocument();
    expect(screen.getByText("Fractions")).toBeInTheDocument();
    expect(screen.getByText("Mastered")).toBeInTheDocument();
    expect(screen.getByText("Geometry")).toBeInTheDocument();
    expect(screen.getByText("Not yet assessed")).toBeInTheDocument();
  });

  it("fetches mastery state fresh on every mount, never from a cache (FR-006)", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue({ topics: [] });

    const { unmount } = render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );
    await waitFor(() => expect(api.getMasteryState).toHaveBeenCalledTimes(1));
    unmount();

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );
    await waitFor(() => expect(api.getMasteryState).toHaveBeenCalledTimes(2));
  });
});

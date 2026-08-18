// Unit test: a failed/rejected recommendations fetch renders a
// distinct "couldn't load" state in the weak-area section while the
// mastery view (US1) still renders correctly (FR-007). T012.

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardSubjectSection from "@/components/DashboardSubjectSection";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getMasteryState: vi.fn(),
    getRecommendations: vi.fn(),
  };
});

describe("DashboardSubjectSection failure isolation", () => {
  beforeEach(() => {
    vi.mocked(api.getMasteryState).mockReset();
    vi.mocked(api.getRecommendations).mockReset();
  });

  it("renders a distinct couldn't-load state for a failed weak-area fetch while mastery still renders (FR-007)", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue({
      topics: [
        {
          topic_id: "fractions",
          status: "scored",
          p_mastery: 0.8,
          band: "mastered",
          last_updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    vi.mocked(api.getRecommendations).mockRejectedValue(new Error("boom"));

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    expect(await screen.findByTestId("mastery-view")).toBeInTheDocument();
    expect(screen.getByText("Fractions")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByTestId("dashboard-weak-area-slot")).toHaveTextContent(/couldn.t load/i),
    );
    expect(screen.queryByTestId("weak-area-section")).not.toBeInTheDocument();
  });
});

// Unit tests: MasteryTrend sparkline (spec 025 User Story 5, FR-012).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MasteryTrend from "@/components/MasteryTrend";
import type { MasteryHistoryPoint } from "@/services/api";

function point(recordedAt: string, pMastery: number): MasteryHistoryPoint {
  return { recorded_at: recordedAt, p_mastery: pMastery };
}

describe("MasteryTrend", () => {
  it("renders a trend line for multiple points", () => {
    render(
      <MasteryTrend
        points={[
          point("2026-01-01T00:00:00Z", 0.3),
          point("2026-02-01T00:00:00Z", 0.5),
          point("2026-03-01T00:00:00Z", 0.8),
        ]}
      />
    );
    expect(screen.getByTestId("mastery-trend")).toBeInTheDocument();
    expect(screen.getByTestId("mastery-trend-line")).toBeInTheDocument();
  });

  it("degrades gracefully for a single data point, without implying a trend", () => {
    render(<MasteryTrend points={[point("2026-01-01T00:00:00Z", 0.5)]} />);
    expect(screen.getByTestId("mastery-trend")).toBeInTheDocument();
    expect(screen.queryByTestId("mastery-trend-line")).not.toBeInTheDocument();
  });

  it("renders nothing for zero points (unknown topic)", () => {
    render(<MasteryTrend points={[]} />);
    expect(screen.queryByTestId("mastery-trend")).not.toBeInTheDocument();
  });

  it("renders a row-sized sparkline for the per-topic list view", () => {
    render(
      <MasteryTrend
        points={[point("2026-01-01T00:00:00Z", 0.3), point("2026-02-01T00:00:00Z", 0.8)]}
        size="row"
      />
    );
    expect(screen.getByTestId("mastery-trend-line")).toBeInTheDocument();
  });

  it("renders nothing (not the sm fallback text) for a single point at row size", () => {
    render(<MasteryTrend points={[point("2026-01-01T00:00:00Z", 0.5)]} size="row" />);
    expect(screen.queryByTestId("mastery-trend")).not.toBeInTheDocument();
  });
});

// Unit test: WeakAreaSection renders weak_areas/next_step and
// data_sufficiency/broad_review_needed framing verbatim, never
// paraphrased (FR-002). T011.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import WeakAreaSection from "@/components/WeakAreaSection";
import type { RecommendationsResponse } from "@/services/api";

const baseResponse: RecommendationsResponse = {
  subject_id: "algebra-1",
  data_sufficiency: "confident",
  broad_review_needed: false,
  weak_areas: [
    {
      topic_id: "linear-equations",
      display_name: "Linear Equations",
      p_mastery: 0.23,
      evidence: [],
      next_step: {
        recommended_topic_id: "order-of-operations",
        recommended_display_name: "Order of Operations",
        reason: "prerequisite_gap",
        prerequisite_chain: ["linear-equations", "order-of-operations"],
      },
    },
  ],
  in_progress_topic_ids: [],
  not_yet_assessed_topic_ids: [],
  insufficient_data_topic_ids: [],
};

describe("WeakAreaSection", () => {
  it("renders flagged weak areas and their next-step suggestions verbatim", () => {
    render(<WeakAreaSection recommendations={baseResponse} />);
    expect(screen.getByText("Linear Equations")).toBeInTheDocument();
    expect(screen.getByText(/23%/)).toBeInTheDocument();
    expect(screen.getByText("Order of Operations")).toBeInTheDocument();
  });

  it("renders the insufficient-data framing, not paraphrased into false confidence", () => {
    render(
      <WeakAreaSection
        recommendations={{ ...baseResponse, data_sufficiency: "insufficient_data", weak_areas: [] }}
      />,
    );
    expect(screen.getByTestId("data-sufficiency-framing")).toHaveTextContent(/not enough data/i);
    expect(screen.queryByText("Linear Equations")).not.toBeInTheDocument();
  });

  it("renders the broad-review-needed framing verbatim when the agent flags it", () => {
    render(<WeakAreaSection recommendations={{ ...baseResponse, broad_review_needed: true }} />);
    expect(screen.getByTestId("broad-review-framing")).toHaveTextContent(/broad review/i);
  });

  it("does not show the broad-review framing when the agent has not flagged it", () => {
    render(<WeakAreaSection recommendations={baseResponse} />);
    expect(screen.queryByTestId("broad-review-framing")).not.toBeInTheDocument();
  });
});

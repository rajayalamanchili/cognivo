// Unit tests: WeakAreaSummary, a learner-facing softened rendering of
// the existing Recommendation Agent report (spec 025 User Story 6,
// FR-013/FR-014). Distinct from the instructor-facing WeakAreaSection
// (weak-area-section.test.tsx) -- same data, gentler presentation.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import WeakAreaSummary from "@/components/WeakAreaSummary";
import type { RecommendationsResponse } from "@/services/api";

const baseResponse: RecommendationsResponse = {
  subject_id: "algebra-1",
  data_sufficiency: "confident",
  broad_review_needed: false,
  weak_areas: [
    {
      topic_id: "linear-equations",
      display_name: "Linear Equations",
      p_mastery: 0.35,
      evidence: [],
      next_step: {
        recommended_topic_id: "linear-equations",
        recommended_display_name: "Linear Equations",
        reason: "direct_practice",
        prerequisite_chain: [],
      },
      misconception: null,
    },
  ],
  in_progress_topic_ids: [],
  not_yet_assessed_topic_ids: [],
  insufficient_data_topic_ids: [],
};

describe("WeakAreaSummary", () => {
  it("lists exactly the weak areas from the report, matching its content", () => {
    render(<WeakAreaSummary recommendations={baseResponse} />);
    expect(screen.getByTestId("weak-area-summary")).toHaveTextContent("Linear Equations");
  });

  it("shows an encouraging state when no weak areas are flagged", () => {
    render(<WeakAreaSummary recommendations={{ ...baseResponse, weak_areas: [] }} />);
    const el = screen.getByTestId("weak-area-summary");
    expect(el.textContent).not.toBe("");
    // Encouraging, not alarming or a bare error/empty-state message.
    expect(el.textContent?.toLowerCase()).toMatch(/great|nice|solid|keep up/);
    expect(el.textContent?.toLowerCase()).not.toMatch(/^error$|^empty$/);
  });

  it("does not independently recompute weak areas -- renders only what the report contains", () => {
    const twoFlags: RecommendationsResponse = {
      ...baseResponse,
      weak_areas: [
        baseResponse.weak_areas[0],
        {
          ...baseResponse.weak_areas[0],
          topic_id: "quadratics",
          display_name: "Quadratics",
        },
      ],
    };
    render(<WeakAreaSummary recommendations={twoFlags} />);
    expect(screen.getByTestId("weak-area-summary")).toHaveTextContent("Linear Equations");
    expect(screen.getByTestId("weak-area-summary")).toHaveTextContent("Quadratics");
    expect(screen.getAllByTestId(/weak-area-summary-item-/)).toHaveLength(2);
  });
});

// Unit tests: CareerConnectionsList (spec 039 FR-003/FR-007).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CareerConnectionsList from "@/components/CareerConnectionsList";
import type { CareerConnectionEntry } from "@/services/api";

function entry(overrides: Partial<CareerConnectionEntry> = {}): CareerConnectionEntry {
  return {
    topic_id: "topic-a",
    career: "Civil Engineer",
    description: "Civil engineers use the same equations to calculate load limits on bridges.",
    ...overrides,
  };
}

describe("CareerConnectionsList", () => {
  it("renders a matched entry's career and description", () => {
    render(<CareerConnectionsList careerConnections={[entry()]} />);
    const list = screen.getByTestId("career-connections-list");
    expect(list.textContent).toMatch(/Civil Engineer/);
    expect(list.textContent).toMatch(/load limits/);
  });

  it("renders nothing when careerConnections is empty (FR-006/FR-007)", () => {
    render(<CareerConnectionsList careerConnections={[]} />);
    expect(screen.queryByTestId("career-connections-list")).not.toBeInTheDocument();
  });

  it("renders one item per entry when there are several", () => {
    render(
      <CareerConnectionsList
        careerConnections={[entry(), entry({ topic_id: "topic-b", career: "Biologist" })]}
      />,
    );
    expect(screen.getByTestId("career-connections-list").children).toHaveLength(2);
  });
});

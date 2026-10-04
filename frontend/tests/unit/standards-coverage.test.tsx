// Unit tests: StandardsCoverage (spec 038 FR-004/FR-006/FR-011/FR-013).

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import StandardsCoverage from "@/components/StandardsCoverage";
import type { StandardCoverageEntry } from "@/services/api";

function entry(overrides: Partial<StandardCoverageEntry> = {}): StandardCoverageEntry {
  return {
    framework: "Common Core Math",
    code: "CCSS.MATH.CONTENT.6.NS.C.5",
    title: "Understand that positive and negative numbers represent opposite quantities.",
    topic_ids: ["topic-a"],
    status: "met",
    ...overrides,
  };
}

describe("StandardsCoverage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders a met standard's code and a visible 'Met' text label", () => {
    render(<StandardsCoverage standards={[entry({ status: "met" })]} />);
    const row = screen.getByTestId("standards-coverage");
    expect(row.textContent).toMatch(/CCSS\.MATH\.CONTENT\.6\.NS\.C\.5/);
    expect(row.textContent).toMatch(/Met/);
  });

  it("renders a visible 'In progress' text label, never color alone (FR-011)", () => {
    render(<StandardsCoverage standards={[entry({ status: "in_progress" })]} />);
    expect(screen.getByTestId("standards-coverage").textContent).toMatch(/In progress/i);
  });

  it("renders a visible 'Not yet reached' text label", () => {
    render(<StandardsCoverage standards={[entry({ status: "not_yet_reached" })]} />);
    expect(screen.getByTestId("standards-coverage").textContent).toMatch(/Not yet reached/i);
  });

  it("renders nothing when standards is empty (FR-006, zero-tags case)", () => {
    render(<StandardsCoverage standards={[]} />);
    expect(screen.queryByTestId("standards-coverage")).not.toBeInTheDocument();
  });

  it("renders nothing when disabled via the enabled prop (FR-013)", () => {
    render(<StandardsCoverage standards={[entry()]} enabled={false} />);
    expect(screen.queryByTestId("standards-coverage")).not.toBeInTheDocument();
  });

  it("renders by default when NEXT_PUBLIC_STANDARDS_ALIGNMENT_ENABLED is unset", () => {
    render(<StandardsCoverage standards={[entry()]} />);
    expect(screen.getByTestId("standards-coverage")).toBeInTheDocument();
  });
});

// Unit tests: RefreshedBanner (spec 025 User Story 4, FR-011).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RefreshedBanner from "@/components/RefreshedBanner";

describe("RefreshedBanner", () => {
  it("renders an encouraging acknowledgment when refreshed is true", () => {
    render(<RefreshedBanner refreshed />);
    expect(screen.getByTestId("refreshed-banner")).toBeInTheDocument();
  });

  it("renders nothing when refreshed is false", () => {
    render(<RefreshedBanner refreshed={false} />);
    expect(screen.queryByTestId("refreshed-banner")).not.toBeInTheDocument();
  });
});

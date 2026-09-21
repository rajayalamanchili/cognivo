// Unit test: LoadingIndicator renders the given message in both its
// full-page and compact (inline) forms.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LoadingIndicator from "@/components/LoadingIndicator";

describe("LoadingIndicator", () => {
  it("renders a full-page block with the given message by default", () => {
    render(<LoadingIndicator message="Finding your next question…" />);
    const indicator = screen.getByTestId("loading-indicator");
    expect(indicator.tagName).toBe("DIV");
    expect(indicator).toHaveTextContent("Finding your next question…");
  });

  it("renders inline when compact", () => {
    render(<LoadingIndicator message="Checking your answer…" compact />);
    const indicator = screen.getByTestId("loading-indicator");
    expect(indicator.tagName).toBe("SPAN");
    expect(indicator).toHaveTextContent("Checking your answer…");
  });

  it("defaults to a generic message when none is given", () => {
    render(<LoadingIndicator />);
    expect(screen.getByTestId("loading-indicator")).toHaveTextContent("Loading…");
  });

  it("renders a plain spinning ring for the professional variant, no emoji", () => {
    render(<LoadingIndicator message="Loading rosters…" variant="professional" />);
    const indicator = screen.getByTestId("loading-indicator");
    expect(indicator).toHaveTextContent("Loading rosters…");
    expect(indicator.textContent).not.toMatch(/🚀|⭐/);
  });

  it("renders the professional variant inline when compact", () => {
    render(<LoadingIndicator message="Loading…" variant="professional" compact />);
    expect(screen.getByTestId("loading-indicator").tagName).toBe("SPAN");
  });
});

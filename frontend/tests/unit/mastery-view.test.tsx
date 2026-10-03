// Unit tests: MasteryView's decay-aware rendering (spec 025 User Story 2,
// FR-005/FR-006/FR-007/FR-008).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MasteryView from "@/components/MasteryView";
import type { MasteryTopicEntry } from "@/services/api";

function topic(overrides: Partial<MasteryTopicEntry> = {}): MasteryTopicEntry {
  return {
    topic_id: "integers-and-operations",
    status: "scored",
    p_mastery: 0.8,
    band: "mastered",
    last_updated_at: new Date().toISOString(),
    effective_p_mastery: 0.8,
    ...overrides,
  };
}

const SIX_MONTHS_AGO = new Date(Date.now() - 183 * 86_400_000).toISOString();

describe("MasteryView", () => {
  it("shows peak mastery only (no separate effective figure) when not decayed", () => {
    render(<MasteryView topics={[topic({ p_mastery: 0.8, effective_p_mastery: 0.8 })]} />);
    const row = screen.getByTestId(`mastery-topic-${"integers-and-operations"}`);
    expect(row.textContent).toMatch(/80%/);
  });

  it("shows both peak and effective mastery, with recovery-oriented copy, when decayed", () => {
    render(
      <MasteryView
        topics={[
          topic({
            p_mastery: 0.8,
            effective_p_mastery: 0.5,
            last_updated_at: SIX_MONTHS_AGO,
          }),
        ]}
      />
    );
    const row = screen.getByTestId("mastery-topic-integers-and-operations");
    expect(row.textContent).toMatch(/80%/);
    expect(row.textContent).toMatch(/50%/);
    expect((row.textContent ?? "").toLowerCase()).not.toMatch(/lost|demot/);
    // Recovery framing must be visible rendered text, not a hover-only
    // tooltip (SC-002's "single glance", not discoverable only on hover).
    expect(row.textContent).toMatch(/faded a little|bring it right back/i);
  });

  it("renders a warmer, text-labeled last-practiced indicator for a long-untouched topic than a recent one", () => {
    render(
      <MasteryView
        topics={[
          topic({ topic_id: "a", last_updated_at: new Date().toISOString() }),
          topic({ topic_id: "b", last_updated_at: SIX_MONTHS_AGO, effective_p_mastery: 0.5 }),
        ]}
      />
    );
    const recent = screen.getByTestId("last-practiced-a");
    const old = screen.getByTestId("last-practiced-b");
    // FR-007: text label present regardless of color -- never color-only.
    expect(old.textContent).toMatch(/month/i);
    expect(recent.className).not.toBe(old.className);
  });

  it("renders gracefully for an entry with no decay/timestamp data (e.g. placement's own response shape)", () => {
    render(
      <MasteryView
        topics={[{ topic_id: "integers-and-operations", status: "scored", p_mastery: 0.5, band: "developing" }]}
      />
    );
    expect(screen.getByTestId("mastery-topic-integers-and-operations")).toBeInTheDocument();
    expect(screen.queryByTestId("last-practiced-integers-and-operations")).not.toBeInTheDocument();
  });

  it("renders 'Not yet assessed' for an unknown topic, unchanged from today", () => {
    render(
      <MasteryView
        topics={[{ topic_id: "x", status: "unknown", p_mastery: null, band: null }]}
      />
    );
    expect(screen.getByText("Not yet assessed")).toBeInTheDocument();
  });

  it("still shows the empty status-bar track for a not-yet-assessed topic, just with no fill (mockup parity)", () => {
    render(
      <MasteryView
        topics={[{ topic_id: "x", status: "unknown", p_mastery: null, band: null }]}
      />
    );
    const row = screen.getByTestId("mastery-topic-x");
    expect(row.querySelector('[data-testid="mastery-bar"]')).toBeInTheDocument();
    expect(row.querySelector('[data-testid="mastery-bar-fill"]')).not.toBeInTheDocument();
  });

  it("renders both the track and a colored fill for an assessed topic", () => {
    render(<MasteryView topics={[topic({ p_mastery: 0.8, effective_p_mastery: 0.8 })]} />);
    const row = screen.getByTestId("mastery-topic-integers-and-operations");
    expect(row.querySelector('[data-testid="mastery-bar"]')).toBeInTheDocument();
    expect(row.querySelector('[data-testid="mastery-bar-fill"]')).toBeInTheDocument();
  });
});

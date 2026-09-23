// Unit test: SessionCountdown ticks down from a server-provided
// expires_at and calls onExpire exactly once at zero (spec 022
// FR-002, research.md §1).

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SessionCountdown from "@/components/SessionCountdown";

describe("SessionCountdown", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-23T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the initial time remaining", () => {
    render(<SessionCountdown expiresAt="2026-09-23T12:05:00Z" />);
    expect(screen.getByTestId("session-countdown")).toHaveTextContent("5:00");
  });

  it("ticks down as time passes", () => {
    render(<SessionCountdown expiresAt="2026-09-23T12:00:30Z" />);
    expect(screen.getByTestId("session-countdown")).toHaveTextContent("0:30");

    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(screen.getByTestId("session-countdown")).toHaveTextContent("0:20");
  });

  it("calls onExpire exactly once when it reaches zero", () => {
    const onExpire = vi.fn();
    render(<SessionCountdown expiresAt="2026-09-23T12:00:03Z" onExpire={onExpire} />);

    act(() => {
      vi.advanceTimersByTime(5_000);
    });
    expect(screen.getByTestId("session-countdown")).toHaveTextContent("0:00");
    expect(onExpire).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(5_000);
    });
    expect(onExpire).toHaveBeenCalledTimes(1);
  });
});

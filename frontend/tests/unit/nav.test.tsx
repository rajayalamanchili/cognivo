// Unit test: Nav's per-visitor-type menu (anonymous/demo-learner/
// guardian/instructor buckets) and the always-visible Personalization
// Evidence link (SC-005, no login required).

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Nav from "@/components/Nav";
import * as api from "@/services/api";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getWhoAmI: vi.fn(),
    logout: vi.fn(),
  };
});

const DEMO_LEARNER_MODE_KEY = "cognivo:demo-learner-mode";

describe("Nav", () => {
  beforeEach(() => {
    push.mockReset();
    vi.mocked(api.getWhoAmI).mockReset();
    vi.mocked(api.logout).mockReset();
    window.localStorage.removeItem(DEMO_LEARNER_MODE_KEY);
  });

  it("shows only Try Demo, Sign In, and Personalization Evidence when logged out", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: null });
    render(<Nav />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(await screen.findByText("Try Demo")).toBeInTheDocument();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
    expect(screen.getByText("Personalization Evidence")).toBeInTheDocument();

    expect(screen.queryByText("My Learners")).not.toBeInTheDocument();
    expect(screen.queryByText("Rosters")).not.toBeInTheDocument();
    expect(screen.queryByText("Placement")).not.toBeInTheDocument();
  });

  it("shows the demo-learner bucket when demo-learner mode is set, with no real session", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: null });
    window.localStorage.setItem(DEMO_LEARNER_MODE_KEY, "true");
    render(<Nav />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(await screen.findByText("Placement")).toBeInTheDocument();
    expect(screen.getByText("Practice")).toBeInTheDocument();
    expect(screen.getByText("Mastery")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Exit Demo")).toBeInTheDocument();
    expect(screen.getByText("Personalization Evidence")).toBeInTheDocument();

    expect(screen.queryByText("Try Demo")).not.toBeInTheDocument();
  });

  it("exiting demo mode clears the flag and navigates home", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: null });
    window.localStorage.setItem(DEMO_LEARNER_MODE_KEY, "true");
    render(<Nav />);

    fireEvent.click(await screen.findByText("Exit Demo"));

    expect(window.localStorage.getItem(DEMO_LEARNER_MODE_KEY)).toBeNull();
    expect(push).toHaveBeenCalledWith("/");
  });

  it("shows the guardian bucket for a guardian session", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: "guardian" });
    render(<Nav />);

    expect(await screen.findByText("My Learners")).toBeInTheDocument();
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
    expect(screen.queryByText("Try Demo")).not.toBeInTheDocument();
    expect(screen.queryByText("Rosters")).not.toBeInTheDocument();
  });

  it("shows the instructor bucket for both real and demo instructor sessions", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: "demo_instructor" });
    render(<Nav />);

    expect(await screen.findByText("Rosters")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
  });

  it("signing out logs out and navigates home", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: "guardian" });
    vi.mocked(api.logout).mockResolvedValue(undefined);
    render(<Nav />);

    fireEvent.click(await screen.findByText("Sign Out"));

    await waitFor(() => expect(api.logout).toHaveBeenCalled());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });
});

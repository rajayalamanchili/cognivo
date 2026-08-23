// Unit test: DemoBadge shows only while the visitor is actually in
// demo territory -- a demo_instructor session, or one of the demo
// learner's own pages -- never on the bare landing page or for a real
// guardian/instructor session.

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DemoBadge from "@/components/DemoBadge";
import * as api from "@/services/api";

let mockPathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getWhoAmI: vi.fn(),
  };
});

describe("DemoBadge", () => {
  beforeEach(() => {
    mockPathname = "/";
    vi.mocked(api.getWhoAmI).mockReset();
  });

  it("is hidden on the bare landing page with no session", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: null, identifier: null });
    render(<DemoBadge />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(screen.queryByTestId("demo-badge")).not.toBeInTheDocument();
  });

  it.each(["/demo", "/placement", "/practice", "/mastery", "/dashboard", "/quiz"])(
    "is shown on %s regardless of session",
    async (pathname) => {
      mockPathname = pathname;
      vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: null, identifier: null });
      render(<DemoBadge />);

      expect(await screen.findByTestId("demo-badge")).toBeInTheDocument();
    },
  );

  it("is shown for a demo_instructor session even on an unrelated path", async () => {
    mockPathname = "/instructor/rosters";
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "demo_instructor",
      identifier: "Demo Instructor",
    });
    render(<DemoBadge />);

    expect(await screen.findByTestId("demo-badge")).toBeInTheDocument();
  });

  it("is hidden for a real guardian session on a non-demo path", async () => {
    mockPathname = "/guardian/learners";
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
    });
    render(<DemoBadge />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(screen.queryByTestId("demo-badge")).not.toBeInTheDocument();
  });

  it("is hidden for a real instructor session on a non-demo path", async () => {
    mockPathname = "/instructor/rosters";
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "instructor",
      identifier: "teacher@example.com",
    });
    render(<DemoBadge />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(screen.queryByTestId("demo-badge")).not.toBeInTheDocument();
  });
});

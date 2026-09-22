// Unit test: Nav's pre-deletion warning banner (spec 020 FR-011) --
// renders when whoami's pending_deletion_warnings is non-empty, and
// renders nothing extra in the common (empty-list) case.

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Nav from "@/components/Nav";
import * as api from "@/services/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getWhoAmI: vi.fn(),
    logout: vi.fn(),
  };
});

describe("Nav deletion warning banner", () => {
  beforeEach(() => {
    vi.mocked(api.getWhoAmI).mockReset();
  });

  it("renders a warning banner naming the scheduled deletion date when a warning is pending", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [
        {
          target_type: "learner",
          target_id: "5b1e0000-0000-0000-0000-0000000000e9",
          warned_at: "2026-09-14T06:00:00Z",
          scheduled_deletion_date: "2026-09-21",
        },
      ],
    });
    render(<Nav />);

    const banner = await screen.findByTestId("deletion-warning-banner");
    expect(banner).toHaveTextContent("2026-09-21");
  });

  it("renders no banner when pending_deletion_warnings is empty (the common case)", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    render(<Nav />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(screen.queryByTestId("deletion-warning-banner")).not.toBeInTheDocument();
  });

  it("renders no banner for a logged-out session with no warnings field at all", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({ account_type: null, identifier: null });
    render(<Nav />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(screen.queryByTestId("deletion-warning-banner")).not.toBeInTheDocument();
  });
});

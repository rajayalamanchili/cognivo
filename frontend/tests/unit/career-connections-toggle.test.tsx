// Unit tests: CareerConnectionsToggle (spec 039 FR-004).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CareerConnectionsToggle from "@/components/CareerConnectionsToggle";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getCareerConnectionsPreference: vi.fn(),
    setCareerConnectionsPreference: vi.fn(),
  };
});

describe("CareerConnectionsToggle", () => {
  beforeEach(() => {
    vi.mocked(api.getCareerConnectionsPreference).mockReset();
    vi.mocked(api.setCareerConnectionsPreference).mockReset();
  });

  it("renders the fetched state", async () => {
    vi.mocked(api.getCareerConnectionsPreference).mockResolvedValue({ enabled: true });
    render(<CareerConnectionsToggle learnerId="learner-1" />);

    const checkbox = await screen.findByTestId("career-connections-toggle");
    expect(checkbox.querySelector("input")).toBeChecked();
  });

  it("calls PATCH with the new value on change and reflects the server's response", async () => {
    vi.mocked(api.getCareerConnectionsPreference).mockResolvedValue({ enabled: true });
    vi.mocked(api.setCareerConnectionsPreference).mockResolvedValue({ enabled: false });
    const user = userEvent.setup();
    render(<CareerConnectionsToggle learnerId="learner-1" />);

    const checkbox = await screen.findByTestId("career-connections-toggle");
    await user.click(checkbox.querySelector("input")!);

    expect(api.setCareerConnectionsPreference).toHaveBeenCalledWith("learner-1", false);
    await waitFor(() => expect(checkbox.querySelector("input")).not.toBeChecked());
  });

  it("reflects the server's response even if it differs from the requested value", async () => {
    vi.mocked(api.getCareerConnectionsPreference).mockResolvedValue({ enabled: true });
    // Server disagrees with the optimistic request -- the component must
    // show what was actually saved, not what was clicked.
    vi.mocked(api.setCareerConnectionsPreference).mockResolvedValue({ enabled: true });
    const user = userEvent.setup();
    render(<CareerConnectionsToggle learnerId="learner-1" />);

    const checkbox = await screen.findByTestId("career-connections-toggle");
    await user.click(checkbox.querySelector("input")!);

    await waitFor(() => expect(checkbox.querySelector("input")).toBeChecked());
  });
});

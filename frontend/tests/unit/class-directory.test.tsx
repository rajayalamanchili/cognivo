// Unit test: ClassDirectoryBrowse's browse/join flow and the
// empty-state (not error) rendering (spec 041 FR-019/FR-020, T043).

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ClassDirectoryBrowse from "@/components/ClassDirectoryBrowse";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getRosterDirectory: vi.fn(),
    joinRoster: vi.fn(),
  };
});

const ENTRY = {
  roster_id: "roster-1",
  subject_id: "algebra-1",
  grade: 7,
  instructor_display_name: "Ms. Rivera",
  join_code: "ALG-1234",
};

beforeEach(() => {
  vi.mocked(api.getRosterDirectory).mockReset();
  vi.mocked(api.joinRoster).mockReset();
});

describe("ClassDirectoryBrowse", () => {
  it("renders an empty state, not an error, when the directory has no listed rosters", async () => {
    vi.mocked(api.getRosterDirectory).mockResolvedValue({ rosters: [] });
    render(<ClassDirectoryBrowse learnerId="learner-1" />);

    expect(await screen.findByTestId("class-directory-empty")).toBeInTheDocument();
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
  });

  it("lists each entry with subject, grade, and instructor name", async () => {
    vi.mocked(api.getRosterDirectory).mockResolvedValue({ rosters: [ENTRY] });
    render(<ClassDirectoryBrowse learnerId="learner-1" />);

    const item = await screen.findByText(/Ms\. Rivera/);
    expect(item.textContent).toMatch(/Algebra 1/);
    expect(item.textContent).toMatch(/Grade 7/);
  });

  it("joining calls the existing joinRoster with the entry's own join_code and shows the enrolled outcome", async () => {
    vi.mocked(api.getRosterDirectory).mockResolvedValue({ rosters: [ENTRY] });
    vi.mocked(api.joinRoster).mockResolvedValue({ status: "enrolled", enrollment_id: "enr-1" });
    render(<ClassDirectoryBrowse learnerId="learner-1" />);

    fireEvent.click(await screen.findByText("Join"));

    await waitFor(() =>
      expect(api.joinRoster).toHaveBeenCalledWith("learner-1", ENTRY.join_code),
    );
    expect(await screen.findByText("Joined")).toBeInTheDocument();
  });

  it("renders the pending outcome when joinRoster reports a pending request", async () => {
    vi.mocked(api.getRosterDirectory).mockResolvedValue({ rosters: [ENTRY] });
    vi.mocked(api.joinRoster).mockResolvedValue({
      status: "pending",
      enrollment_request_id: "req-1",
    });
    render(<ClassDirectoryBrowse learnerId="learner-1" />);

    fireEvent.click(await screen.findByText("Join"));

    expect(await screen.findByText("Request sent")).toBeInTheDocument();
  });
});

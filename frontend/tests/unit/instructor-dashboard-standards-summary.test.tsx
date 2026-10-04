// Unit test: InstructorDashboardFlow renders the roster-wide standards
// summary when present, and renders nothing for it when absent/empty
// (spec 038 FR-005/FR-006, User Story 2, US2 Acceptance Scenario 2).

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InstructorDashboardFlow from "@/app/instructor/dashboard/instructor-dashboard-flow";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    listRosters: vi.fn(),
    getRosterDashboard: vi.fn(),
  };
});

const ROSTER = { roster_id: "r1", subject_id: "algebra-1", enrollment_mode: "open" as const };

describe("InstructorDashboardFlow standards summary", () => {
  beforeEach(() => {
    vi.mocked(api.listRosters).mockReset();
    vi.mocked(api.getRosterDashboard).mockReset();
    vi.mocked(api.listRosters).mockResolvedValue({ rosters: [ROSTER] });
  });

  it("renders the roster-wide standards summary when present", async () => {
    vi.mocked(api.getRosterDashboard).mockResolvedValue({
      roster_id: "r1",
      subject_id: "algebra-1",
      learners: [],
      standards_summary: [
        {
          framework: "Common Core Math",
          code: "CCSS.MATH.CONTENT.6.NS.C.5",
          title: "Understand opposite quantities.",
          met_count: 2,
          total_count: 5,
        },
      ],
    });

    render(<InstructorDashboardFlow />);

    await waitFor(() => {
      expect(screen.getByTestId("roster-standards-summary")).toBeInTheDocument();
    });
    expect(screen.getByTestId("roster-standards-summary").textContent).toMatch(/2\/5 learners/);
  });

  it("renders no standards-summary section when it is empty (US2 Acceptance Scenario 2)", async () => {
    vi.mocked(api.getRosterDashboard).mockResolvedValue({
      roster_id: "r1",
      subject_id: "algebra-1",
      learners: [],
      standards_summary: [],
    });

    render(<InstructorDashboardFlow />);

    await waitFor(() => expect(api.getRosterDashboard).toHaveBeenCalled());
    expect(screen.queryByTestId("roster-standards-summary")).not.toBeInTheDocument();
  });
});

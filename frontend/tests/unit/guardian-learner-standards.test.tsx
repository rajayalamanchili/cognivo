// Unit test: GuardianLearnerStandards fetches the learner's enrolled
// subject(s), then each subject's mastery-state, and renders
// StandardsCoverage per subject (spec 038 FR-004, research.md Decision 4
// / T014 correction).

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GuardianLearnerStandards from "@/components/GuardianLearnerStandards";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    listLearnerEnrollments: vi.fn(),
    getMasteryState: vi.fn(),
  };
});

describe("GuardianLearnerStandards", () => {
  beforeEach(() => {
    vi.mocked(api.listLearnerEnrollments).mockReset();
    vi.mocked(api.getMasteryState).mockReset();
  });

  it("fetches enrollments then renders each subject's standards coverage", async () => {
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({
      enrollments: [{ roster_id: "r1", subject_id: "algebra-1" }],
    });
    vi.mocked(api.getMasteryState).mockResolvedValue({
      topics: [],
      unlocked_grade: null,
      recently_refreshed_topic_id: null,
      standards: [
        {
          framework: "Common Core Math",
          code: "CCSS.MATH.CONTENT.6.NS.C.5",
          title: "Understand opposite quantities.",
          topic_ids: ["topic-a"],
          status: "met",
        },
      ],
    });

    render(<GuardianLearnerStandards learnerId="learner-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("standards-coverage")).toBeInTheDocument();
    });
    expect(api.getMasteryState).toHaveBeenCalledWith("learner-1", "algebra-1");
  });

  it("renders nothing for a learner with no enrollments", async () => {
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({ enrollments: [] });

    render(<GuardianLearnerStandards learnerId="learner-2" />);

    await waitFor(() => expect(api.listLearnerEnrollments).toHaveBeenCalled());
    expect(screen.queryByTestId("standards-coverage")).not.toBeInTheDocument();
    expect(api.getMasteryState).not.toHaveBeenCalled();
  });

  it("fails silently when the enrollments fetch errors", async () => {
    vi.mocked(api.listLearnerEnrollments).mockRejectedValue(new Error("network error"));

    render(<GuardianLearnerStandards learnerId="learner-3" />);

    await waitFor(() => expect(api.listLearnerEnrollments).toHaveBeenCalled());
    expect(screen.queryByTestId("standards-coverage")).not.toBeInTheDocument();
  });
});

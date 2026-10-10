// Unit test: GuardianLearnerCareerConnections fetches the learner's
// enrolled subject(s), then each subject's mastery-state, and renders
// its career connections (spec 039 FR-003, sibling to
// GuardianLearnerStandards.tsx). No test file existed for this
// component before spec 044's subjectId filter addition (FR-002).

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GuardianLearnerCareerConnections from "@/components/GuardianLearnerCareerConnections";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    listLearnerEnrollments: vi.fn(),
    getMasteryState: vi.fn(),
  };
});

describe("GuardianLearnerCareerConnections", () => {
  beforeEach(() => {
    vi.mocked(api.listLearnerEnrollments).mockReset();
    vi.mocked(api.getMasteryState).mockReset();
  });

  it("fetches enrollments then renders every subject's career connections combined", async () => {
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({
      enrollments: [
        { roster_id: "r1", subject_id: "algebra-1", is_default_instructor_roster: false, has_starting_grade: false },
        { roster_id: "r2", subject_id: "biology", is_default_instructor_roster: false, has_starting_grade: false },
      ],
    });
    vi.mocked(api.getMasteryState).mockImplementation((_learnerId, subjectId) =>
      Promise.resolve({
        topics: [],
        unlocked_grade: null,
        recently_refreshed_topic_id: null,
        career_connections: [
          { topic_id: "t1", career: `${subjectId} Career`, description: "Topic" },
        ],
      }),
    );

    render(<GuardianLearnerCareerConnections learnerId="learner-1" />);

    await waitFor(() => expect(screen.getByText("algebra-1 Career")).toBeInTheDocument());
    expect(screen.getByText("biology Career")).toBeInTheDocument();
  });

  it("spec 044 FR-002: scopes to one subject when subjectId is provided", async () => {
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({
      enrollments: [
        { roster_id: "r1", subject_id: "algebra-1", is_default_instructor_roster: false, has_starting_grade: false },
        { roster_id: "r2", subject_id: "biology", is_default_instructor_roster: false, has_starting_grade: false },
      ],
    });
    vi.mocked(api.getMasteryState).mockResolvedValue({
      topics: [],
      unlocked_grade: null,
      recently_refreshed_topic_id: null,
      career_connections: [],
    });

    render(<GuardianLearnerCareerConnections learnerId="learner-2" subjectId="biology" />);

    await waitFor(() => expect(api.getMasteryState).toHaveBeenCalledWith("learner-2", "biology"));
    expect(api.getMasteryState).not.toHaveBeenCalledWith("learner-2", "algebra-1");
  });

  it("renders nothing for a learner with no enrollments", async () => {
    vi.mocked(api.listLearnerEnrollments).mockResolvedValue({ enrollments: [] });

    render(<GuardianLearnerCareerConnections learnerId="learner-3" />);

    await waitFor(() => expect(api.listLearnerEnrollments).toHaveBeenCalled());
    expect(api.getMasteryState).not.toHaveBeenCalled();
  });
});

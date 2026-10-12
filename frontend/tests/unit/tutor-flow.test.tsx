// Unit test: tutor-flow.tsx's subject-aware entry (spec 044 FR-020/
// FR-023, US4) -- a `?subject=` arrival (Dashboard's own link) skips the
// picker and opens chat directly; the plain nav link (no `?subject=`)
// keeps today's picker unchanged.

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TutorFlow from "@/app/tutor/tutor-flow";
import * as api from "@/services/api";

let mockSearchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getDemoLearner: vi.fn(),
    getSubjects: vi.fn(),
    openTutorSession: vi.fn(),
    getTopicPriorityPreview: vi.fn(),
  };
});

beforeEach(() => {
  mockSearchParams = new URLSearchParams();
  vi.mocked(api.getDemoLearner).mockReset().mockResolvedValue({
    learner_id: "learner-1",
    display_name: "Demo Learner",
  });
  vi.mocked(api.getSubjects).mockReset().mockResolvedValue({
    subjects: [
      { subject_id: "algebra-1", display_name: "Algebra I" },
      { subject_id: "physics-1", display_name: "Physics" },
    ],
  });
  vi.mocked(api.openTutorSession).mockReset();
  vi.mocked(api.getTopicPriorityPreview).mockReset().mockResolvedValue({
    subject_id: "algebra-1",
    next_topic: {
      topic_id: "linear-equations",
      display_name: "Linear Equations",
      band: "developing",
      p_mastery: 0.4,
    },
    upcoming_topics: [],
    is_fallback: false,
    next_topic_prerequisite_display_name: null,
  });
});

describe("TutorFlow subject-scoped entry (spec 044 FR-020, US4)", () => {
  it("skips the picker and opens chat directly when arriving with ?subject=", async () => {
    mockSearchParams = new URLSearchParams("subject=physics-1");
    vi.mocked(api.openTutorSession).mockResolvedValue({
      session_id: "session-1",
      subject_id: "physics-1",
      status: "active",
    });

    render(<TutorFlow />);

    expect(await screen.findByTestId("tutor-chat")).toBeInTheDocument();
    expect(screen.queryByTestId("tutor-start-form")).not.toBeInTheDocument();
    expect(api.openTutorSession).toHaveBeenCalledWith("learner-1", "physics-1");
  });

  it("still shows the picker for the plain nav link with no subject (FR-023)", async () => {
    render(<TutorFlow />);

    expect(await screen.findByTestId("tutor-start-form")).toBeInTheDocument();
    expect(api.openTutorSession).not.toHaveBeenCalled();
  });
});

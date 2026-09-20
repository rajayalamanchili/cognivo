// Unit test: PlacementFlow displays each question's grade label when
// present (spec 017 FR-002), and its skip button swaps in a
// replacement or removes the question entirely (FR-006).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PlacementFlow from "@/app/placement/placement-flow";
import * as api from "@/services/api";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("subject=algebra-1"),
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    startPlacement: vi.fn(),
    skipPlacementQuestion: vi.fn(),
  };
});

const gradedQuestion = {
  question_id: "q1",
  topic_id: "integers-and-operations",
  grade: 6,
  difficulty: "easy" as const,
  question_type: "multiple_choice" as const,
  stem: "What is -3 + 7?",
  options: ["4", "-4", "10", "-10"],
  read_aloud_eligible: false,
};

const higherGradeQuestion = {
  question_id: "q3",
  topic_id: "systems-of-linear-equations",
  grade: 8,
  difficulty: "easy" as const,
  question_type: "multiple_choice" as const,
  stem: "Solve the system of equations.",
  options: ["(0, 0)", "(1, 2)", "(2, 3)", "(3, 4)"],
  read_aloud_eligible: false,
};

const replacementQuestion = {
  question_id: "q4",
  topic_id: "variables-and-expressions",
  grade: 6,
  difficulty: "easy" as const,
  question_type: "multiple_choice" as const,
  stem: "Evaluate 3x + 2 for x = 4.",
  options: ["10", "12", "14", "16"],
  read_aloud_eligible: false,
};

const ungradedQuestion = {
  question_id: "q2",
  topic_id: "cell-structure-and-function",
  grade: null,
  difficulty: "easy" as const,
  question_type: "multiple_choice" as const,
  stem: "Which organelle produces energy?",
  options: ["Nucleus", "Mitochondria", "Ribosome", "Golgi"],
  read_aloud_eligible: false,
};

describe("PlacementFlow grade label", () => {
  beforeEach(() => {
    vi.mocked(api.startPlacement).mockReset();
  });

  it("shows a grade label for a graded subject's question", async () => {
    vi.mocked(api.startPlacement).mockResolvedValue({
      placement_session_id: "session-1",
      questions: [gradedQuestion],
    });

    render(<PlacementFlow />);

    await screen.findByText(/What is -3 \+ 7\?/);
    expect(screen.getByText("Grade 6")).toBeInTheDocument();
  });

  it("shows no grade label for an ungraded subject's question", async () => {
    vi.mocked(api.startPlacement).mockResolvedValue({
      placement_session_id: "session-2",
      questions: [ungradedQuestion],
    });

    render(<PlacementFlow />);

    await screen.findByText(/Which organelle produces energy\?/);
    expect(screen.queryByText(/Grade/)).not.toBeInTheDocument();
  });
});

describe("PlacementFlow read-aloud (spec 019 FR-001/FR-003)", () => {
  beforeEach(() => {
    vi.mocked(api.startPlacement).mockReset();
    // jsdom has no SpeechSynthesis implementation -- stub the minimum
    // surface `canUseReadAloud`/`speak` (src/lib/read-aloud.ts) touch.
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: { speak: vi.fn(), cancel: vi.fn() },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: undefined });
  });

  it("shows a read-aloud control for a read-aloud-eligible question", async () => {
    vi.mocked(api.startPlacement).mockResolvedValue({
      placement_session_id: "session-1",
      questions: [{ ...gradedQuestion, read_aloud_eligible: true }],
    });

    render(<PlacementFlow />);
    await screen.findByText(/What is -3 \+ 7\?/);

    expect(screen.getByTestId("read-aloud-button")).toBeInTheDocument();
  });

  it("shows no read-aloud control when the question is not eligible", async () => {
    vi.mocked(api.startPlacement).mockResolvedValue({
      placement_session_id: "session-1",
      questions: [gradedQuestion],
    });

    render(<PlacementFlow />);
    await screen.findByText(/What is -3 \+ 7\?/);

    expect(screen.queryByTestId("read-aloud-button")).not.toBeInTheDocument();
  });
});

describe("PlacementFlow skip button", () => {
  beforeEach(() => {
    vi.mocked(api.startPlacement).mockReset();
    vi.mocked(api.skipPlacementQuestion).mockReset();
  });

  it("hides the skip button for the lowest shown grade, since the backend always rejects it", async () => {
    vi.mocked(api.startPlacement).mockResolvedValue({
      placement_session_id: "session-1",
      questions: [gradedQuestion, higherGradeQuestion],
    });

    render(<PlacementFlow />);
    await screen.findByText(/Solve the system of equations\./);

    expect(screen.getAllByRole("button", { name: /skip \(too hard\)/i })).toHaveLength(1);
  });

  it("swaps in the replacement question when skip returns one", async () => {
    vi.mocked(api.startPlacement).mockResolvedValue({
      placement_session_id: "session-1",
      questions: [gradedQuestion, higherGradeQuestion],
    });
    vi.mocked(api.skipPlacementQuestion).mockResolvedValue({
      replacement_question: replacementQuestion,
    });

    render(<PlacementFlow />);
    await screen.findByText(/Solve the system of equations\./);

    // gradedQuestion (grade 6) is the lowest shown grade, so only
    // higherGradeQuestion (grade 8) gets a skip button.
    await userEvent.click(screen.getByRole("button", { name: /skip \(too hard\)/i }));

    await screen.findByText(/Evaluate 3x \+ 2 for x = 4\./);
    expect(screen.queryByText(/Solve the system of equations\./)).not.toBeInTheDocument();
    expect(api.skipPlacementQuestion).toHaveBeenCalledWith(
      "session-1",
      higherGradeQuestion.question_id,
    );
  });

  it("removes the question entirely when skip returns no replacement", async () => {
    vi.mocked(api.startPlacement).mockResolvedValue({
      placement_session_id: "session-1",
      questions: [gradedQuestion, higherGradeQuestion],
    });
    vi.mocked(api.skipPlacementQuestion).mockResolvedValue({ replacement_question: null });

    render(<PlacementFlow />);
    await screen.findByText(/Solve the system of equations\./);

    // gradedQuestion (grade 6) is the lowest shown grade, so only
    // higherGradeQuestion (grade 8) gets a skip button.
    await userEvent.click(screen.getByRole("button", { name: /skip \(too hard\)/i }));

    await waitFor(() =>
      expect(screen.queryByText(/Solve the system of equations\./)).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/What is -3 \+ 7\?/)).toBeInTheDocument();
  });
});

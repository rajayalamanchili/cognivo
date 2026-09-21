// Unit test: MultiStepAnswerInput renders one field per step prompt and
// submits them as an ordered array via answerQuestion() (spec 018 T023),
// and AnswerResultView renders the per-step breakdown it reports back.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MultiStepAnswerInput from "@/components/MultiStepAnswerInput";
import AnswerResultView from "@/components/AnswerResultView";
import * as api from "@/services/api";
import type { AnswerResult } from "@/services/api";
import { ApiError } from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    answerQuestion: vi.fn(),
  };
});

const STEPS = ["Isolate the variable term on one side.", "Solve for x."];

describe("MultiStepAnswerInput", () => {
  beforeEach(() => {
    vi.mocked(api.answerQuestion).mockReset();
  });

  it("renders one input per step prompt and submits them as an ordered array", async () => {
    const onGraded = vi.fn();
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: 0.4,
      posterior_p_mastery: 0.6,
      band: "developing",
      graduated_score: 1.0,
      criteria_met: null,
      criteria_missed: null,
      grading_logic_version: "v1",
      first_diverging_step_index: null,
      step_results: [
        { step_index: 0, correct: true, criteria_met: ["a"], criteria_missed: [] },
        { step_index: 1, correct: true, criteria_met: ["b"], criteria_missed: [] },
      ],
    });

    render(<MultiStepAnswerInput questionId="q1" steps={STEPS} onGraded={onGraded} />);

    expect(screen.getByText(STEPS[0])).toBeInTheDocument();
    expect(screen.getByText(STEPS[1])).toBeInTheDocument();

    await userEvent.type(screen.getByTestId("multi-step-input-0"), "3x = 12");
    await userEvent.type(screen.getByTestId("multi-step-input-1"), "x = 4");
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    expect(api.answerQuestion).toHaveBeenCalledWith(
      "q1",
      ["3x = 12", "x = 4"],
      undefined,
      undefined,
    );
    expect(onGraded).toHaveBeenCalledWith(expect.objectContaining({ correct: true }));
  });

  it("disables submission until every step has non-whitespace content", async () => {
    render(<MultiStepAnswerInput questionId="q1" steps={STEPS} onGraded={vi.fn()} />);

    const submitButton = screen.getByRole("button", { name: /submit answer/i });
    expect(submitButton).toBeDisabled();

    await userEvent.type(screen.getByTestId("multi-step-input-0"), "3x = 12");
    expect(submitButton).toBeDisabled();

    await userEvent.type(screen.getByTestId("multi-step-input-1"), "x = 4");
    expect(submitButton).not.toBeDisabled();
  });

  it("shows a grading-unavailable state when the Grading Agent stays down", async () => {
    vi.mocked(api.answerQuestion).mockRejectedValue(
      new ApiError(503, "unavailable", { error: "grading_unavailable" }),
    );

    render(<MultiStepAnswerInput questionId="q1" steps={STEPS} onGraded={vi.fn()} />);

    await userEvent.type(screen.getByTestId("multi-step-input-0"), "3x = 12");
    await userEvent.type(screen.getByTestId("multi-step-input-1"), "x = 4");
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    expect(await screen.findByTestId("multi-step-error-unavailable")).toBeInTheDocument();
  });
});

describe("AnswerResultView step-by-step result", () => {
  const baseResult: AnswerResult = {
    correct: false,
    topic_id: "linear-equations",
    prior_p_mastery: 0.4,
    posterior_p_mastery: 0.31,
    band: "struggling",
    graduated_score: 0.5,
    criteria_met: null,
    criteria_missed: null,
    grading_logic_version: "v1",
    first_diverging_step_index: 1,
    step_results: [
      {
        step_index: 0,
        correct: true,
        criteria_met: ["Chooses to subtract 2 from both sides", "Correctly computes 3x = 12"],
        criteria_missed: [],
      },
      {
        step_index: 1,
        correct: false,
        criteria_met: ["Chooses to divide both sides by 3"],
        criteria_missed: ["Correctly computes x = 4"],
      },
    ],
  };

  it("names the diverging step and distinguishes its met/missed criteria", () => {
    render(<AnswerResultView result={baseResult} />);

    const stepResults = screen.getByTestId("step-results");
    expect(stepResults).toHaveTextContent("Step 1");
    expect(stepResults).toHaveTextContent("Step 2");
    expect(stepResults).toHaveTextContent("Chooses to divide both sides by 3");
    expect(stepResults).toHaveTextContent("Correctly computes x = 4");
  });

  it("renders nothing step-related for a non-multi-step result", () => {
    render(
      <AnswerResultView
        result={{ ...baseResult, first_diverging_step_index: null, step_results: null }}
      />,
    );

    expect(screen.queryByTestId("step-results")).not.toBeInTheDocument();
  });
});

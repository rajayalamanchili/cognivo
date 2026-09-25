// Unit test: MultiStepAnswerInput renders one field per step prompt and
// submits them as an ordered array via answerQuestion() (spec 018 T023),
// and AnswerResultView renders the per-step breakdown it reports back.

import { fireEvent, render, screen, within } from "@testing-library/react";
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

  it("calls onSessionEnded instead of showing a rejection state on a 409", async () => {
    vi.mocked(api.answerQuestion).mockRejectedValue(
      new ApiError(409, "practice session 1: session has ended (status=ended_early)"),
    );
    const onSessionEnded = vi.fn();
    render(
      <MultiStepAnswerInput
        questionId="q1"
        steps={STEPS}
        onGraded={vi.fn()}
        onSessionEnded={onSessionEnded}
      />,
    );

    await userEvent.type(screen.getByTestId("multi-step-input-0"), "3x = 12");
    await userEvent.type(screen.getByTestId("multi-step-input-1"), "x = 4");
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    await vi.waitFor(() => expect(onSessionEnded).toHaveBeenCalledOnce());
    expect(screen.queryByTestId("multi-step-error-unavailable")).not.toBeInTheDocument();
  });

  // Spec 023: each step gets its own notation toolbar (FR-001, FR-002, FR-006).
  it("inserts notation into one step without affecting the other", async () => {
    render(<MultiStepAnswerInput questionId="q1" steps={STEPS} onGraded={vi.fn()} />);

    const step0 = within(screen.getByTestId("multi-step-step-0"));
    const step1 = within(screen.getByTestId("multi-step-step-1"));

    await userEvent.click(step0.getByTestId("notation-fraction-½"));

    expect(screen.getByTestId("multi-step-input-0")).toHaveValue("½");
    expect(screen.getByTestId("multi-step-input-1")).toHaveValue("");
    expect(step1.getByTestId("notation-fraction-insert")).toBeDisabled();
  });

  it("submits notated step answers as the exact composed strings, unchanged by grading (FR-004)", async () => {
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

    render(<MultiStepAnswerInput questionId="q1" steps={STEPS} onGraded={vi.fn()} />);

    await userEvent.click(within(screen.getByTestId("multi-step-step-0")).getByTestId("notation-fraction-½"));
    await userEvent.type(screen.getByTestId("multi-step-input-1"), "x = 4");
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    expect(api.answerQuestion).toHaveBeenCalledWith("q1", ["½", "x = 4"], undefined, undefined);
  });

  // Parity with FreeTextAnswerInput's own MAX_LENGTH guard: the backend
  // enforces 2000 chars on the "\n"-joined concatenation of all steps, so
  // a toolbar insert must be dropped, not silently allowed, once that
  // total would be exceeded.
  it("drops a toolbar insert into a step that would push the concatenated answer past MAX_LENGTH", async () => {
    render(<MultiStepAnswerInput questionId="q1" steps={STEPS} onGraded={vi.fn()} />);

    const step0Input = screen.getByTestId("multi-step-input-0") as HTMLInputElement;
    fireEvent.change(step0Input, { target: { value: "a".repeat(1999) } });

    await userEvent.click(
      within(screen.getByTestId("multi-step-step-0")).getByTestId("notation-fraction-½"),
    );

    expect(step0Input.value).toBe("a".repeat(1999));
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

// Regression test (issue #94): the backend omits step_results/criteria_met/
// criteria_missed entirely (not `null`) for MC/numeric answers
// (contracts/api.md, questions.py's answer_body), so `result.step_results`
// is `undefined`, not `null`, on the vast majority of practice submissions.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AnswerResultView from "@/components/AnswerResultView";
import type { AnswerResultViewData } from "@/components/AnswerResultView";

describe("AnswerResultView", () => {
  it("renders an MC/numeric result whose optional fields are absent, not null", () => {
    const result: AnswerResultViewData = {
      correct: true,
      topic_id: "order-of-operations",
      prior_p_mastery: 0.48,
      posterior_p_mastery: 0.6,
      band: "developing",
      criteria_met: null,
      criteria_missed: null,
      // step_results deliberately omitted -- matches the real JSON body.
    };

    expect(() => render(<AnswerResultView result={result} />)).not.toThrow();
    expect(screen.getByText("Correct!")).toBeInTheDocument();
    expect(screen.queryByTestId("step-results")).not.toBeInTheDocument();
    expect(screen.getByText("48%")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
  });

  it("omits the mastery-change section when prior_p_mastery is null (e.g. a reconstructed quiz result)", () => {
    const result: AnswerResultViewData = {
      correct: true,
      topic_id: "order-of-operations",
      prior_p_mastery: null,
      posterior_p_mastery: 0.6,
      band: "developing",
      criteria_met: null,
      criteria_missed: null,
    };

    render(<AnswerResultView result={result} />);

    expect(screen.queryByText("YOUR MASTERY")).not.toBeInTheDocument();
  });

  it("renders the step-by-step section when step_results is populated", () => {
    const result: AnswerResultViewData = {
      correct: false,
      topic_id: "linear-equations",
      prior_p_mastery: 0.45,
      posterior_p_mastery: 0.4,
      band: "developing",
      criteria_met: null,
      criteria_missed: null,
      step_results: [
        { step_index: 0, correct: true, criteria_met: ["Isolates the variable"], criteria_missed: [] },
        { step_index: 1, correct: false, criteria_met: [], criteria_missed: ["Computes the final value"] },
      ],
    };

    render(<AnswerResultView result={result} />);

    expect(screen.getByTestId("step-results")).toBeInTheDocument();
    expect(screen.getByText("Isolates the variable")).toBeInTheDocument();
    expect(screen.getByText("Computes the final value")).toBeInTheDocument();
  });
});

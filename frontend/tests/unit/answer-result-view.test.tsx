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
    const result = {
      correct: true,
      topic_id: "order-of-operations",
      posterior_p_mastery: 0.6,
      band: "developing",
      criteria_met: null,
      criteria_missed: null,
      // step_results deliberately omitted -- matches the real JSON body.
    } as unknown as AnswerResultViewData;

    expect(() => render(<AnswerResultView result={result} />)).not.toThrow();
    expect(screen.getByText("Correct!")).toBeInTheDocument();
  });
});

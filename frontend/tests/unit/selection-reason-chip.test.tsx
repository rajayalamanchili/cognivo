// Unit tests: SelectionReasonChip (spec 025 User Story 1, FR-001/002/003/004).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SelectionReasonChip from "@/components/SelectionReasonChip";
import type { NextQuestion } from "@/services/api";

function question(overrides: Partial<NextQuestion> = {}): NextQuestion {
  return {
    question_id: "q1",
    topic_id: "t1",
    difficulty: "medium",
    question_type: "multiple_choice",
    stem: "stem",
    options: null,
    image_url: null,
    image_alt_text: null,
    steps: null,
    read_aloud_eligible: false,
    unlocked_grade: null,
    is_fallback: false,
    p_mastery: null,
    effective_p_mastery: null,
    last_practiced_at: null,
    ...overrides,
  };
}

const SIX_MONTHS_AGO = new Date(Date.now() - 183 * 86_400_000).toISOString();

describe("SelectionReasonChip", () => {
  it("renders review-style copy naming elapsed time for a fallback/decayed pick", () => {
    render(
      <SelectionReasonChip
        question={question({
          is_fallback: true,
          p_mastery: 0.8,
          effective_p_mastery: 0.5,
          last_practiced_at: SIX_MONTHS_AGO,
        })}
      />
    );
    const chip = screen.getByTestId("selection-reason-chip");
    expect(chip.textContent).toMatch(/review|practiced|decay/i);
    expect(chip.textContent).toMatch(/month/i);
  });

  it("does not claim elapsed time for a fallback pick that hasn't actually decayed (issue: practiced today)", () => {
    render(
      <SelectionReasonChip
        question={question({
          is_fallback: true,
          p_mastery: 0.9,
          effective_p_mastery: 0.9,
          last_practiced_at: new Date().toISOString(),
        })}
      />
    );
    const chip = screen.getByTestId("selection-reason-chip");
    expect(chip.textContent).not.toMatch(/while|today|month|week|year/i);
  });

  it("renders next-step-style copy for an eligible-pool pick by default", () => {
    render(<SelectionReasonChip question={question({ is_fallback: false })} />);
    const chip = screen.getByTestId("selection-reason-chip");
    expect(chip.textContent).not.toMatch(/review|decay/i);
  });

  it("omits the chip for an eligible-pool pick when explainEveryPick is false", () => {
    render(
      <SelectionReasonChip question={question({ is_fallback: false })} explainEveryPick={false} />
    );
    expect(screen.queryByTestId("selection-reason-chip")).not.toBeInTheDocument();
  });

  it("still renders for a fallback pick even when explainEveryPick is false (FR-003)", () => {
    render(
      <SelectionReasonChip
        question={question({
          is_fallback: true,
          p_mastery: 0.8,
          effective_p_mastery: 0.5,
          last_practiced_at: SIX_MONTHS_AGO,
        })}
        explainEveryPick={false}
      />
    );
    expect(screen.getByTestId("selection-reason-chip")).toBeInTheDocument();
  });

  it("omits the chip rather than fabricating a reason when a fallback pick has no mastery data (FR-004)", () => {
    render(
      <SelectionReasonChip
        question={question({ is_fallback: true, p_mastery: null, effective_p_mastery: null })}
      />
    );
    expect(screen.queryByTestId("selection-reason-chip")).not.toBeInTheDocument();
  });
});

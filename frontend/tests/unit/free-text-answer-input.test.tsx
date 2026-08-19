// Unit test: FreeTextAnswerInput renders a textarea and submits its
// value via answerQuestion() (spec 007 T026).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FreeTextAnswerInput from "@/components/FreeTextAnswerInput";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    answerQuestion: vi.fn(),
  };
});

describe("FreeTextAnswerInput", () => {
  beforeEach(() => {
    vi.mocked(api.answerQuestion).mockReset();
  });

  it("submits the textarea's value via answerQuestion() and reports the graded result", async () => {
    const onGraded = vi.fn();
    vi.mocked(api.answerQuestion).mockResolvedValue({
      correct: true,
      topic_id: "linear-equations",
      prior_p_mastery: 0.4,
      posterior_p_mastery: 0.6,
      band: "developing",
    });

    render(<FreeTextAnswerInput questionId="q1" onGraded={onGraded} />);

    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "The independent variable is x.");
    await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    expect(api.answerQuestion).toHaveBeenCalledWith("q1", "The independent variable is x.");
    expect(onGraded).toHaveBeenCalledWith(
      expect.objectContaining({ correct: true, topic_id: "linear-equations" }),
    );
  });

  it("disables submission until the textarea has non-whitespace content", async () => {
    render(<FreeTextAnswerInput questionId="q1" onGraded={vi.fn()} />);

    const submitButton = screen.getByRole("button", { name: /submit answer/i });
    expect(submitButton).toBeDisabled();

    await userEvent.type(screen.getByRole("textbox"), "   ");
    expect(submitButton).toBeDisabled();

    await userEvent.type(screen.getByRole("textbox"), "an answer");
    expect(submitButton).not.toBeDisabled();
  });
});

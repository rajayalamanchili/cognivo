// Unit test: the free-text answer flow renders five distinct states --
// grading-in-progress, too-long, rate-limited, moderation-rejected, and
// grading-unavailable -- without conflating any of them (spec 007
// FR-018, T027).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FreeTextAnswerInput from "@/components/FreeTextAnswerInput";
import * as api from "@/services/api";
import { ApiError } from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    answerQuestion: vi.fn(),
  };
});

const ALL_STATE_TESTIDS = [
  "free-text-error-too-long",
  "free-text-error-rate-limited",
  "free-text-error-moderation",
  "free-text-error-unavailable",
];

async function submit() {
  await userEvent.type(screen.getByRole("textbox"), "an answer");
  await userEvent.click(screen.getByRole("button", { name: /submit answer/i }));
}

function expectOnlyVisible(testId: string | null) {
  for (const id of ALL_STATE_TESTIDS) {
    if (id === testId) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    } else {
      expect(screen.queryByTestId(id)).not.toBeInTheDocument();
    }
  }
}

describe("FreeTextAnswerInput rejection states", () => {
  beforeEach(() => {
    vi.mocked(api.answerQuestion).mockReset();
  });

  it("shows a grading-in-progress state while the submission is in flight", async () => {
    let resolveAnswer: (() => void) | undefined;
    vi.mocked(api.answerQuestion).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveAnswer = () =>
            resolve({
              correct: true,
              topic_id: "t",
              prior_p_mastery: null,
              posterior_p_mastery: 0.5,
              band: "developing",
              graduated_score: 0.9,
              criteria_met: [],
              criteria_missed: [],
              grading_logic_version: "v1",
            });
        }),
    );

    render(<FreeTextAnswerInput questionId="q1" onGraded={vi.fn()} />);
    await submit();

    expect(screen.getByRole("button", { name: /grading/i })).toBeDisabled();
    expectOnlyVisible(null);

    resolveAnswer?.();
  });

  it("shows the too-long state and no other rejection state", async () => {
    vi.mocked(api.answerQuestion).mockRejectedValue(
      new ApiError(422, "too long", { error: "answer_too_long", max_length: 2000 }),
    );
    render(<FreeTextAnswerInput questionId="q1" onGraded={vi.fn()} />);
    await submit();
    await screen.findByTestId("free-text-error-too-long");
    expectOnlyVisible("free-text-error-too-long");
  });

  it("shows the rate-limited state and no other rejection state", async () => {
    vi.mocked(api.answerQuestion).mockRejectedValue(
      new ApiError(429, "rate limited", { error: "rate_limited", retry_after_seconds: 137 }),
    );
    render(<FreeTextAnswerInput questionId="q1" onGraded={vi.fn()} />);
    await submit();
    await screen.findByTestId("free-text-error-rate-limited");
    expectOnlyVisible("free-text-error-rate-limited");
  });

  it("shows the moderation-rejected state and no other rejection state", async () => {
    vi.mocked(api.answerQuestion).mockRejectedValue(
      new ApiError(422, "moderation rejected", { error: "moderation_rejected" }),
    );
    render(<FreeTextAnswerInput questionId="q1" onGraded={vi.fn()} />);
    await submit();
    await screen.findByTestId("free-text-error-moderation");
    expectOnlyVisible("free-text-error-moderation");
  });

  it("shows the grading-unavailable state and no other rejection state", async () => {
    vi.mocked(api.answerQuestion).mockRejectedValue(
      new ApiError(503, "grading unavailable", { error: "grading_unavailable" }),
    );
    render(<FreeTextAnswerInput questionId="q1" onGraded={vi.fn()} />);
    await submit();
    await screen.findByTestId("free-text-error-unavailable");
    expectOnlyVisible("free-text-error-unavailable");
  });
});

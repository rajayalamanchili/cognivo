// Unit test: QuestionCard's read-aloud control (spec 019 FR-001/FR-002/
// FR-002a, research.md Decision 1).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import QuestionCard from "@/components/QuestionCard";
import type { NextQuestion } from "@/services/api";

const baseQuestion: NextQuestion = {
  question_id: "q1",
  topic_id: "systems-of-equations",
  difficulty: "easy",
  question_type: "multiple_choice",
  stem: "Where do the two lines intersect?",
  options: ["(2, 3)", "(0, 1)", "(5, 0)", "(-1, 2)"],
  image_url: null,
  image_alt_text: null,
  steps: null,
  read_aloud_eligible: true,
  unlocked_grade: null,
};

function stubSpeechSynthesis() {
  Object.defineProperty(window, "speechSynthesis", {
    configurable: true,
    value: { speak: vi.fn(), cancel: vi.fn() },
  });
  // jsdom has no SpeechSynthesisUtterance constructor either.
  vi.stubGlobal(
    "SpeechSynthesisUtterance",
    class {
      text: string;
      constructor(text: string) {
        this.text = text;
      }
    },
  );
}

function removeSpeechSynthesis() {
  Object.defineProperty(window, "speechSynthesis", {
    configurable: true,
    value: undefined,
  });
}

describe("QuestionCard read-aloud", () => {
  afterEach(() => {
    removeSpeechSynthesis();
    vi.unstubAllGlobals();
  });

  it("renders the control when enabled and speech synthesis is available", () => {
    stubSpeechSynthesis();
    render(
      <QuestionCard
        question={baseQuestion}
        response=""
        onResponseChange={vi.fn()}
        onFlag={vi.fn()}
        flagged={false}
        readAloudEnabled
      />,
    );

    expect(screen.getByTestId("read-aloud-button")).toBeInTheDocument();
  });

  it("does not render when readAloudEnabled is false", () => {
    stubSpeechSynthesis();
    render(
      <QuestionCard
        question={baseQuestion}
        response=""
        onResponseChange={vi.fn()}
        onFlag={vi.fn()}
        flagged={false}
        readAloudEnabled={false}
      />,
    );

    expect(screen.queryByTestId("read-aloud-button")).not.toBeInTheDocument();
  });

  it("degrades gracefully (no control) when the browser has no speechSynthesis (FR-002a)", () => {
    removeSpeechSynthesis();
    render(
      <QuestionCard
        question={baseQuestion}
        response=""
        onResponseChange={vi.fn()}
        onFlag={vi.fn()}
        flagged={false}
        readAloudEnabled
      />,
    );

    expect(screen.queryByTestId("read-aloud-button")).not.toBeInTheDocument();
    // The question remains fully usable as text -- the options are
    // still rendered normally.
    expect(screen.getByText("(2, 3)")).toBeInTheDocument();
  });

  it("does not clear the in-progress response or call onResponseChange when clicked (FR-002)", async () => {
    stubSpeechSynthesis();
    const onResponseChange = vi.fn();
    const user = userEvent.setup();
    render(
      <QuestionCard
        question={baseQuestion}
        response="1"
        onResponseChange={onResponseChange}
        onFlag={vi.fn()}
        flagged={false}
        readAloudEnabled
      />,
    );

    await user.click(screen.getByTestId("read-aloud-button"));

    expect(onResponseChange).not.toHaveBeenCalled();
    expect(window.speechSynthesis.speak).toHaveBeenCalledTimes(1);
  });

  it("reports usage once via onReadAloudUsed, even across replays", async () => {
    stubSpeechSynthesis();
    const onReadAloudUsed = vi.fn();
    const user = userEvent.setup();
    render(
      <QuestionCard
        question={baseQuestion}
        response=""
        onResponseChange={vi.fn()}
        onFlag={vi.fn()}
        flagged={false}
        readAloudEnabled
        onReadAloudUsed={onReadAloudUsed}
      />,
    );

    const button = screen.getByTestId("read-aloud-button");
    expect(button).toHaveTextContent("Read aloud");

    await user.click(button);
    expect(onReadAloudUsed).toHaveBeenCalledTimes(1);
    expect(button).toHaveTextContent("Replay");

    await user.click(button);
    expect(onReadAloudUsed).toHaveBeenCalledTimes(1);
    expect(window.speechSynthesis.speak).toHaveBeenCalledTimes(2);
  });
});

"use client";

import { useState } from "react";
import {
  answerQuestion,
  ApiError,
  type AnswerResult,
  type FreeTextErrorBody,
} from "@/services/api";

// Free-text owns its own submission (unlike MC/numeric, whose submit
// button lives in the parent flow page) so it can render FR-018's five
// distinct states -- grading-in-progress plus the four guardrail
// rejections -- without the parent needing to know about any of them.

export interface FreeTextAnswerInputProps {
  questionId: string;
  onGraded: (result: AnswerResult) => void;
  disabled?: boolean;
}

type SubmitState =
  | "idle"
  | "grading-in-progress"
  | "too-long"
  | "rate-limited"
  | "moderation-rejected"
  | "grading-unavailable";

const MAX_LENGTH = 2000;

function stateFromError(error: unknown): SubmitState {
  if (error instanceof ApiError && error.body && typeof error.body === "object") {
    const body = error.body as FreeTextErrorBody;
    if (body.error === "answer_too_long") return "too-long";
    if (body.error === "rate_limited") return "rate-limited";
    if (body.error === "moderation_rejected") return "moderation-rejected";
    if (body.error === "grading_unavailable") return "grading-unavailable";
  }
  return "idle";
}

export default function FreeTextAnswerInput({
  questionId,
  onGraded,
  disabled,
}: FreeTextAnswerInputProps) {
  const [text, setText] = useState("");
  const [state, setState] = useState<SubmitState>("idle");

  async function handleSubmit() {
    setState("grading-in-progress");
    try {
      const result = await answerQuestion(questionId, text);
      setState("idle");
      onGraded(result);
    } catch (error) {
      setState(stateFromError(error));
    }
  }

  const busy = disabled || state === "grading-in-progress";

  return (
    <div className="flex flex-col gap-2" data-testid="free-text-answer-input">
      <textarea
        className="rounded-lg border border-border px-3 py-2"
        rows={4}
        maxLength={MAX_LENGTH}
        value={text}
        onChange={(event) => setText(event.target.value)}
        disabled={busy}
      />
      <button
        type="button"
        onClick={handleSubmit}
        disabled={busy || text.trim() === ""}
        className="self-start rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-40"
      >
        {state === "grading-in-progress" ? "Grading…" : "Submit Answer"}
      </button>

      {state === "too-long" && (
        <p className="text-sm text-error" data-testid="free-text-error-too-long">
          Your answer is too long (max {MAX_LENGTH} characters). Please shorten it and resubmit.
        </p>
      )}
      {state === "rate-limited" && (
        <p className="text-sm text-error" data-testid="free-text-error-rate-limited">
          You&apos;ve submitted too many answers recently. Please wait a bit and try again.
        </p>
      )}
      {state === "moderation-rejected" && (
        <p className="text-sm text-error" data-testid="free-text-error-moderation">
          This answer couldn&apos;t be accepted. Please revise and resubmit.
        </p>
      )}
      {state === "grading-unavailable" && (
        <p className="text-sm text-error" data-testid="free-text-error-unavailable">
          Grading is temporarily unavailable. Please try again shortly.
        </p>
      )}
    </div>
  );
}

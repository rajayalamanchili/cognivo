"use client";

import { useState } from "react";
import {
  answerQuestion,
  ApiError,
  type AnswerResult,
  type FreeTextErrorBody,
} from "@/services/api";

// Multi-step owns its own submission, same reasoning as
// `FreeTextAnswerInput` (spec 018 extends spec 007's Grading Agent): one
// text field per expected step, submitted together as a single batched
// grading call (FR-003a) rather than the parent flow's shared
// `response`/`onResponseChange` props MC/numeric use.

export interface MultiStepAnswerInputProps {
  questionId: string;
  steps: string[];
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

export default function MultiStepAnswerInput({
  questionId,
  steps,
  onGraded,
  disabled,
}: MultiStepAnswerInputProps) {
  const [answers, setAnswers] = useState<string[]>(() => steps.map(() => ""));
  const [state, setState] = useState<SubmitState>("idle");

  function updateStep(index: number, value: string) {
    setAnswers((previous) => previous.map((answer, i) => (i === index ? value : answer)));
  }

  async function handleSubmit() {
    setState("grading-in-progress");
    try {
      const result = await answerQuestion(questionId, answers);
      setState("idle");
      onGraded(result);
    } catch (error) {
      setState(stateFromError(error));
    }
  }

  const busy = disabled || state === "grading-in-progress";
  const allStepsFilled = answers.every((answer) => answer.trim() !== "");

  return (
    <div className="flex flex-col gap-3" data-testid="multi-step-answer-input">
      {steps.map((stepPrompt, index) => (
        <div key={index} className="flex flex-col gap-1">
          <label className="text-sm text-muted">{stepPrompt}</label>
          <input
            type="text"
            className="rounded-lg border border-border px-3 py-2"
            value={answers[index]}
            onChange={(event) => updateStep(index, event.target.value)}
            disabled={busy}
            data-testid={`multi-step-input-${index}`}
          />
        </div>
      ))}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={busy || !allStepsFilled}
        className="self-start rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-40"
      >
        {state === "grading-in-progress" ? "Grading…" : "Submit Answer"}
      </button>

      {state === "too-long" && (
        <p className="text-sm text-error" data-testid="multi-step-error-too-long">
          Your answer is too long. Please shorten it and resubmit.
        </p>
      )}
      {state === "rate-limited" && (
        <p className="text-sm text-error" data-testid="multi-step-error-rate-limited">
          You&apos;ve submitted too many answers recently. Please wait a bit and try again.
        </p>
      )}
      {state === "moderation-rejected" && (
        <p className="text-sm text-error" data-testid="multi-step-error-moderation">
          This answer couldn&apos;t be accepted. Please revise and resubmit.
        </p>
      )}
      {state === "grading-unavailable" && (
        <p className="text-sm text-error" data-testid="multi-step-error-unavailable">
          Grading is temporarily unavailable. Please try again shortly.
        </p>
      )}
    </div>
  );
}

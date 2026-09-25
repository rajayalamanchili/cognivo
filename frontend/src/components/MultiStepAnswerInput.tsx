"use client";

import { useRef, useState } from "react";
import {
  answerQuestion,
  ApiError,
  isAlreadyAnsweredError,
  type AnswerResult,
  type FreeTextErrorBody,
} from "@/services/api";
import LoadingIndicator from "@/components/LoadingIndicator";
import NotationToolbar from "@/components/NotationToolbar";

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
  readAloudUsed?: boolean;
  handoffToken?: string | null;
  // Spec 022: same reasoning as FreeTextAnswerInput's own onSessionEnded.
  onSessionEnded?: () => void;
  // PR feedback: same reasoning as FreeTextAnswerInput's own onBusyChange.
  onBusyChange?: (busy: boolean) => void;
}

// Matches backend guardrails.MAX_ANSWER_LENGTH, checked there against the
// "\n"-joined concatenation of all steps (questions.py's
// _grade_stepwise_submission) -- mirrored here so a toolbar insert can't
// silently push the submission past that limit.
const MAX_LENGTH = 2000;

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
  readAloudUsed,
  handoffToken,
  onSessionEnded,
  onBusyChange,
}: MultiStepAnswerInputProps) {
  const [answers, setAnswers] = useState<string[]>(() => steps.map(() => ""));
  const [state, setState] = useState<SubmitState>("idle");
  const stepRefs = useRef<(HTMLInputElement | null)[]>([]);

  function updateStep(index: number, value: string) {
    setAnswers((previous) => previous.map((answer, i) => (i === index ? value : answer)));
  }

  // Spec 023 FR-001/FR-002/FR-006: same cursor-insertion behavior as
  // FreeTextAnswerInput -- see that component's comment for why this
  // deliberately does not restore focus/cursor afterward.
  function insertNotation(index: number, insertText: string) {
    const el = stepRefs.current[index];
    const current = answers[index];
    const start = el?.selectionStart ?? current.length;
    const end = el?.selectionEnd ?? current.length;
    const nextStep = current.slice(0, start) + insertText + current.slice(end);
    const nextAnswers = answers.map((answer, i) => (i === index ? nextStep : answer));
    if (nextAnswers.join("\n").length > MAX_LENGTH) return;
    updateStep(index, nextStep);
  }

  async function handleSubmit() {
    setState("grading-in-progress");
    onBusyChange?.(true);
    try {
      const result = await answerQuestion(questionId, answers, readAloudUsed, handoffToken);
      setState("idle");
      onGraded(result);
    } catch (error) {
      // PR feedback: a duplicate-submit 409 isn't a session-ended 409 --
      // falls through to stateFromError below, same as any other
      // unrecognized error shape (resets to "idle").
      if (!isAlreadyAnsweredError(error) && onSessionEnded && error instanceof ApiError && error.status === 409) {
        onSessionEnded();
        return;
      }
      setState(stateFromError(error));
    } finally {
      onBusyChange?.(false);
    }
  }

  const busy = disabled || state === "grading-in-progress";
  const allStepsFilled = answers.every((answer) => answer.trim() !== "");

  return (
    <div className="flex flex-col gap-3" data-testid="multi-step-answer-input">
      {steps.map((stepPrompt, index) => (
        <div key={index} className="flex flex-col gap-1" data-testid={`multi-step-step-${index}`}>
          <label className="text-sm text-muted">{stepPrompt}</label>
          <NotationToolbar onInsert={(text) => insertNotation(index, text)} disabled={busy} />
          <input
            ref={(el) => {
              stepRefs.current[index] = el;
            }}
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
        {state === "grading-in-progress" ? (
          <LoadingIndicator message="Checking each step…" compact />
        ) : (
          "Submit Answer"
        )}
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

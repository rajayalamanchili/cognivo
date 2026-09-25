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

// Free-text owns its own submission (unlike MC/numeric, whose submit
// button lives in the parent flow page) so it can render FR-018's five
// distinct states -- grading-in-progress plus the four guardrail
// rejections -- without the parent needing to know about any of them.

export interface FreeTextAnswerInputProps {
  questionId: string;
  onGraded: (result: AnswerResult) => void;
  disabled?: boolean;
  readAloudUsed?: boolean;
  handoffToken?: string | null;
  // Spec 022: a timed session's real (server) deadline can pass before
  // the client-side countdown's own onExpire fires (clock drift, a
  // throttled background tab) -- if that happens mid-submission here,
  // the parent flow's existing 409 handling (routing to the summary/
  // ended screen, same as the MC/numeric submit path) should take over
  // instead of this component falling through to a silent idle state.
  onSessionEnded?: () => void;
  // PR feedback: free_text/multi_step submit themselves, so the parent's
  // `phase` never reflects a grading call in flight here -- this lets the
  // parent's countdown-expiry/end-now guards see it too.
  onBusyChange?: (busy: boolean) => void;
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
  readAloudUsed,
  handoffToken,
  onSessionEnded,
  onBusyChange,
}: FreeTextAnswerInputProps) {
  const [text, setText] = useState("");
  const [state, setState] = useState<SubmitState>("idle");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Spec 023 FR-001/FR-002: insert at the cursor rather than appending,
  // so a learner can drop a fraction into the middle of an answer.
  // Deliberately does not restore focus/cursor afterward -- a delayed
  // refocus raced with fast subsequent typing elsewhere (e.g. tabbing
  // to another field right after a toolbar click) and stole keystrokes
  // back into this field. Reading selectionStart/End synchronously
  // before the click's own focus change is enough for correct
  // insertion position; anything after that is an unrequested nicety
  // not worth the race.
  function insertNotation(insertText: string) {
    const el = textareaRef.current;
    const start = el?.selectionStart ?? text.length;
    const end = el?.selectionEnd ?? text.length;
    // The textarea's own maxLength only constrains keystroke/IME input,
    // not this programmatic insert -- guard here too. Dropping the whole
    // insert (rather than slicing the composed string) keeps
    // NotationToolbar's "only complete units reach the field" guarantee
    // intact instead of truncating a multi-character construct mid-way.
    const composed = text.slice(0, start) + insertText + text.slice(end);
    if (composed.length > MAX_LENGTH) return;
    setText(composed);
  }

  async function handleSubmit() {
    setState("grading-in-progress");
    onBusyChange?.(true);
    try {
      const result = await answerQuestion(questionId, text, readAloudUsed, handoffToken);
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

  return (
    <div className="flex flex-col gap-2" data-testid="free-text-answer-input">
      <NotationToolbar onInsert={insertNotation} disabled={busy} />
      <textarea
        ref={textareaRef}
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
        {state === "grading-in-progress" ? (
          <LoadingIndicator message="Reading your answer…" compact />
        ) : (
          "Submit Answer"
        )}
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

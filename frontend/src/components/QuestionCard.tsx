"use client";

import { useState } from "react";
import type { AnswerResult, NextQuestion } from "@/services/api";
import FreeTextAnswerInput from "@/components/FreeTextAnswerInput";
import MultiStepAnswerInput from "@/components/MultiStepAnswerInput";
import { canUseReadAloud, speak } from "@/lib/read-aloud";

// Presentational + flag-affordance only (FR-011) -- answer submission and
// question fetching stay owned by the page that renders this card, with
// two exceptions: `free_text` and `multi_step` questions submit
// themselves (via `FreeTextAnswerInput`/`MultiStepAnswerInput`, spec 007
// FR-018/spec 018 FR-003a), reported back through the shared
// `onFreeTextGraded` callback rather than the `response`/
// `onResponseChange` props MC/numeric use.

export interface QuestionCardProps {
  question: NextQuestion;
  response: string;
  onResponseChange: (value: string) => void;
  onFlag: (reason: string) => void;
  flagged: boolean;
  disabled?: boolean;
  onFreeTextGraded?: (result: AnswerResult) => void;
  // Read-aloud (spec 019 FR-001/FR-002/FR-002a, research.md Decision 1)
  // -- `readAloudEnabled` gates the control's visibility (grades 1-2
  // only, per `question.read_aloud_eligible`); `onReadAloudUsed` fires
  // once, the first time it's triggered for this question, so the
  // parent flow can report `read_aloud_used` on answer submission
  // (FR-012).
  readAloudEnabled?: boolean;
  onReadAloudUsed?: () => void;
  // spec 019 FR-005b: forwarded to FreeTextAnswerInput/MultiStepAnswerInput,
  // which submit their own answers independently of the parent flow.
  handoffToken?: string | null;
  // Spec 022: forwarded to FreeTextAnswerInput/MultiStepAnswerInput so a
  // 409 on their own independent submission can route through the
  // parent flow's existing session-ended handling.
  onSessionEnded?: () => void;
  // PR feedback: forwarded to FreeTextAnswerInput/MultiStepAnswerInput so
  // the parent flow can gate its countdown-expiry/end-now guards on a
  // grading call those two own independently of `disabled`/phase.
  onBusyChange?: (busy: boolean) => void;
}

const DEFAULT_FLAG_REASON = "Learner flagged this question's answer key as incorrect.";

// Every answer choice, in the same order they're rendered (FR-001) --
// covers multiple_choice's options and multi_step's step prompts;
// free_text/numeric questions have neither, so just the stem is read.
function buildReadAloudText(question: NextQuestion): string {
  const parts = [question.stem];
  if (question.options) parts.push(...question.options);
  if (question.steps) parts.push(...question.steps);
  return parts.join(". ");
}

export default function QuestionCard({
  question,
  response,
  onResponseChange,
  onFlag,
  flagged,
  disabled,
  onFreeTextGraded,
  readAloudEnabled,
  onReadAloudUsed,
  handoffToken,
  onSessionEnded,
  onBusyChange,
}: QuestionCardProps) {
  const [showFlagForm, setShowFlagForm] = useState(false);
  const [reason, setReason] = useState("");
  const [readAloudUsed, setReadAloudUsed] = useState(false);

  function handleFlagSubmit() {
    onFlag(reason.trim() || DEFAULT_FLAG_REASON);
    setShowFlagForm(false);
    setReason("");
  }

  function handleReadAloud() {
    speak(buildReadAloudText(question));
    if (!readAloudUsed) {
      setReadAloudUsed(true);
      onReadAloudUsed?.();
    }
  }

  const canReadAloud = readAloudEnabled && canUseReadAloud();

  return (
    <fieldset className="flex flex-col gap-3" disabled={disabled} data-testid="question-card">
      <legend className="font-medium">{question.stem}</legend>

      {canReadAloud && (
        <button
          type="button"
          onClick={handleReadAloud}
          className="self-start rounded-lg border border-border px-3 py-1.5 text-sm"
          data-testid="read-aloud-button"
        >
          🔊 {readAloudUsed ? "Replay" : "Read aloud"}
        </button>
      )}

      {question.image_url ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- deliberately
              a plain <img>, not next/image: SVG is an allowed content format
              (research.md §2) and next/image's optimizer doesn't handle SVG by
              default, plus this is a static asset synced ahead of time, not one
              that benefits from next/image's runtime resizing/optimization. */}
          <img
            src={question.image_url}
            alt={question.image_alt_text ?? ""}
            className="max-w-full rounded-lg border border-border"
          />
        </>
      ) : null}

      {question.question_type === "multiple_choice" && question.options ? (
        <div className="flex flex-col gap-2">
          {question.options.map((option, index) => (
            <label key={index} className="flex items-center gap-2">
              <input
                type="radio"
                name={question.question_id}
                value={index}
                checked={response === String(index)}
                onChange={() => onResponseChange(String(index))}
              />
              {option}
            </label>
          ))}
        </div>
      ) : question.question_type === "free_text" ? (
        <FreeTextAnswerInput
          questionId={question.question_id}
          onGraded={(result) => onFreeTextGraded?.(result)}
          disabled={disabled}
          readAloudUsed={readAloudUsed}
          handoffToken={handoffToken}
          onSessionEnded={onSessionEnded}
          onBusyChange={onBusyChange}
        />
      ) : question.question_type === "multi_step" ? (
        <MultiStepAnswerInput
          questionId={question.question_id}
          steps={question.steps ?? []}
          onGraded={(result) => onFreeTextGraded?.(result)}
          disabled={disabled}
          readAloudUsed={readAloudUsed}
          handoffToken={handoffToken}
          onSessionEnded={onSessionEnded}
          onBusyChange={onBusyChange}
        />
      ) : (
        <input
          type="number"
          step="any"
          className="rounded-lg border border-border px-3 py-2"
          value={response}
          onChange={(event) => onResponseChange(event.target.value)}
        />
      )}

      {flagged ? (
        <p className="text-sm text-muted">Flagged for review -- thanks for the report.</p>
      ) : showFlagForm ? (
        <div className="flex flex-col gap-2">
          <input
            type="text"
            placeholder="Why is this question wrong? (optional)"
            className="rounded-lg border border-border px-3 py-2 text-sm"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleFlagSubmit}
              className="text-sm text-error underline"
            >
              Submit flag
            </button>
            <button
              type="button"
              onClick={() => setShowFlagForm(false)}
              className="text-sm text-muted underline"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowFlagForm(true)}
          className="self-start text-sm text-muted underline"
        >
          Flag this question
        </button>
      )}
    </fieldset>
  );
}

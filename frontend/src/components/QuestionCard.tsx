"use client";

import { useState } from "react";
import type { AnswerResult, NextQuestion } from "@/services/api";
import FreeTextAnswerInput from "@/components/FreeTextAnswerInput";

// Presentational + flag-affordance only (FR-011) -- answer submission and
// question fetching stay owned by the page that renders this card, with
// one exception: `free_text` questions submit themselves via
// `FreeTextAnswerInput` (spec 007 FR-018), reported back through
// `onFreeTextGraded` rather than the shared `response`/`onResponseChange`
// props MC/numeric use.

export interface QuestionCardProps {
  question: NextQuestion;
  response: string;
  onResponseChange: (value: string) => void;
  onFlag: (reason: string) => void;
  flagged: boolean;
  disabled?: boolean;
  onFreeTextGraded?: (result: AnswerResult) => void;
}

const DEFAULT_FLAG_REASON = "Learner flagged this question's answer key as incorrect.";

export default function QuestionCard({
  question,
  response,
  onResponseChange,
  onFlag,
  flagged,
  disabled,
  onFreeTextGraded,
}: QuestionCardProps) {
  const [showFlagForm, setShowFlagForm] = useState(false);
  const [reason, setReason] = useState("");

  function handleFlagSubmit() {
    onFlag(reason.trim() || DEFAULT_FLAG_REASON);
    setShowFlagForm(false);
    setReason("");
  }

  return (
    <fieldset className="flex flex-col gap-3" disabled={disabled} data-testid="question-card">
      <legend className="font-medium">{question.stem}</legend>

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

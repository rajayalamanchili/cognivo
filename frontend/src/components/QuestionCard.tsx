"use client";

import { useState } from "react";
import type { NextQuestion } from "@/services/api";

// Presentational + flag-affordance only (FR-011) -- answer submission and
// question fetching stay owned by the page that renders this card.

export interface QuestionCardProps {
  question: NextQuestion;
  response: string;
  onResponseChange: (value: string) => void;
  onFlag: (reason: string) => void;
  flagged: boolean;
  disabled?: boolean;
}

const DEFAULT_FLAG_REASON = "Learner flagged this question's answer key as incorrect.";

export default function QuestionCard({
  question,
  response,
  onResponseChange,
  onFlag,
  flagged,
  disabled,
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
      ) : (
        <input
          type="number"
          step="any"
          className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
          value={response}
          onChange={(event) => onResponseChange(event.target.value)}
        />
      )}

      {flagged ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Flagged for review -- thanks for the report.
        </p>
      ) : showFlagForm ? (
        <div className="flex flex-col gap-2">
          <input
            type="text"
            placeholder="Why is this question wrong? (optional)"
            className="rounded border border-black/20 px-3 py-2 text-sm dark:border-white/20"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleFlagSubmit}
              className="text-sm text-red-600 underline"
            >
              Submit flag
            </button>
            <button
              type="button"
              onClick={() => setShowFlagForm(false)}
              className="text-sm text-zinc-500 underline dark:text-zinc-400"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowFlagForm(true)}
          className="self-start text-sm text-zinc-500 underline dark:text-zinc-400"
        >
          Flag this question
        </button>
      )}
    </fieldset>
  );
}

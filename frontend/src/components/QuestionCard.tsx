"use client";

import { useState } from "react";
import type { AnswerResult, Difficulty, NextQuestion } from "@/services/api";
import FreeTextAnswerInput from "@/components/FreeTextAnswerInput";
import MultiStepAnswerInput from "@/components/MultiStepAnswerInput";
import SelectionReasonChip from "@/components/SelectionReasonChip";
import { canUseReadAloud, speak } from "@/lib/read-aloud";
import { formatTopicId } from "@/lib/format-topic-id";

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
  // Spec 027: opts into the Practice mockup's header (topic title +
  // grade/difficulty pills + selection-reason chip, circular read-aloud/
  // flag icons) -- gated behind this instead of applying unconditionally
  // so Quiz and instructor-assigned-quiz (both out of this redesign's
  // scope, both still rendering the pre-redesign layout) are unaffected.
  variant?: "practice";
  // Rendered inside the card, below everything else, behind a divider --
  // Practice's "ask the Tutor"/primary-submit row (spec 027). Omitted by
  // every other caller.
  footer?: React.ReactNode;
}

const DEFAULT_FLAG_REASON = "Learner flagged this question's answer key as incorrect.";

const DIFFICULTY_DOTS_FILLED: Record<Difficulty, number> = { easy: 1, medium: 2, hard: 3 };

function DifficultyPill({ difficulty }: { difficulty: Difficulty }) {
  const filled = DIFFICULTY_DOTS_FILLED[difficulty];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-primary-subtle px-3 py-0.5 text-[13px] font-extrabold text-heading"
      aria-label={`Difficulty: ${difficulty}`}
    >
      <span className="inline-flex gap-0.5" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`h-2.5 w-1.5 rounded-sm ${i < filled ? "bg-primary" : "bg-border"}`}
          />
        ))}
      </span>
      {difficulty[0].toUpperCase() + difficulty.slice(1)}
    </span>
  );
}

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
  variant,
  footer,
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
  const isPractice = variant === "practice";

  // Practice variant's flag confirmation/reason-form -- the circular flag
  // icon above opens this. The default variant keeps its own original
  // text-link-triggered version inline below, unchanged.
  const flagConfirmation = flagged ? (
    <div
      role="status"
      className="rounded-2xl border border-border bg-surface px-[18px] py-3.5 text-[15px] text-muted"
    >
      <strong className="text-heading">Thanks — flagged for review.</strong> Your instructor
      will take a look. You can keep going or skip this one.
    </div>
  ) : showFlagForm ? (
    <div className="flex flex-col gap-2">
      <input
        type="text"
        placeholder="Why is this question wrong? (optional)"
        className="rounded-[14px] border-2 border-primary/30 px-[14px] py-2 text-sm"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <div className="flex gap-3">
        <button type="button" onClick={handleFlagSubmit} className="text-sm font-bold text-error underline">
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
  ) : null;

  if (isPractice) {
    return (
      <div
        className="flex flex-col gap-[22px] rounded-card border border-border bg-surface p-8"
        data-testid="question-card"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-2.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="font-heading text-xl font-bold text-heading">
                {formatTopicId(question.topic_id)}
              </span>
              {question.grade != null && (
                <span className="rounded-full bg-primary-subtle px-3 py-0.5 text-[13px] font-extrabold text-heading">
                  Grade {question.grade}
                </span>
              )}
              <DifficultyPill difficulty={question.difficulty} />
            </div>
            <SelectionReasonChip question={question} />
          </div>
          <div className="flex gap-2">
            {canReadAloud && (
              <button
                type="button"
                onClick={handleReadAloud}
                aria-label="Read this question aloud"
                data-testid="read-aloud-button"
                className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-primary/30 text-primary"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M11 5 6 9H3v6h3l5 4z" />
                  <path d="M15.5 8.5a5 5 0 0 1 0 7" />
                  <path d="M18.5 5.5a9 9 0 0 1 0 13" />
                </svg>
                <span className="sr-only">{readAloudUsed ? "Replay" : "Read aloud"}</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => !flagged && setShowFlagForm((v) => !v)}
              aria-pressed={flagged}
              aria-label="Flag this question for review"
              disabled={flagged}
              data-testid="flag-button"
              className={`flex h-11 w-11 items-center justify-center rounded-full border-2 ${
                flagged ? "border-warning bg-warning/15 text-warning" : "border-primary/30 text-primary"
              }`}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 21V4" />
                <path d="M5 4h11l-2 4 2 4H5" />
              </svg>
            </button>
          </div>
        </div>

        <fieldset className="flex flex-col gap-[22px]" disabled={disabled}>
          <legend className="font-heading text-[34px] font-bold leading-tight text-heading">
            {question.stem}
          </legend>

          {question.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- see non-practice branch below for why.
            <img
              src={question.image_url}
              alt={question.image_alt_text ?? ""}
              className="max-w-full rounded-[16px] border border-border"
            />
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
              className="rounded-[14px] border-2 border-primary/30 px-[18px] py-3 text-lg"
              value={response}
              onChange={(event) => onResponseChange(event.target.value)}
            />
          )}
        </fieldset>

        {flagConfirmation}

        {footer && <div className="border-t border-border pt-[22px]">{footer}</div>}
      </div>
    );
  }

  return (
    <fieldset
      className="flex flex-col gap-[22px] rounded-card border border-border bg-surface p-8"
      disabled={disabled}
      data-testid="question-card"
    >
      <legend className="font-heading text-[28px] font-bold text-heading">{question.stem}</legend>

      {canReadAloud && (
        <button
          type="button"
          onClick={handleReadAloud}
          className="self-start rounded-full border-2 border-primary/30 px-4 py-2 text-sm font-bold text-primary"
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
            className="max-w-full rounded-[16px] border border-border"
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
          className="rounded-[14px] border-2 border-primary/30 px-[18px] py-3 text-lg"
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

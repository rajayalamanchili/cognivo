"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  skipPlacementQuestion,
  startPlacement,
  submitPlacement,
  type MasteryStateEntry,
  type PlacementQuestion,
  type PlacementQuestionResultEntry,
} from "@/services/api";
import MasteryView from "@/components/MasteryView";
import AnswerResultView from "@/components/AnswerResultView";
import { DifficultyPill } from "@/components/QuestionCard";
import { formatTopicId } from "@/lib/format-topic-id";
import { getExplanationCopyTier } from "@/lib/explainabilityCopy";
import LoadingIndicator from "@/components/LoadingIndicator";
import { canUseReadAloud, speak } from "@/lib/read-aloud";

type Phase = "loading" | "answering" | "submitting" | "results" | "error";

// FR-001: stem + every answer choice, same as QuestionCard's read-aloud
// (research.md Decision 1) -- placement renders its own question UI
// independently of QuestionCard, so this is a small, separate copy
// rather than a shared abstraction over two different question shapes.
function buildReadAloudText(question: PlacementQuestion): string {
  const parts = [question.stem];
  if (question.options) parts.push(...question.options);
  return parts.join(". ");
}

export default function PlacementFlow() {
  const searchParams = useSearchParams();
  const subjectId = searchParams.get("subject") ?? "algebra-1";

  const [phase, setPhase] = useState<Phase>("loading");
  const [placementSessionId, setPlacementSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<PlacementQuestion[]>([]);
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [masteryState, setMasteryState] = useState<MasteryStateEntry[] | null>(null);
  const [perQuestionResults, setPerQuestionResults] = useState<PlacementQuestionResultEntry[]>(
    [],
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [skippingQuestionId, setSkippingQuestionId] = useState<string | null>(null);
  const [skipError, setSkipError] = useState<string | null>(null);
  const [readAloudUsed, setReadAloudUsed] = useState<Record<string, boolean>>({});
  // Spec 027 (Placement mockup-fidelity pass): the intro's progress bar
  // and "Covers Grades X-Y" note need the *original* question count/grade
  // range, which `questions` no longer reflects once a skip removes an
  // entry -- captured once from the initial fetch, zero new data.
  const [totalQuestionCount, setTotalQuestionCount] = useState(0);
  const [gradeRange, setGradeRange] = useState<{ min: number; max: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    startPlacement(subjectId)
      .then((result) => {
        if (cancelled) return;
        setPlacementSessionId(result.placement_session_id);
        setQuestions(result.questions);
        setTotalQuestionCount(result.questions.length);
        const grades = result.questions
          .map((q) => q.grade)
          .filter((grade): grade is number => grade !== null);
        setGradeRange(grades.length > 0 ? { min: Math.min(...grades), max: Math.max(...grades) } : null);
        setPhase("answering");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [subjectId]);

  const allAnswered =
    questions.length > 0 &&
    questions.every(
      (q) => responses[q.question_id] !== undefined && responses[q.question_id] !== "",
    );

  // The backend only allows skipping a question above the learner's
  // current assessed level, which -- since skip always precedes submit
  // in this flow -- is the lowest grade among the questions still shown.
  // Gating the button on that client-side avoids offering a skip that
  // will always 422.
  const lowestShownGrade = questions.reduce<number | null>(
    (min, q) => (q.grade !== null && (min === null || q.grade < min) ? q.grade : min),
    null,
  );

  // Progress bar/label (mockup intro section): answered-so-far among the
  // questions still shown, plus every question already removed by a skip
  // (it can only have left the list by being skipped) -- derived entirely
  // from state already tracked above, no new data.
  const answeredCount = questions.filter(
    (q) => responses[q.question_id] !== undefined && responses[q.question_id] !== "",
  ).length;
  const doneCount = answeredCount + (totalQuestionCount - questions.length);
  const progressPct =
    totalQuestionCount > 0 ? Math.round((doneCount / totalQuestionCount) * 100) : 0;

  async function handleSubmit() {
    if (!placementSessionId || !allAnswered) return;
    setPhase("submitting");
    try {
      const answers = questions.map((question) => {
        const raw = responses[question.question_id];
        return {
          question_id: question.question_id,
          response: question.question_type === "numeric" ? Number(raw) : Number.parseInt(raw, 10),
          read_aloud_used: readAloudUsed[question.question_id] ?? false,
        };
      });
      const result = await submitPlacement(placementSessionId, answers);
      setMasteryState(result.mastery_state);
      setPerQuestionResults(result.per_question_results);
      setPhase("results");
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : String(error),
      );
      setPhase("error");
    }
  }

  async function handleSkip(questionId: string) {
    if (!placementSessionId) return;
    setSkippingQuestionId(questionId);
    setSkipError(null);
    try {
      const result = await skipPlacementQuestion(placementSessionId, questionId);
      setQuestions((prev) =>
        result.replacement_question
          ? prev.map((q) => (q.question_id === questionId ? result.replacement_question! : q))
          : prev.filter((q) => q.question_id !== questionId),
      );
      setResponses((prev) => {
        const next = { ...prev };
        delete next[questionId];
        return next;
      });
    } catch (error) {
      setSkipError(
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : String(error),
      );
    } finally {
      setSkippingQuestionId(null);
    }
  }

  if (phase === "loading") {
    return <LoadingIndicator message="Preparing your first questions…" />;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  if (phase === "results" && masteryState) {
    // Spec 025 FR-011: placement submits (and grades) every question in
    // one batch, unlike practice's single-answer response -- so more
    // than one topic can cross into mastered in the same submit. Same
    // one-shot framing as RefreshedBanner, just naming every topic it
    // applies to instead of assuming exactly one.
    const refreshedTopicIds = perQuestionResults
      .filter((result) => result.refreshed)
      .map((result) => result.topic_id);
    const tier = getExplanationCopyTier(null);

    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8">
        <h1 className="font-heading text-[32px] font-bold text-heading">Placement Results</h1>
        <MasteryView topics={masteryState} />
        {refreshedTopicIds.length > 0 && (
          <p
            data-testid="placement-refreshed-topics"
            className="rounded-[18px] bg-success/15 px-5 py-4 text-[15px] font-bold text-success"
          >
            {tier.refreshedFraming} ({refreshedTopicIds.map(formatTopicId).join(", ")})
          </p>
        )}
        {perQuestionResults.length > 0 && (
          <div className="flex flex-col gap-4" data-testid="placement-per-question-results">
            <p className="text-[15px] font-bold text-heading">How each question was graded</p>
            {perQuestionResults.map((result) => (
              <AnswerResultView key={result.question_id} result={result} />
            ))}
          </div>
        )}
        <div className="flex items-center gap-4">
          <Link
            href={`/practice?subject=${subjectId}`}
            className="rounded-full bg-primary px-7 py-3.5 text-[17px] font-extrabold text-primary-foreground"
          >
            Start Practicing
          </Link>
          <Link href={`/mastery?subject=${subjectId}`} className="text-link underline">
            View full mastery state
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col gap-6 p-8">
      <section className="flex flex-col gap-2.5">
        <span className="text-[13px] font-extrabold uppercase tracking-wide text-link">
          {formatTopicId(subjectId)} · Placement
        </span>
        <h1 className="font-heading text-[40px] font-bold leading-[1.1] text-heading">
          Let&apos;s find your starting point
        </h1>
        <p className="max-w-[640px] text-lg text-muted">
          A few questions so Cognivo can skip what you already know. This isn&apos;t a test — if
          you haven&apos;t learned something yet, just skip it.
        </p>
        <div className="mt-2 flex flex-col gap-1.5">
          {gradeRange && (
            <div className="mb-1.5 flex flex-wrap gap-x-6 gap-y-2.5 rounded-2xl border border-border bg-surface px-4 py-3 text-[15px]">
              <span>
                <strong>
                  Covers Grades {gradeRange.min}–{gradeRange.max}
                </strong>{" "}
                <span className="text-muted">of {formatTopicId(subjectId)}</span>
              </span>
              <span className="text-muted">
                Questions above Grade {gradeRange.min} can be skipped if they feel too hard
              </span>
            </div>
          )}
          <div className="flex justify-between text-sm font-bold text-muted">
            <span>
              {doneCount} of {totalQuestionCount} answered or skipped
            </span>
            <span>About 5 minutes</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-surface-subtle">
            <div
              className="h-full rounded-full bg-primary transition-[width]"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </section>

      {skipError && <p className="text-error">{skipError}</p>}

      {questions.map((question, index) => {
        const headingId = `pq-${question.question_id}`;
        const canSkip =
          question.grade !== null && lowestShownGrade !== null && question.grade > lowestShownGrade;
        return (
          <section
            key={question.question_id}
            aria-labelledby={headingId}
            data-testid="placement-question"
            className="flex flex-col gap-4 rounded-card border border-border bg-surface p-7"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-extrabold text-link">
                    Question {index + 1} · {formatTopicId(question.topic_id)}
                  </span>
                  {question.grade !== null && (
                    <span className="rounded-full bg-surface-subtle px-3 py-0.5 text-xs font-extrabold text-muted">
                      Grade {question.grade}
                    </span>
                  )}
                  <DifficultyPill difficulty={question.difficulty} />
                </div>
                <h2
                  id={headingId}
                  className="font-heading text-[24px] font-semibold leading-snug text-heading"
                >
                  {question.stem}
                </h2>
              </div>
              {question.read_aloud_eligible && canUseReadAloud() && (
                <button
                  type="button"
                  onClick={() => {
                    speak(buildReadAloudText(question));
                    setReadAloudUsed((prev) => ({ ...prev, [question.question_id]: true }));
                  }}
                  aria-label={`Read question ${index + 1} aloud`}
                  data-testid="read-aloud-button"
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-primary/30 text-primary"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M11 5 6 9H3v6h3l5 4z" />
                    <path d="M15.5 8.5a5 5 0 0 1 0 7" />
                    <path d="M18.5 5.5a9 9 0 0 1 0 13" />
                  </svg>
                </button>
              )}
            </div>

            {question.question_type === "multiple_choice" && question.options ? (
              <div role="radiogroup" aria-labelledby={headingId} className="grid gap-2.5 sm:grid-cols-2">
                {question.options.map((option, optionIndex) => {
                  const letter = String.fromCharCode(65 + optionIndex);
                  const checked = responses[question.question_id] === String(optionIndex);
                  return (
                    <button
                      key={optionIndex}
                      type="button"
                      role="radio"
                      aria-checked={checked}
                      onClick={() =>
                        setResponses((prev) => ({
                          ...prev,
                          [question.question_id]: String(optionIndex),
                        }))
                      }
                      className={`flex min-h-[56px] items-center gap-3.5 rounded-2xl border-2 px-4 py-2.5 text-left text-lg font-bold text-heading ${
                        checked ? "border-primary bg-primary-subtle" : "border-border bg-surface"
                      }`}
                    >
                      <span
                        aria-hidden="true"
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[15px] font-extrabold ${
                          checked ? "bg-primary text-primary-foreground" : "bg-surface-subtle text-muted"
                        }`}
                      >
                        {letter}
                      </span>
                      {option}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <label htmlFor={`pq-in-${question.question_id}`} className="font-extrabold text-muted">
                  Your answer
                </label>
                <input
                  id={`pq-in-${question.question_id}`}
                  type="number"
                  step="any"
                  placeholder="e.g. 12"
                  className="min-h-[52px] w-[200px] rounded-[14px] border-2 border-primary/30 px-[18px] text-lg"
                  value={responses[question.question_id] ?? ""}
                  onChange={(event) =>
                    setResponses((prev) => ({
                      ...prev,
                      [question.question_id]: event.target.value,
                    }))
                  }
                />
              </div>
            )}

            {canSkip && (
              <button
                type="button"
                disabled={skippingQuestionId === question.question_id}
                onClick={() => handleSkip(question.question_id)}
                className="self-start text-[15px] font-extrabold text-muted underline disabled:opacity-40"
              >
                {skippingQuestionId === question.question_id
                  ? "Skipping…"
                  : `Too hard? Skip this Grade ${question.grade} question`}
              </button>
            )}
          </section>
        );
      })}

      <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
        <p className="max-w-[460px] text-[15px] text-muted">
          You&apos;ll see which answers were right and where you&apos;re starting, right after you
          finish.
        </p>
        <button
          type="button"
          disabled={!allAnswered || phase === "submitting"}
          onClick={handleSubmit}
          className="inline-flex items-center gap-2.5 rounded-full bg-primary px-7 py-3.5 text-[17px] font-extrabold text-primary-foreground disabled:opacity-40"
        >
          {phase === "submitting" ? (
            <LoadingIndicator message="Figuring out where to start you…" compact />
          ) : (
            <>
              Finish placement
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M5 12h14" />
                <path d="m13 6 6 6-6 6" />
              </svg>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

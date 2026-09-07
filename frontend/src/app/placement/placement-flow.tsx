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
} from "@/services/api";
import MasteryView from "@/components/MasteryView";

type Phase = "loading" | "answering" | "submitting" | "results" | "error";

export default function PlacementFlow() {
  const searchParams = useSearchParams();
  const subjectId = searchParams.get("subject") ?? "algebra-1";

  const [phase, setPhase] = useState<Phase>("loading");
  const [placementSessionId, setPlacementSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<PlacementQuestion[]>([]);
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [masteryState, setMasteryState] = useState<MasteryStateEntry[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [skippingQuestionId, setSkippingQuestionId] = useState<string | null>(null);
  const [skipError, setSkipError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    startPlacement(subjectId)
      .then((result) => {
        if (cancelled) return;
        setPlacementSessionId(result.placement_session_id);
        setQuestions(result.questions);
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

  async function handleSubmit() {
    if (!placementSessionId || !allAnswered) return;
    setPhase("submitting");
    try {
      const answers = questions.map((question) => {
        const raw = responses[question.question_id];
        return {
          question_id: question.question_id,
          response: question.question_type === "numeric" ? Number(raw) : Number.parseInt(raw, 10),
        };
      });
      const result = await submitPlacement(placementSessionId, answers);
      setMasteryState(result.mastery_state);
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
    return <p className="p-8">Loading placement questions&hellip;</p>;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  if (phase === "results" && masteryState) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
        <h1 className="text-2xl font-semibold">Placement Results</h1>
        <MasteryView topics={masteryState} />
        <div className="flex items-center gap-4">
          <Link
            href={`/practice?subject=${subjectId}`}
            className="rounded-lg bg-primary px-5 py-3 text-primary-foreground"
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
    <div className="mx-auto flex max-w-2xl flex-col gap-8 p-8">
      <h1 className="text-2xl font-semibold">Placement Assessment</h1>
      {skipError && <p className="text-error">{skipError}</p>}
      {questions.map((question, index) => (
        <fieldset key={question.question_id} className="flex flex-col gap-3">
          <legend className="font-medium">
            {index + 1}. {question.stem}
            {question.grade !== null && (
              <span className="ml-2 rounded-full bg-muted/10 px-2 py-0.5 text-xs font-normal text-muted">
                Grade {question.grade}
              </span>
            )}
            {question.grade !== null && lowestShownGrade !== null && question.grade > lowestShownGrade && (
              <button
                type="button"
                disabled={skippingQuestionId === question.question_id}
                onClick={() => handleSkip(question.question_id)}
                className="ml-2 text-xs font-normal text-link underline disabled:opacity-40"
              >
                {skippingQuestionId === question.question_id ? "Skipping…" : "Skip (too hard)"}
              </button>
            )}
          </legend>
          {question.question_type === "multiple_choice" && question.options ? (
            <div className="flex flex-col gap-2">
              {question.options.map((option, optionIndex) => (
                <label key={optionIndex} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name={question.question_id}
                    value={optionIndex}
                    checked={responses[question.question_id] === String(optionIndex)}
                    onChange={() =>
                      setResponses((prev) => ({
                        ...prev,
                        [question.question_id]: String(optionIndex),
                      }))
                    }
                  />
                  {option}
                </label>
              ))}
            </div>
          ) : (
            <input
              type="number"
              step="any"
              className="rounded-lg border border-border px-3 py-2"
              value={responses[question.question_id] ?? ""}
              onChange={(event) =>
                setResponses((prev) => ({
                  ...prev,
                  [question.question_id]: event.target.value,
                }))
              }
            />
          )}
        </fieldset>
      ))}
      <button
        type="button"
        disabled={!allAnswered || phase === "submitting"}
        onClick={handleSubmit}
        className="rounded-lg bg-primary px-5 py-3 text-primary-foreground disabled:opacity-40"
      >
        {phase === "submitting" ? "Submitting…" : "Submit Placement"}
      </button>
    </div>
  );
}

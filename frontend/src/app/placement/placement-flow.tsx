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
      <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
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
    <div className="mx-auto flex max-w-2xl flex-col gap-8 p-8">
      <h1 className="font-heading text-[32px] font-bold text-heading">Placement Assessment</h1>
      {skipError && <p className="text-error">{skipError}</p>}
      {questions.map((question, index) => (
        <fieldset
          key={question.question_id}
          className="flex flex-col gap-4 rounded-card border border-border bg-surface p-7"
        >
          <legend className="font-heading text-[24px] font-semibold leading-snug text-heading">
            {index + 1}. {question.stem}
            {question.grade !== null && (
              <span className="ml-2 rounded-full bg-surface-subtle px-3 py-0.5 text-xs font-extrabold text-muted">
                Grade {question.grade}
              </span>
            )}
            {question.grade !== null &&
              lowestShownGrade !== null &&
              question.grade > lowestShownGrade && (
                <button
                  type="button"
                  disabled={skippingQuestionId === question.question_id}
                  onClick={() => handleSkip(question.question_id)}
                  className="ml-2 text-xs font-bold text-muted underline disabled:opacity-40"
                >
                  {skippingQuestionId === question.question_id ? "Skipping…" : "Skip (too hard)"}
                </button>
              )}
          </legend>
          {question.read_aloud_eligible && canUseReadAloud() && (
            <button
              type="button"
              onClick={() => {
                speak(buildReadAloudText(question));
                setReadAloudUsed((prev) => ({ ...prev, [question.question_id]: true }));
              }}
              className="self-start rounded-full border-2 border-primary/30 px-4 py-2 text-sm font-bold text-primary"
              data-testid="read-aloud-button"
            >
              🔊 Read aloud
            </button>
          )}
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
              className="rounded-[14px] border-2 border-primary/30 px-[18px] py-3 text-lg"
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
        className="rounded-full bg-primary px-7 py-3.5 text-[17px] font-extrabold text-primary-foreground disabled:opacity-40"
      >
        {phase === "submitting" ? (
          <LoadingIndicator message="Figuring out where to start you…" compact />
        ) : (
          "Submit Placement"
        )}
      </button>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  answerQuestion,
  flagQuestion,
  getDemoLearner,
  getNextQuestion,
  type AnswerResult,
  type NextQuestion,
} from "@/services/api";
import QuestionCard from "@/components/QuestionCard";
import AnswerResultView from "@/components/AnswerResultView";

type Phase = "loading" | "answering" | "submitting" | "result" | "error";

export default function PracticeFlow() {
  const searchParams = useSearchParams();
  const subjectId = searchParams.get("subject") ?? "algebra-1";

  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [question, setQuestion] = useState<NextQuestion | null>(null);
  const [response, setResponse] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [flagged, setFlagged] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadNextQuestion = useCallback(
    (currentLearnerId: string) => {
      setPhase("loading");
      setResponse("");
      setResult(null);
      setFlagged(false);
      getNextQuestion(currentLearnerId, subjectId)
        .then((nextQuestion) => {
          setQuestion(nextQuestion);
          setPhase("answering");
        })
        .catch((error: unknown) => {
          setErrorMessage(error instanceof Error ? error.message : String(error));
          setPhase("error");
        });
    },
    [subjectId],
  );

  useEffect(() => {
    let cancelled = false;
    getDemoLearner()
      .then((learner) => {
        if (cancelled) return;
        setLearnerId(learner.learner_id);
        loadNextQuestion(learner.learner_id);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [loadNextQuestion]);

  async function handleSubmit() {
    if (!question || response === "") return;
    setPhase("submitting");
    try {
      const value =
        question.question_type === "numeric" ? Number(response) : Number.parseInt(response, 10);
      const answer = await answerQuestion(question.question_id, value);
      setResult(answer);
      setPhase("result");
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

  function handleFreeTextGraded(answer: AnswerResult) {
    setResult(answer);
    setPhase("result");
  }

  async function handleFlag(reason: string) {
    if (!question || !learnerId) return;
    try {
      await flagQuestion(question.question_id, learnerId, reason);
      setFlagged(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  if (phase === "loading") {
    return <p className="p-8">Loading next question&hellip;</p>;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  if (phase === "result" && result) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
        <AnswerResultView result={result} />
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => learnerId && loadNextQuestion(learnerId)}
            className="rounded-lg bg-primary px-5 py-3 text-primary-foreground"
          >
            Next question
          </button>
          <Link href={`/mastery?subject=${subjectId}`} className="text-link underline">
            View mastery state
          </Link>
        </div>
      </div>
    );
  }

  if (!question) return null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 p-8">
      <h1 className="text-2xl font-semibold">Practice</h1>
      <QuestionCard
        question={question}
        response={response}
        onResponseChange={setResponse}
        onFlag={handleFlag}
        flagged={flagged}
        disabled={phase === "submitting"}
        onFreeTextGraded={handleFreeTextGraded}
      />
      {question.question_type !== "free_text" && (
        <button
          type="button"
          disabled={response === "" || phase === "submitting"}
          onClick={handleSubmit}
          className="rounded-lg bg-primary px-5 py-3 text-primary-foreground disabled:opacity-40"
        >
          {phase === "submitting" ? "Submitting…" : "Submit Answer"}
        </button>
      )}
    </div>
  );
}

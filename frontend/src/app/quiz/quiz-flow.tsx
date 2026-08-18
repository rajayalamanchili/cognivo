"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  answerQuestion,
  flagQuestion,
  getDemoLearner,
  getMasteryState,
  getQuizNextQuestion,
  getQuizSummary,
  getSubjects,
  startQuiz,
  type MasteryTopicEntry,
  type NextQuestion,
  type QuizSummaryResponse,
  type SubjectSummary,
} from "@/services/api";
import QuestionCard from "@/components/QuestionCard";
import QuizSummary from "@/components/QuizSummary";
import { formatTopicId } from "@/lib/format-topic-id";

type Phase = "loading" | "start" | "starting" | "answering" | "submitting" | "finished" | "error";

const DEFAULT_QUESTION_COUNT = 5;

export default function QuizFlow() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [topics, setTopics] = useState<MasteryTopicEntry[]>([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([]);
  const [questionCount, setQuestionCount] = useState(DEFAULT_QUESTION_COUNT);

  const [quizSessionId, setQuizSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<NextQuestion | null>(null);
  const [response, setResponse] = useState("");
  const [flagged, setFlagged] = useState(false);
  const [summary, setSummary] = useState<QuizSummaryResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoLearner()
      .then((learner) => {
        if (cancelled) return undefined;
        setLearnerId(learner.learner_id);
        return getSubjects();
      })
      .then((subjectsResponse) => {
        if (cancelled || !subjectsResponse) return;
        setSubjects(subjectsResponse.subjects);
        setSelectedSubjectId(subjectsResponse.subjects[0]?.subject_id ?? null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!learnerId || !selectedSubjectId) return;
    let cancelled = false;
    getMasteryState(learnerId, selectedSubjectId)
      .then((result) => {
        if (cancelled) return;
        setTopics(result.topics);
        setSelectedTopicIds([]);
        setPhase("start");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, selectedSubjectId]);

  function toggleTopic(topicId: string) {
    setSelectedTopicIds((current) =>
      current.includes(topicId)
        ? current.filter((id) => id !== topicId)
        : [...current, topicId],
    );
  }

  async function goToSummary(sessionId: string) {
    const result = await getQuizSummary(sessionId);
    setSummary(result);
    setPhase("finished");
  }

  async function handleStart() {
    if (selectedTopicIds.length === 0) return;
    setPhase("starting");
    try {
      const result = await startQuiz(selectedTopicIds, questionCount);
      setQuizSessionId(result.quiz_session_id);
      if (result.status === "in_progress" && result.question) {
        setCurrentQuestion(result.question);
        setPhase("answering");
      } else {
        await goToSummary(result.quiz_session_id);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  async function advanceToNextQuestion(sessionId: string) {
    try {
      const next = await getQuizNextQuestion(sessionId);
      if (next.status === "in_progress" && next.question) {
        setCurrentQuestion(next.question);
        setFlagged(false);
        setPhase("answering");
      } else {
        await goToSummary(sessionId);
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await goToSummary(sessionId);
        return;
      }
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  async function handleSubmitAnswer() {
    if (!currentQuestion || !quizSessionId || response === "") return;
    setPhase("submitting");
    try {
      const value =
        currentQuestion.question_type === "numeric"
          ? Number(response)
          : Number.parseInt(response, 10);
      await answerQuestion(currentQuestion.question_id, value);
      setResponse("");
      await advanceToNextQuestion(quizSessionId);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  async function handleFlag(reason: string) {
    if (!currentQuestion || !learnerId) return;
    try {
      await flagQuestion(currentQuestion.question_id, learnerId, reason);
      setFlagged(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  if (phase === "loading") {
    return <p className="p-8">Loading&hellip;</p>;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-red-600">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  if (phase === "finished" && summary) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
        <QuizSummary summary={summary} />
      </div>
    );
  }

  if (phase === "answering" || phase === "submitting") {
    if (!currentQuestion) return null;
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-8 p-8">
        <h1 className="text-2xl font-semibold">Quiz</h1>
        <QuestionCard
          question={currentQuestion}
          response={response}
          onResponseChange={setResponse}
          onFlag={handleFlag}
          flagged={flagged}
          disabled={phase === "submitting"}
        />
        <button
          type="button"
          disabled={response === "" || phase === "submitting"}
          onClick={handleSubmitAnswer}
          className="rounded bg-foreground px-5 py-3 text-background disabled:opacity-40"
        >
          {phase === "submitting" ? "Submitting…" : "Submit Answer"}
        </button>
      </div>
    );
  }

  return (
    <div
      className="mx-auto flex max-w-2xl flex-col gap-6 p-8"
      data-testid="quiz-start-form"
    >
      <h1 className="text-2xl font-semibold">Start a Quiz</h1>
      {subjects.length > 1 && (
        <label className="flex flex-col gap-1">
          Subject
          <select
            value={selectedSubjectId ?? ""}
            onChange={(event) => setSelectedSubjectId(event.target.value)}
            className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
          >
            {subjects.map((subject) => (
              <option key={subject.subject_id} value={subject.subject_id}>
                {subject.display_name}
              </option>
            ))}
          </select>
        </label>
      )}
      <fieldset className="flex flex-col gap-2">
        <legend className="font-medium">Topics</legend>
        {topics.map((topic) => (
          <label key={topic.topic_id} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selectedTopicIds.includes(topic.topic_id)}
              onChange={() => toggleTopic(topic.topic_id)}
            />
            {formatTopicId(topic.topic_id)}
          </label>
        ))}
      </fieldset>
      <label className="flex flex-col gap-1">
        Question count
        <input
          type="number"
          min={1}
          max={50}
          value={questionCount}
          onChange={(event) => setQuestionCount(Number(event.target.value))}
          className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
        />
      </label>
      <button
        type="button"
        disabled={selectedTopicIds.length === 0 || phase === "starting"}
        onClick={handleStart}
        className="rounded bg-foreground px-5 py-3 text-background disabled:opacity-40"
      >
        {phase === "starting" ? "Starting…" : "Start Quiz"}
      </button>
    </div>
  );
}

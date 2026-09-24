"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  answerQuestion,
  endQuiz,
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
import LoadingIndicator from "@/components/LoadingIndicator";
import SessionCountdown from "@/components/SessionCountdown";
import { formatTopicId } from "@/lib/format-topic-id";
import { getPacingProfile } from "@/lib/pacing";
import { TIME_LIMIT_OPTIONS } from "@/lib/time-limit-options";

type Phase =
  | "loading"
  | "start"
  | "starting"
  | "answering"
  | "submitting"
  | "stopping-point"
  | "finished"
  | "error";

const DEFAULT_QUESTION_COUNT = 5;

// FR-009's "more frequent positive reinforcement for younger bands" --
// a brief, non-blocking encouragement shown above the next question
// every `reinforcementEveryN` answered questions, distinct from (and
// suppressed by) the end-of-recommended-length stopping point itself.
const REINFORCEMENT_MESSAGE = "Nice work! Keep it up! ⭐";

export default function QuizFlow() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [topics, setTopics] = useState<MasteryTopicEntry[]>([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([]);
  const [questionCount, setQuestionCount] = useState(DEFAULT_QUESTION_COUNT);
  const [timeLimitSeconds, setTimeLimitSeconds] = useState<number | null>(null);

  const [quizSessionId, setQuizSessionId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<NextQuestion | null>(null);
  const [response, setResponse] = useState("");
  const [flagged, setFlagged] = useState(false);
  const [readAloudUsed, setReadAloudUsed] = useState(false);
  const [summary, setSummary] = useState<QuizSummaryResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Session pacing (spec 019 FR-009, research.md Decision 6) -- a soft,
  // dismissible checkpoint only; the quiz itself is never ended by
  // reaching it (Acceptance Scenario 1).
  const [answeredCount, setAnsweredCount] = useState(0);
  const [stoppingPointShown, setStoppingPointShown] = useState(false);
  const [reinforcementMessage, setReinforcementMessage] = useState<string | null>(null);

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
      current.includes(topicId) ? current.filter((id) => id !== topicId) : [...current, topicId],
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
      const result = await startQuiz(selectedTopicIds, questionCount, timeLimitSeconds);
      setQuizSessionId(result.quiz_session_id);
      setExpiresAt(result.expires_at ?? null);
      setAnsweredCount(0);
      setStoppingPointShown(false);
      setReinforcementMessage(null);
      if (result.status === "in_progress" && result.question) {
        setCurrentQuestion(result.question);
        setReadAloudUsed(false);
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
      setExpiresAt(next.expires_at ?? null);
      if (next.status === "in_progress" && next.question) {
        setCurrentQuestion(next.question);
        setFlagged(false);
        setReadAloudUsed(false);
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

  // Spec 022 FR-010: a new "end now" action, timed quizzes only.
  async function handleEndQuizNow() {
    if (!quizSessionId) return;
    try {
      await endQuiz(quizSessionId);
      await goToSummary(quizSessionId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await goToSummary(quizSessionId);
        return;
      }
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  // Spec 022 FR-003: the countdown reaching zero doesn't itself end the
  // session -- it just triggers the same request the learner's next
  // action would have, and the server's own lazy expiry check (already
  // wired into next-question/answer) does the real work.
  function handleCountdownExpire() {
    if (!quizSessionId) return;
    void advanceToNextQuestion(quizSessionId);
  }

  // spec 019 FR-009: called after every answered question (both the
  // MC/numeric path below and free-text/multi-step's own submission),
  // before fetching the next question -- so a reached stopping point
  // shows the checkpoint instead of an unnecessary extra fetch.
  async function advanceAfterAnswer(sessionId: string, unlockedGrade: number | null) {
    const newCount = answeredCount + 1;
    setAnsweredCount(newCount);
    const profile = getPacingProfile(unlockedGrade);
    if (!stoppingPointShown && newCount >= profile.recommendedQuestionCount) {
      setStoppingPointShown(true);
      setReinforcementMessage(null);
      setPhase("stopping-point");
      return;
    }
    setReinforcementMessage(
      newCount % profile.reinforcementEveryN === 0 ? REINFORCEMENT_MESSAGE : null,
    );
    await advanceToNextQuestion(sessionId);
  }

  async function handleContinueFromStoppingPoint() {
    if (!quizSessionId) return;
    await advanceToNextQuestion(quizSessionId);
  }

  async function handleSubmitAnswer() {
    if (!currentQuestion || !quizSessionId || response === "") return;
    setPhase("submitting");
    try {
      const value =
        currentQuestion.question_type === "numeric"
          ? Number(response)
          : Number.parseInt(response, 10);
      await answerQuestion(currentQuestion.question_id, value, readAloudUsed);
      setResponse("");
      await advanceAfterAnswer(quizSessionId, currentQuestion.unlocked_grade);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await goToSummary(quizSessionId);
        return;
      }
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  async function handleFreeTextGraded() {
    if (!quizSessionId || !currentQuestion) return;
    setResponse("");
    await advanceAfterAnswer(quizSessionId, currentQuestion.unlocked_grade);
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
    return <LoadingIndicator message="Getting ready…" />;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
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

  if (phase === "stopping-point") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8" data-testid="quiz-stopping-point">
        <h1 className="text-2xl font-semibold">Great work! 🎉</h1>
        <p>You&apos;ve answered {answeredCount} questions -- that&apos;s a nice stopping point.</p>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={handleContinueFromStoppingPoint}
            className="rounded-lg bg-primary px-5 py-3 text-primary-foreground"
          >
            Keep going
          </button>
          <Link
            href={selectedSubjectId ? `/mastery?subject=${selectedSubjectId}` : "/mastery"}
            className="text-link underline"
          >
            I&apos;m done for now
          </Link>
        </div>
      </div>
    );
  }

  if (phase === "answering" || phase === "submitting") {
    if (!currentQuestion) return null;
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-8 p-8">
        <h1 className="text-2xl font-semibold">Quiz</h1>
        {expiresAt && (
          <div className="flex items-center justify-between gap-4">
            <SessionCountdown expiresAt={expiresAt} onExpire={handleCountdownExpire} />
            <button
              type="button"
              onClick={handleEndQuizNow}
              className="text-sm text-link underline"
            >
              End quiz now
            </button>
          </div>
        )}
        {reinforcementMessage && (
          <p
            data-testid="reinforcement-message"
            className="font-heading text-primary"
            aria-live="polite"
          >
            {reinforcementMessage}
          </p>
        )}
        <QuestionCard
          key={currentQuestion.question_id}
          question={currentQuestion}
          response={response}
          onResponseChange={setResponse}
          onFlag={handleFlag}
          flagged={flagged}
          disabled={phase === "submitting"}
          onFreeTextGraded={handleFreeTextGraded}
          readAloudEnabled={currentQuestion.read_aloud_eligible}
          onReadAloudUsed={() => setReadAloudUsed(true)}
        />
        {currentQuestion.question_type !== "free_text" &&
          currentQuestion.question_type !== "multi_step" && (
            <button
              type="button"
              disabled={response === "" || phase === "submitting"}
              onClick={handleSubmitAnswer}
              className="rounded-lg bg-primary px-5 py-3 text-primary-foreground disabled:opacity-40"
            >
              {phase === "submitting" ? (
                <LoadingIndicator message="Checking your answer…" compact />
              ) : (
                "Submit Answer"
              )}
            </button>
          )}
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8" data-testid="quiz-start-form">
      <h1 className="text-2xl font-semibold">Start a Quiz</h1>
      {subjects.length > 1 && (
        <label className="flex flex-col gap-1">
          Subject
          <select
            value={selectedSubjectId ?? ""}
            onChange={(event) => setSelectedSubjectId(event.target.value)}
            className="rounded-lg border border-border px-3 py-2"
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
          className="rounded-lg border border-border px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1">
        Time limit
        <select
          value={timeLimitSeconds ?? ""}
          onChange={(event) =>
            setTimeLimitSeconds(event.target.value === "" ? null : Number(event.target.value))
          }
          className="rounded-lg border border-border px-3 py-2"
        >
          {TIME_LIMIT_OPTIONS.map((option) => (
            <option key={option.label} value={option.seconds ?? ""}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        disabled={selectedTopicIds.length === 0 || phase === "starting"}
        onClick={handleStart}
        className="rounded-lg bg-primary px-5 py-3 text-primary-foreground disabled:opacity-40"
      >
        {phase === "starting" ? (
          <LoadingIndicator message="Building your quiz…" compact />
        ) : (
          "Start Quiz"
        )}
      </button>
    </div>
  );
}

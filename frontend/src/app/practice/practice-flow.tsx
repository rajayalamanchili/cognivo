"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  answerQuestion,
  endPracticeSession,
  flagQuestion,
  getDemoLearner,
  getNextQuestion,
  getPracticeNextQuestion,
  getPracticeSessionSummary,
  getSubjects,
  startPracticeSession,
  type AnswerResult,
  type NextQuestion,
  type PracticeSessionSummaryResponse,
  type SubjectSummary,
} from "@/services/api";
import QuestionCard from "@/components/QuestionCard";
import AnswerResultView from "@/components/AnswerResultView";
import LoadingIndicator from "@/components/LoadingIndicator";
import SessionCountdown from "@/components/SessionCountdown";
import SessionTimingSummary from "@/components/SessionTimingSummary";
import { TIME_LIMIT_OPTIONS } from "@/lib/time-limit-options";

type Phase =
  | "loading"
  | "start"
  | "starting"
  | "answering"
  | "submitting"
  | "result"
  | "ended"
  | "error";

export default function PracticeFlow() {
  const searchParams = useSearchParams();
  const urlSubjectId = searchParams.get("subject");

  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [timeLimitSeconds, setTimeLimitSeconds] = useState<number | null>(null);

  // Spec 022: a timed practice session, when active. `null` = ordinary
  // untimed practice, identical to before this feature (FR-009).
  const [practiceSessionId, setPracticeSessionId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [endedSummary, setEndedSummary] = useState<PracticeSessionSummaryResponse | null>(null);

  const [question, setQuestion] = useState<NextQuestion | null>(null);
  const [response, setResponse] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [flagged, setFlagged] = useState(false);
  const [readAloudUsed, setReadAloudUsed] = useState(false);
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
        setSelectedSubjectId(urlSubjectId ?? subjectsResponse.subjects[0]?.subject_id ?? null);
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
  }, [urlSubjectId]);

  const loadUntimedQuestion = useCallback((currentLearnerId: string, subjectId: string) => {
    setPhase("loading");
    setResponse("");
    setResult(null);
    setFlagged(false);
    setReadAloudUsed(false);
    getNextQuestion(currentLearnerId, subjectId)
      .then((nextQuestion) => {
        setQuestion(nextQuestion);
        setPhase("answering");
      })
      .catch((error: unknown) => {
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      });
  }, []);

  async function handleStart() {
    if (!learnerId || !selectedSubjectId) return;
    setResponse("");
    setResult(null);
    setFlagged(false);
    setReadAloudUsed(false);
    if (timeLimitSeconds === null) {
      loadUntimedQuestion(learnerId, selectedSubjectId);
      return;
    }
    setPhase("starting");
    try {
      const started = await startPracticeSession(learnerId, selectedSubjectId, timeLimitSeconds);
      setPracticeSessionId(started.practice_session_id);
      setExpiresAt(started.expires_at);
      setQuestion(started.question);
      setPhase("answering");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  // Spec 022 SC-005: fetches the session summary (time limit, time
  // used, end reason) before showing the ended screen, so a learner
  // can see how the timed session actually went.
  async function goToEnded(sessionId: string) {
    try {
      const summary = await getPracticeSessionSummary(sessionId);
      setEndedSummary(summary);
    } catch {
      setEndedSummary(null);
    }
    setPhase("ended");
  }

  async function advanceToNextQuestion() {
    if (practiceSessionId) {
      setResponse("");
      setResult(null);
      setFlagged(false);
      setReadAloudUsed(false);
      try {
        const next = await getPracticeNextQuestion(practiceSessionId);
        setExpiresAt(next.expires_at ?? null);
        if (next.status === "in_progress" && next.question) {
          setQuestion(next.question);
          setPhase("answering");
        } else {
          await goToEnded(practiceSessionId);
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          await goToEnded(practiceSessionId);
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      }
      return;
    }
    if (learnerId && selectedSubjectId) {
      loadUntimedQuestion(learnerId, selectedSubjectId);
    }
  }

  // Spec 022 FR-003: the countdown reaching zero just triggers the same
  // request the learner's next action would have -- the server's own
  // lazy expiry check does the real work.
  function handleCountdownExpire() {
    void advanceToNextQuestion();
  }

  async function handleEndPracticeNow() {
    if (!practiceSessionId) return;
    try {
      await endPracticeSession(practiceSessionId);
      await goToEnded(practiceSessionId);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  function handleStartOver() {
    setPracticeSessionId(null);
    setExpiresAt(null);
    setEndedSummary(null);
    setQuestion(null);
    setPhase("start");
  }

  async function handleSubmit() {
    if (!question || response === "") return;
    setPhase("submitting");
    try {
      const value =
        question.question_type === "numeric" ? Number(response) : Number.parseInt(response, 10);
      const answer = await answerQuestion(question.question_id, value, readAloudUsed);
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

  if (phase === "loading" || phase === "starting") {
    return (
      <LoadingIndicator
        message={phase === "starting" ? "Setting up your timed session…" : "Finding your next question…"}
      />
    );
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  if (phase === "ended") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8" data-testid="practice-ended">
        <h1 className="text-2xl font-semibold">Practice session ended</h1>
        {endedSummary && (
          <>
            <p className="text-lg">
              Score: <strong>{endedSummary.score.correct}</strong> / {endedSummary.score.total}
            </p>
            <SessionTimingSummary
              timeLimitSeconds={endedSummary.time_limit_seconds}
              elapsedSeconds={endedSummary.elapsed_seconds}
              endReason={endedSummary.end_reason}
            />
          </>
        )}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={handleStartOver}
            className="rounded-lg bg-primary px-5 py-3 text-primary-foreground"
          >
            Practice again
          </button>
          {selectedSubjectId && (
            <Link href={`/mastery?subject=${selectedSubjectId}`} className="text-link underline">
              View mastery state
            </Link>
          )}
        </div>
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
            onClick={() => void advanceToNextQuestion()}
            className="rounded-lg bg-primary px-5 py-3 text-primary-foreground"
          >
            Next question
          </button>
          {selectedSubjectId && (
            <Link href={`/mastery?subject=${selectedSubjectId}`} className="text-link underline">
              View mastery state
            </Link>
          )}
        </div>
      </div>
    );
  }

  if (phase === "answering" || phase === "submitting") {
    if (!question) return null;
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-8 p-8">
        <h1 className="text-2xl font-semibold">Practice</h1>
        {expiresAt && (
          <div className="flex items-center justify-between gap-4">
            <SessionCountdown expiresAt={expiresAt} onExpire={handleCountdownExpire} />
            <button
              type="button"
              onClick={handleEndPracticeNow}
              className="text-sm text-link underline"
            >
              End practice now
            </button>
          </div>
        )}
        <QuestionCard
          key={question.question_id}
          question={question}
          response={response}
          onResponseChange={setResponse}
          onFlag={handleFlag}
          flagged={flagged}
          disabled={phase === "submitting"}
          onFreeTextGraded={handleFreeTextGraded}
          readAloudEnabled={question.read_aloud_eligible}
          onReadAloudUsed={() => setReadAloudUsed(true)}
        />
        {question.question_type !== "free_text" && question.question_type !== "multi_step" && (
          <button
            type="button"
            disabled={response === "" || phase === "submitting"}
            onClick={handleSubmit}
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

  // phase === "start"
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8" data-testid="practice-start-form">
      <h1 className="text-2xl font-semibold">Practice</h1>
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
        disabled={!selectedSubjectId}
        onClick={handleStart}
        className="rounded-lg bg-primary px-5 py-3 text-primary-foreground disabled:opacity-40"
      >
        {timeLimitSeconds === null ? "Start practicing" : "Start timed practice"}
      </button>
    </div>
  );
}

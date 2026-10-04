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
  isAlreadyAnsweredError,
  startPracticeSession,
  type AnswerResult,
  type NextQuestion,
  type PracticeSessionSummaryResponse,
  type SubjectSummary,
} from "@/services/api";
import QuestionCard from "@/components/QuestionCard";
import AnswerResultView from "@/components/AnswerResultView";
import RefreshedBanner from "@/components/RefreshedBanner";
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
  // Spec 027: the mockup's "Question N this session" caption -- a plain
  // client-side counter of questions shown since the session last
  // (re)started, not fetched/persisted data (no endpoint reports this).
  const [questionNumber, setQuestionNumber] = useState(0);
  const [response, setResponse] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [flagged, setFlagged] = useState(false);
  const [readAloudUsed, setReadAloudUsed] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // PR feedback: free_text/multi_step submit themselves, so `phase` alone
  // doesn't cover their grading call being in flight -- tracked separately
  // so the countdown-expiry/end-now guards below see it too.
  const [answerBusy, setAnswerBusy] = useState(false);

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
        setQuestionNumber((n) => n + 1);
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
    setQuestionNumber(0);
    if (timeLimitSeconds === null) {
      loadUntimedQuestion(learnerId, selectedSubjectId);
      return;
    }
    setPhase("starting");
    try {
      const started = await startPracticeSession(selectedSubjectId, timeLimitSeconds);
      setPracticeSessionId(started.practice_session_id);
      setExpiresAt(started.expires_at);
      setQuestion(started.question);
      setQuestionNumber((n) => n + 1);
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
          setQuestionNumber((n) => n + 1);
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
    // PR feedback: skip while a submit is already in flight -- otherwise
    // this fires a concurrent next-question fetch while handleSubmit's
    // own answerQuestion call is still pending for the same session,
    // racing which one lands first. `answerBusy` covers free_text/
    // multi_step, whose grading call doesn't move `phase`.
    if (phase !== "answering" || answerBusy) return;
    void advanceToNextQuestion();
  }

  async function handleEndPracticeNow() {
    // Same guard as handleCountdownExpire above.
    if (!practiceSessionId || phase !== "answering" || answerBusy) return;
    try {
      await endPracticeSession(practiceSessionId);
      await goToEnded(practiceSessionId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await goToEnded(practiceSessionId);
        return;
      }
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  function handleStartOver() {
    setPracticeSessionId(null);
    setExpiresAt(null);
    setEndedSummary(null);
    setQuestion(null);
    setQuestionNumber(0);
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
      // PR feedback: a duplicate-submit 409 isn't a session-ended 409 --
      // no-op, the original request's own resolution above already
      // carries the UI forward.
      if (isAlreadyAnsweredError(error)) return;
      if (practiceSessionId && error instanceof ApiError && error.status === 409) {
        await goToEnded(practiceSessionId);
        return;
      }
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
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8" data-testid="practice-ended">
        <h1 className="font-heading text-[32px] font-bold text-heading">Practice session ended</h1>
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
            className="rounded-full bg-primary px-7 py-3.5 text-[17px] font-extrabold text-primary-foreground"
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
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8">
        <AnswerResultView
          result={result}
          actions={
            <>
              <button
                type="button"
                onClick={() => void advanceToNextQuestion()}
                className="inline-flex min-h-[48px] w-full items-center justify-center rounded-full bg-primary px-7 text-[17px] font-extrabold text-primary-foreground"
              >
                Next question
              </button>
              <Link
                href="/tutor"
                className="inline-flex min-h-[48px] w-full items-center justify-center rounded-full border-2 border-primary/30 px-7 text-[16px] font-extrabold text-primary"
              >
                Talk it through with the AI Tutor
              </Link>
              {selectedSubjectId && (
                <Link
                  href={`/mastery?subject=${selectedSubjectId}`}
                  className="text-center text-sm text-link underline"
                >
                  View mastery state
                </Link>
              )}
            </>
          }
        />
        <RefreshedBanner refreshed={result.refreshed} unlockedGrade={question?.unlocked_grade ?? null} />
        <div className="flex justify-center">
          {flagged ? (
            <p className="text-sm text-muted">Flagged for review -- thanks for the report.</p>
          ) : (
            <button
              type="button"
              onClick={() => void handleFlag("Learner flagged this answer's grading as incorrect.")}
              className="min-h-[44px] text-[15px] font-bold text-muted underline"
            >
              Think this was graded wrong? Flag it for your instructor
            </button>
          )}
        </div>
      </div>
    );
  }

  if (phase === "answering" || phase === "submitting") {
    if (!question) return null;
    const subjectName = subjects.find((s) => s.subject_id === selectedSubjectId)?.display_name;
    const ownsSubmit =
      question.question_type !== "free_text" && question.question_type !== "multi_step";
    return (
      <div className="mx-auto flex w-full max-w-[860px] flex-col gap-5 p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            {subjectName && (
              <span className="text-[13px] font-extrabold uppercase tracking-wide text-primary">
                {subjectName} · Practice
              </span>
            )}
            {question.unlocked_grade != null && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3.5 py-1 text-sm font-bold text-heading">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="5" y="11" width="14" height="10" rx="2" />
                  <path d="M8 11V7a4 4 0 0 1 8 0" />
                </svg>
                Unlocked up to Grade {question.unlocked_grade}
              </span>
            )}
            {expiresAt && <SessionCountdown expiresAt={expiresAt} onExpire={handleCountdownExpire} />}
          </div>
          {practiceSessionId ? (
            <button
              type="button"
              disabled={phase === "submitting" || answerBusy}
              onClick={handleEndPracticeNow}
              className="text-[15px] font-extrabold text-link disabled:opacity-40"
            >
              End practice now
            </button>
          ) : (
            <Link href="/dashboard" className="text-[15px] font-extrabold text-link">
              End session
            </Link>
          )}
        </div>

        <QuestionCard
          key={question.question_id}
          variant="practice"
          question={question}
          response={response}
          onResponseChange={setResponse}
          onFlag={handleFlag}
          flagged={flagged}
          disabled={phase === "submitting"}
          onFreeTextGraded={handleFreeTextGraded}
          onSessionEnded={
            practiceSessionId ? () => void goToEnded(practiceSessionId) : undefined
          }
          onBusyChange={setAnswerBusy}
          readAloudEnabled={question.read_aloud_eligible}
          onReadAloudUsed={() => setReadAloudUsed(true)}
          footer={
            <div className="flex flex-wrap items-center justify-between gap-4">
              <Link href="/tutor" className="text-[15px] font-extrabold text-link">
                Stuck? Ask the AI Tutor for a hint
              </Link>
              {ownsSubmit && (
                <button
                  type="button"
                  disabled={response === "" || phase === "submitting"}
                  onClick={handleSubmit}
                  className="inline-flex items-center gap-2.5 rounded-full bg-primary px-7 py-3.5 text-[17px] font-extrabold text-primary-foreground disabled:opacity-40"
                >
                  {phase === "submitting" ? (
                    <LoadingIndicator message="Checking your answer…" compact />
                  ) : (
                    <>
                      Submit Answer
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M5 12h14" />
                        <path d="m13 6 6 6-6 6" />
                      </svg>
                    </>
                  )}
                </button>
              )}
            </div>
          }
        />
        <p className="text-center text-sm text-muted">
          Question {questionNumber} this session · Your answer updates your mastery for this topic
        </p>
      </div>
    );
  }

  // phase === "start"
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8" data-testid="practice-start-form">
      <h1 className="font-heading text-[32px] font-bold text-heading">Practice</h1>
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
        className="rounded-full bg-primary px-7 py-3.5 text-[17px] font-extrabold text-primary-foreground disabled:opacity-40"
      >
        {timeLimitSeconds === null ? "Start practicing" : "Start timed practice"}
      </button>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  answerQuestion,
  flagQuestion,
  getQuizNextQuestion,
  getQuizSummary,
  listLearnerAssignments,
  startAssignment,
  type AssignmentStatus,
  type LearnerAssignment,
  type NextQuestion,
  type QuizSummaryResponse,
} from "@/services/api";
import QuestionCard from "@/components/QuestionCard";
import QuizSummary from "@/components/QuizSummary";

// A per-learner assignment list (spec 011, User Story 2) -- "start"
// re-uses the exact same question/answer/summary UI `quiz-flow.tsx`
// already built for a self-serve quiz (`QuestionCard`/`QuizSummary`,
// `getQuizNextQuestion`/`answerQuestion`/`getQuizSummary`), since an
// assignment attempt is just an ordinary quiz session under the hood
// (research.md §1) and must look identical to one.

type Phase = "list" | "answering" | "submitting" | "finished";

const STATUS_LABEL: Record<AssignmentStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
  ended_early: "Ended early",
};

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export interface LearnerAssignmentsProps {
  learnerId: string;
}

export default function LearnerAssignments({ learnerId }: LearnerAssignmentsProps) {
  const [assignments, setAssignments] = useState<LearnerAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [startingId, setStartingId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  const [phase, setPhase] = useState<Phase>("list");
  const [quizSessionId, setQuizSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<NextQuestion | null>(null);
  const [response, setResponse] = useState("");
  const [flagged, setFlagged] = useState(false);
  const [summary, setSummary] = useState<QuizSummaryResponse | null>(null);
  const [attemptError, setAttemptError] = useState<string | null>(null);

  // `refreshAssignments` is only ever called from event handlers (the
  // "Back to assignments" button below), never from the effect itself --
  // it resets `loading`/`loadError` synchronously, which the mount
  // effect below deliberately never does (react-hooks/set-state-in-effect):
  // `loading` already starts `true` via its initial state, so the effect
  // only ever needs to set state from inside its `.then`/`.catch`.
  function refreshAssignments() {
    setLoading(true);
    setLoadError(null);
    listLearnerAssignments(learnerId)
      .then((result) => {
        setAssignments(result.assignments);
        setLoading(false);
      })
      .catch((error: unknown) => {
        setLoadError(errorText(error));
        setLoading(false);
      });
  }

  useEffect(() => {
    let cancelled = false;
    listLearnerAssignments(learnerId)
      .then((result) => {
        if (cancelled) return;
        setAssignments(result.assignments);
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setLoadError(errorText(error));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId]);

  async function goToSummary(sessionId: string) {
    const result = await getQuizSummary(sessionId);
    setSummary(result);
    setPhase("finished");
  }

  async function handleStart(assignmentId: string) {
    setStartingId(assignmentId);
    setStartError(null);
    try {
      const result = await startAssignment(assignmentId, learnerId);
      setQuizSessionId(result.quiz_session_id);
      if (result.status === "in_progress" && result.question) {
        setCurrentQuestion(result.question);
        setPhase("answering");
      } else {
        await goToSummary(result.quiz_session_id);
      }
    } catch (error) {
      setStartError(errorText(error));
    } finally {
      setStartingId(null);
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
      setAttemptError(errorText(error));
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
      setAttemptError(errorText(error));
      setPhase("answering");
    }
  }

  async function handleFreeTextGraded() {
    if (!quizSessionId) return;
    setResponse("");
    await advanceToNextQuestion(quizSessionId);
  }

  async function handleFlag(reason: string) {
    if (!currentQuestion) return;
    try {
      await flagQuestion(currentQuestion.question_id, learnerId, reason);
      setFlagged(true);
    } catch (error) {
      setAttemptError(errorText(error));
    }
  }

  function handleBackToList() {
    setPhase("list");
    setQuizSessionId(null);
    setCurrentQuestion(null);
    setSummary(null);
    setAttemptError(null);
    refreshAssignments();
  }

  if (phase === "finished" && summary) {
    return (
      <div className="flex flex-col gap-6" data-testid="learner-assignment-attempt">
        <QuizSummary summary={summary} />
        <button
          type="button"
          onClick={handleBackToList}
          className="self-start rounded-lg border border-border px-4 py-2 text-sm"
        >
          Back to assignments
        </button>
      </div>
    );
  }

  if ((phase === "answering" || phase === "submitting") && currentQuestion) {
    return (
      <div className="flex flex-col gap-6" data-testid="learner-assignment-attempt">
        {attemptError && (
          <p className="text-sm text-error" data-testid="learner-assignment-attempt-error">
            {attemptError}
          </p>
        )}
        <QuestionCard
          question={currentQuestion}
          response={response}
          onResponseChange={setResponse}
          onFlag={handleFlag}
          flagged={flagged}
          disabled={phase === "submitting"}
          onFreeTextGraded={handleFreeTextGraded}
        />
        {currentQuestion.question_type !== "free_text" && (
          <button
            type="button"
            disabled={response === "" || phase === "submitting"}
            onClick={handleSubmitAnswer}
            className="rounded-lg bg-primary px-5 py-3 text-primary-foreground disabled:opacity-40"
          >
            {phase === "submitting" ? "Submitting…" : "Submit Answer"}
          </button>
        )}
      </div>
    );
  }

  if (loading) {
    return <p className="text-sm">Loading assignments&hellip;</p>;
  }

  if (loadError) {
    return (
      <p className="text-sm text-error" data-testid="learner-assignments-error">
        {loadError}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2" data-testid="learner-assignments">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Assigned quizzes</h3>
        <button type="button" onClick={refreshAssignments} className="text-sm text-muted underline">
          Refresh
        </button>
      </div>
      {assignments.length === 0 && <p className="text-sm">No assignments yet.</p>}
      {assignments.map((assignment) => (
        <div
          key={assignment.assignment_id}
          data-testid={`learner-assignment-${assignment.assignment_id}`}
          className="flex items-center justify-between rounded-lg border border-border px-4 py-3 text-sm"
        >
          <div className="flex flex-col gap-1">
            <span>
              {assignment.topic_ids.join(", ")} &middot; {assignment.question_count} questions
            </span>
            <span className="text-muted">
              {STATUS_LABEL[assignment.status]}
              {assignment.due_at && ` · due ${new Date(assignment.due_at).toLocaleString()}`}
              {assignment.cancelled_at && (
                <span data-testid={`learner-assignment-cancelled-${assignment.assignment_id}`}>
                  {" "}
                  &middot; cancelled
                </span>
              )}
            </span>
          </div>
          {assignment.status === "not_started" && !assignment.cancelled_at && (
            <button
              type="button"
              onClick={() => handleStart(assignment.assignment_id)}
              disabled={startingId === assignment.assignment_id}
              className="rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-40"
            >
              {startingId === assignment.assignment_id ? "Starting…" : "Start"}
            </button>
          )}
        </div>
      ))}
      {startError && (
        <p className="text-sm text-error" data-testid="learner-assignment-start-error">
          {startError}
        </p>
      )}
    </div>
  );
}

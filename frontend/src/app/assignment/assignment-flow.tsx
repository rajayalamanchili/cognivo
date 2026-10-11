"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  answerQuestion,
  flagQuestion,
  getQuizNextQuestion,
  getQuizSummary,
  getWhoAmI,
  listLearnerAssignments,
  startAssignment,
  type AnswerResult,
  type NextQuestion,
  type QuizSummaryResponse,
} from "@/services/api";
import { getRealLearnerSession } from "@/lib/visitor-state";
import QuestionCard from "@/components/QuestionCard";
import QuizSummary from "@/components/QuizSummary";
import LoadingIndicator from "@/components/LoadingIndicator";
import { getPacingProfile } from "@/lib/pacing";
import { formatTopicId } from "@/lib/format-topic-id";

// A dedicated full-page flow for an assigned quiz (mirrors `/practice`
// and `/placement`'s own page+flow split) -- "Start"/"Resume" on the
// guardian's learner card (`LearnerAssignments.tsx`) navigate here via
// `enterRealLearnerSession` + `router.push`, same hand-off pattern
// `GuardianLearnerCard`'s "Start practice"/"Take placement" tiles
// already use, instead of answering the quiz inline inside the card.

type Phase = "loading" | "answering" | "submitting" | "stopping-point" | "finished" | "error";

const REINFORCEMENT_MESSAGE = "Nice work! Keep it up! ⭐";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function AssignmentFlow() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const assignmentId = searchParams.get("assignmentId");

  const [phase, setPhase] = useState<Phase>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [topicIds, setTopicIds] = useState<string[]>([]);

  const [quizSessionId, setQuizSessionId] = useState<string | null>(null);
  const [handoffToken, setHandoffToken] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<NextQuestion | null>(null);
  const [response, setResponse] = useState("");
  const [flagged, setFlagged] = useState(false);
  const [readAloudUsed, setReadAloudUsed] = useState(false);
  const [readAloudDefault, setReadAloudDefault] = useState(false);
  const [summary, setSummary] = useState<QuizSummaryResponse | null>(null);
  const [attemptError, setAttemptError] = useState<string | null>(null);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [stoppingPointShown, setStoppingPointShown] = useState(false);
  const [reinforcementMessage, setReinforcementMessage] = useState<string | null>(null);
  const [refreshedTopicIds, setRefreshedTopicIds] = useState<Set<string>>(new Set());

  function recordIfRefreshed(topicId: string, result: { refreshed: boolean }) {
    if (!result.refreshed) return;
    setRefreshedTopicIds((prev) => new Set(prev).add(topicId));
  }

  async function goToSummary(sessionId: string, handoffTokenOverride?: string | null) {
    const result = await getQuizSummary(sessionId, handoffTokenOverride ?? handoffToken);
    setSummary(result);
    setPhase("finished");
  }

  useEffect(() => {
    let cancelled = false;

    async function resolve() {
      if (!assignmentId) {
        setErrorMessage("No assignment was specified.");
        setPhase("error");
        return;
      }
      const session = getRealLearnerSession();
      if (!session) {
        setErrorMessage("Open this quiz from the learner's card on My learners.");
        setPhase("error");
        return;
      }
      setLearnerId(session.learnerId);
      getWhoAmI()
        .then((who) => {
          if (!cancelled) setReadAloudDefault(who.read_aloud_default ?? false);
        })
        .catch(() => {});

      try {
        const list = await listLearnerAssignments(session.learnerId);
        if (cancelled) return;
        const match = list.assignments.find((a) => a.assignment_id === assignmentId);
        if (!match) {
          setErrorMessage("That assignment could not be found.");
          setPhase("error");
          return;
        }
        setTopicIds(match.topic_ids);

        if (match.status === "not_started") {
          const started = await startAssignment(assignmentId, session.learnerId);
          if (cancelled) return;
          setQuizSessionId(started.quiz_session_id);
          setHandoffToken(started.handoff_token);
          if (started.status === "in_progress" && started.question) {
            setCurrentQuestion(started.question);
            setPhase("answering");
          } else {
            await goToSummary(started.quiz_session_id, started.handoff_token);
          }
          return;
        }

        if (match.status === "in_progress" && match.quiz_session_id) {
          setQuizSessionId(match.quiz_session_id);
          setHandoffToken(null);
          const next = await getQuizNextQuestion(match.quiz_session_id, null);
          if (cancelled) return;
          if (next.status === "in_progress" && next.question) {
            setCurrentQuestion(next.question);
            setPhase("answering");
          } else {
            await goToSummary(match.quiz_session_id, null);
          }
          return;
        }

        if (match.quiz_session_id) {
          setQuizSessionId(match.quiz_session_id);
          await goToSummary(match.quiz_session_id, null);
          return;
        }

        setErrorMessage("This assignment has no attempt to show.");
        setPhase("error");
      } catch (error) {
        if (cancelled) return;
        setErrorMessage(errorText(error));
        setPhase("error");
      }
    }

    void resolve();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignmentId]);

  async function advanceToNextQuestion(sessionId: string) {
    try {
      const next = await getQuizNextQuestion(sessionId, handoffToken);
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
      setAttemptError(errorText(error));
    }
  }

  // spec 019 FR-009: same soft, dismissible checkpoint quiz-flow.tsx/
  // LearnerAssignments.tsx use -- called after every answered question.
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
      const result = await answerQuestion(
        currentQuestion.question_id,
        value,
        readAloudUsed,
        handoffToken,
      );
      recordIfRefreshed(currentQuestion.topic_id, result);
      setResponse("");
      await advanceAfterAnswer(quizSessionId, currentQuestion.unlocked_grade);
    } catch (error) {
      setAttemptError(errorText(error));
      setPhase("answering");
    }
  }

  async function handleFreeTextGraded(result: AnswerResult) {
    if (!quizSessionId || !currentQuestion) return;
    recordIfRefreshed(currentQuestion.topic_id, result);
    setResponse("");
    await advanceAfterAnswer(quizSessionId, currentQuestion.unlocked_grade);
  }

  async function handleFlag(reason: string) {
    if (!currentQuestion || !learnerId) return;
    try {
      await flagQuestion(currentQuestion.question_id, learnerId, reason);
      setFlagged(true);
    } catch (error) {
      setAttemptError(errorText(error));
    }
  }

  if (phase === "loading") {
    return <LoadingIndicator message="Finding your quiz…" />;
  }

  if (phase === "error") {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 p-8">
        <p className="text-error">{errorMessage}</p>
        <Link href="/guardian/learners" className="text-link underline">
          Back to My learners
        </Link>
      </div>
    );
  }

  if (phase === "stopping-point") {
    return (
      <div
        className="mx-auto flex w-full max-w-2xl flex-col items-center gap-4 p-8 text-center"
        data-testid="quiz-stopping-point"
      >
        <p className="text-lg">Nice work! You&apos;ve reached a good stopping point.</p>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleContinueFromStoppingPoint}
            className="rounded-full bg-primary px-5 py-3 text-primary-foreground"
          >
            Keep going
          </button>
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="rounded-full border border-border px-5 py-3"
          >
            I&apos;m done for now
          </button>
        </div>
      </div>
    );
  }

  if (phase === "finished" && summary) {
    return (
      <div
        className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8"
        data-testid="learner-assignment-attempt"
      >
        <QuizSummary
          summary={summary}
          refreshedTopicIds={[...refreshedTopicIds]}
          unlockedGrade={currentQuestion?.unlocked_grade ?? null}
        />
        <button
          type="button"
          onClick={() => router.push("/dashboard")}
          className="self-start rounded-full bg-primary px-5 py-3 font-extrabold text-primary-foreground"
        >
          Done
        </button>
      </div>
    );
  }

  if ((phase === "answering" || phase === "submitting") && currentQuestion) {
    const ownsSubmit =
      currentQuestion.question_type !== "free_text" && currentQuestion.question_type !== "multi_step";
    return (
      <div
        className="mx-auto flex w-full max-w-[860px] flex-col gap-5 p-8"
        data-testid="learner-assignment-attempt"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <span className="text-[13px] font-extrabold uppercase tracking-wide text-primary">
            {topicIds.map(formatTopicId).join(", ")} · Assigned quiz
          </span>
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="text-[15px] font-extrabold text-link"
          >
            End session
          </button>
        </div>
        {attemptError && (
          <p className="text-sm text-error" data-testid="learner-assignment-attempt-error">
            {attemptError}
          </p>
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
          readAloudDefault={readAloudDefault}
          onReadAloudUsed={() => setReadAloudUsed(true)}
          handoffToken={handoffToken}
        />
        {ownsSubmit && (
          <button
            type="button"
            disabled={response === "" || phase === "submitting"}
            onClick={handleSubmitAnswer}
            className="self-start rounded-full bg-primary px-7 py-3.5 text-[17px] font-extrabold text-primary-foreground disabled:opacity-40"
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

  return null;
}

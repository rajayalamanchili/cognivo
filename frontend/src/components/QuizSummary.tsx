import type { Difficulty, QuizSummaryResponse } from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";
import SessionTimingSummary from "@/components/SessionTimingSummary";
import AnswerResultView from "@/components/AnswerResultView";
import { getExplanationCopyTier } from "@/lib/explainabilityCopy";

// Presentational only -- FR-005's score + per-topic/difficulty summary,
// rendered identically whether the quiz reached a normal `completed`
// state or `ended_early` (contracts/api.md, checklist review 2026-08-18).

const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

const STATUS_LABEL: Record<"completed" | "ended_early", string> = {
  completed: "Quiz completed",
  ended_early: "Quiz ended early",
};

export interface QuizSummaryProps {
  summary: QuizSummaryResponse;
  // Spec 025 FR-011/User Story 4 (research.md §5): the *unmodified*
  // `refreshed` flag from each answer's own response, accumulated in
  // ephemeral session-local state by the caller as the quiz progressed
  // -- never recomputed here, never persisted.
  refreshedTopicIds?: string[];
  unlockedGrade?: number | null;
}

export default function QuizSummary({
  summary,
  refreshedTopicIds = [],
  unlockedGrade = null,
}: QuizSummaryProps) {
  const tier = getExplanationCopyTier(unlockedGrade);
  const heading =
    summary.status === "in_progress" ? "Quiz in progress" : STATUS_LABEL[summary.status];

  return (
    <div className="flex flex-col gap-4" data-testid="quiz-summary">
      <h2 className="text-xl font-semibold">{heading}</h2>
      <p className="text-lg">
        Score: <strong>{summary.score.correct}</strong> / {summary.score.total}
      </p>
      <SessionTimingSummary
        timeLimitSeconds={summary.time_limit_seconds}
        elapsedSeconds={summary.elapsed_seconds}
        endReason={summary.end_reason}
      />
      {summary.summary.length > 0 && (
        <ul className="flex flex-col gap-2">
          {summary.summary.map((entry) => (
            <li
              key={`${entry.topic_id}-${entry.difficulty}`}
              className="flex items-center justify-between rounded-lg border border-border px-4 py-3"
            >
              <span className="font-medium">{formatTopicId(entry.topic_id)}</span>
              <span className="text-sm text-muted">{DIFFICULTY_LABEL[entry.difficulty]}</span>
              <span className="text-sm">
                {entry.correct} / {entry.total}
              </span>
            </li>
          ))}
        </ul>
      )}
      {refreshedTopicIds.length > 0 && (
        <p
          data-testid="quiz-refreshed-topics"
          className="rounded-lg bg-success/15 px-4 py-3 text-sm font-medium text-success"
        >
          {tier.refreshedFraming} ({refreshedTopicIds.map(formatTopicId).join(", ")})
        </p>
      )}
      {summary.per_question_results != null && summary.per_question_results.length > 0 && (
        <div className="flex flex-col gap-4" data-testid="quiz-per-question-results">
          <p className="text-sm font-medium text-muted">How each question was graded</p>
          {summary.per_question_results.map((result) => (
            <AnswerResultView key={result.question_id} result={result} />
          ))}
        </div>
      )}
    </div>
  );
}

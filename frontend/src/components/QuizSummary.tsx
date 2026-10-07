import type { Difficulty, QuizSummaryResponse } from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";
import SessionTimingSummary from "@/components/SessionTimingSummary";
import AnswerResultView from "@/components/AnswerResultView";
import { getExplanationCopyTier } from "@/lib/explainabilityCopy";
import { masteryBeforeAfterByTopic } from "@/lib/mastery-before-after";

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
  const beforeAfter = masteryBeforeAfterByTopic(summary.per_question_results);

  return (
    <div className="flex flex-col gap-5" data-testid="quiz-summary">
      <section className="flex flex-col gap-4 rounded-card border border-border bg-surface p-8">
        <span className="text-[13px] font-extrabold tracking-[0.08em] text-primary">
          {heading.toUpperCase()}
        </span>
        <p className="font-heading text-[28px] font-bold leading-tight text-heading">
          Score: {summary.score.correct} / {summary.score.total}
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
                className="flex items-center justify-between gap-3 rounded-2xl bg-surface-subtle px-4 py-3"
              >
                <span className="font-extrabold">{formatTopicId(entry.topic_id)}</span>
                <span className="text-sm text-muted">{DIFFICULTY_LABEL[entry.difficulty]}</span>
                <span className="rounded-full bg-primary-subtle px-3 py-0.5 text-sm font-extrabold text-heading">
                  {entry.correct} / {entry.total}
                </span>
              </li>
            ))}
          </ul>
        )}
        {refreshedTopicIds.length > 0 && (
          <p
            data-testid="quiz-refreshed-topics"
            className="rounded-2xl bg-success/15 px-4 py-3 text-sm font-bold text-success"
          >
            {tier.refreshedFraming} ({refreshedTopicIds.map(formatTopicId).join(", ")})
          </p>
        )}
      </section>
      {beforeAfter.length > 0 && (
        <section
          className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6"
          data-testid="quiz-mastery-before-after"
        >
          <h3 className="font-heading text-xl font-bold text-heading">Mastery before → after</h3>
          <ul className="flex flex-col gap-2">
            {beforeAfter.map((entry) => (
              <li
                key={entry.topic_id}
                className="flex items-center justify-between gap-3 rounded-2xl bg-surface-subtle px-4 py-3"
              >
                <span className="font-extrabold">{formatTopicId(entry.topic_id)}</span>
                <span className="text-sm font-bold text-muted">
                  {entry.before != null ? `${Math.round(entry.before * 100)}%` : "—"} &rarr;{" "}
                  {Math.round(entry.after * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {summary.per_question_results != null && summary.per_question_results.length > 0 && (
        <section
          className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6"
          data-testid="quiz-per-question-results"
        >
          <h3 className="font-heading text-xl font-bold text-heading">
            How each answer was graded
          </h3>
          {summary.per_question_results.map((result) => (
            <AnswerResultView key={result.question_id} result={result} />
          ))}
        </section>
      )}
    </div>
  );
}

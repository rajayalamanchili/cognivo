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
  const scorePct =
    summary.score.total > 0 ? Math.round((summary.score.correct / summary.score.total) * 100) : null;

  return (
    <div className="flex flex-col gap-5" data-testid="quiz-summary">
      <section className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-6 rounded-card border border-border bg-surface p-8">
        <div className="flex flex-col gap-4">
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
        </div>
        {scorePct != null && (
          <div
            role="img"
            aria-label={`${scorePct} percent correct`}
            className="flex h-28 w-28 flex-shrink-0 items-center justify-center rounded-full"
            style={{
              background: `conic-gradient(var(--color-primary) 0 ${scorePct}%, var(--color-surface-subtle) ${scorePct}% 100%)`,
            }}
          >
            <span className="flex h-[84px] w-[84px] items-center justify-center rounded-full bg-surface font-heading text-[28px] font-bold text-heading">
              {scorePct}%
            </span>
          </div>
        )}
      </section>
      <section className="flex flex-col gap-4 rounded-card border border-border bg-surface p-8">
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
          <h3 className="font-heading text-xl font-bold text-heading">Your mastery, before and after</h3>
          <ul className="flex flex-col gap-4">
            {beforeAfter.map((entry) => {
              const beforePct = entry.before != null ? Math.round(entry.before * 100) : null;
              const afterPct = Math.round(entry.after * 100);
              const delta = beforePct != null ? afterPct - beforePct : null;
              return (
                <li key={entry.topic_id} className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <span className="font-extrabold">
                      {formatTopicId(entry.topic_id)}{" "}
                      <span className="text-sm font-semibold text-muted">
                        · {entry.question_count} question{entry.question_count === 1 ? "" : "s"}
                      </span>
                    </span>
                    <span className="flex items-baseline gap-2">
                      <span className="font-heading text-lg font-bold text-muted">
                        {beforePct != null ? `${beforePct}%` : "—"}
                      </span>
                      <span aria-hidden="true" className="text-muted">
                        &rarr;
                      </span>
                      <span className="font-heading text-2xl font-bold text-heading">{afterPct}%</span>
                      {delta != null && (
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[13px] font-extrabold ${
                            delta >= 0 ? "bg-success/15 text-success" : "bg-warning/15 text-warning"
                          }`}
                        >
                          {delta >= 0 ? "+" : "−"}
                          {Math.abs(delta)}
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="relative h-3 rounded-full bg-surface-subtle" aria-hidden="true">
                    <div
                      className="absolute inset-y-0 left-0 rounded-full bg-primary/40"
                      style={{ width: `${afterPct}%` }}
                    />
                    {beforePct != null && (
                      <div
                        className="absolute inset-y-0 left-0 rounded-full bg-primary"
                        style={{ width: `${beforePct}%` }}
                      />
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="text-sm text-muted">
            &ldquo;Before&rdquo; is your estimate going into the first question on each topic;
            &ldquo;after&rdquo; is the estimate after your last one.
          </p>
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

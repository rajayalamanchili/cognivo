import type { Difficulty, QuizSummaryResponse } from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";

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
}

export default function QuizSummary({ summary }: QuizSummaryProps) {
  const heading =
    summary.status === "in_progress" ? "Quiz in progress" : STATUS_LABEL[summary.status];

  return (
    <div className="flex flex-col gap-4" data-testid="quiz-summary">
      <h2 className="text-xl font-semibold">{heading}</h2>
      <p className="text-lg">
        Score: <strong>{summary.score.correct}</strong> / {summary.score.total}
      </p>
      {summary.summary.length > 0 && (
        <ul className="flex flex-col gap-2">
          {summary.summary.map((entry) => (
            <li
              key={`${entry.topic_id}-${entry.difficulty}`}
              className="flex items-center justify-between rounded border border-black/10 px-4 py-3 dark:border-white/10"
            >
              <span className="font-medium">{formatTopicId(entry.topic_id)}</span>
              <span className="text-sm text-zinc-500 dark:text-zinc-400">
                {DIFFICULTY_LABEL[entry.difficulty]}
              </span>
              <span className="text-sm">
                {entry.correct} / {entry.total}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

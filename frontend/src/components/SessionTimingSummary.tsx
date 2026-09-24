import type { SessionEndReason } from "@/services/api";

// Spec 022 SC-005: the configured time limit, actual time used, and
// how a timed session ended -- shared by QuizSummary and the practice
// result view so the two can't drift into different wording. Renders
// nothing for an untimed session (all three fields null).

const END_REASON_LABEL: Record<Exclude<SessionEndReason, null>, string> = {
  completed: "Finished before time ran out",
  timer_expired: "Time ran out",
  manually_ended_early: "Ended early",
  dedup_exhausted: "Ended early -- ran out of new questions",
};

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds === 0 ? `${minutes} min` : `${minutes} min ${seconds} sec`;
}

export interface SessionTimingSummaryProps {
  timeLimitSeconds: number | null | undefined;
  elapsedSeconds: number | null | undefined;
  endReason: SessionEndReason | undefined;
}

export default function SessionTimingSummary({
  timeLimitSeconds,
  elapsedSeconds,
  endReason,
}: SessionTimingSummaryProps) {
  if (timeLimitSeconds == null) return null;

  return (
    <p data-testid="session-timing-summary" className="text-sm text-muted">
      Time limit: {formatDuration(timeLimitSeconds)}
      {elapsedSeconds != null && <> · Time used: {formatDuration(elapsedSeconds)}</>}
      {endReason && <> · {END_REASON_LABEL[endReason]}</>}
    </p>
  );
}

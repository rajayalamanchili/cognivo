import type { StandardCoverageEntry, StandardCoverageStatus } from "@/services/api";

// Spec 038 FR-004/FR-006/FR-007/FR-011. Presentational only -- takes
// already-fetched coverage entries (identical shape/derivation whether
// the caller is the instructor dashboard or the guardian's own learner
// view) so this one component serves both surfaces.

const STATUS_LABEL: Record<StandardCoverageStatus, string> = {
  met: "Met",
  in_progress: "In progress",
  not_yet_reached: "Not yet reached",
};

// Same bg-X/15 text-X pill idiom MasteryView's BAND_CLASSES already
// uses -- every status pairs a color with the visible text label above,
// never color alone (FR-011).
const STATUS_CLASSES: Record<StandardCoverageStatus, string> = {
  met: "bg-success/15 text-success",
  in_progress: "bg-warning/15 text-warning",
  not_yet_reached: "bg-surface-subtle text-muted",
};

export interface StandardsCoverageProps {
  standards: StandardCoverageEntry[];
  // Spec 038 FR-013: a developer-controlled, frontend-only render
  // toggle. Exposed as a prop (not a bare module-level const) so tests
  // don't need to fight Next.js's build-time env-var inlining -- the
  // same pattern SelectionReasonChip's `explainEveryPick` prop already
  // establishes (research.md Decision 5).
  enabled?: boolean;
}

export default function StandardsCoverage({
  standards,
  enabled = process.env.NEXT_PUBLIC_STANDARDS_ALIGNMENT_ENABLED !== "false",
}: StandardsCoverageProps) {
  if (!enabled || standards.length === 0) return null;

  return (
    <ul
      className="flex flex-col gap-1 rounded-card border border-border bg-surface p-3"
      data-testid="standards-coverage"
    >
      {standards.map((standard) => (
        <li
          key={`${standard.framework}:${standard.code}`}
          className="flex items-center justify-between gap-3 rounded-[18px] px-4 py-3"
        >
          <div className="flex flex-col">
            <span className="text-[13px] font-semibold text-muted">{standard.framework}</span>
            <span className="text-[15px] font-extrabold text-heading">{standard.code}</span>
            <span className="text-[13px] text-muted">{standard.title}</span>
          </div>
          <span
            className={`shrink-0 rounded-full px-3 py-1 text-[13px] font-semibold ${STATUS_CLASSES[standard.status]}`}
          >
            {STATUS_LABEL[standard.status]}
          </span>
        </li>
      ))}
    </ul>
  );
}

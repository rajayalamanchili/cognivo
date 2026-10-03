import type { MasteryHistoryPoint } from "@/services/api";

// Spec 025 FR-012: a small trend line built from recorded mastery
// history. Native inline SVG -- no charting library, this project has
// none installed and a sparkline is a handful of lines of markup.

const SIZES = {
  sm: { width: 160, height: 40, padding: 4 },
  // Mastery screen's detail-panel chart (mockup's larger 320x120
  // "Mastery over time" card) -- same component, just sized up and
  // with the mastery-line reference drawn in.
  lg: { width: 320, height: 120, padding: 6 },
  // Mastery screen's per-row sparkline (mockup's 120x36 inline chart
  // next to each topic's bar) -- too narrow for the sm/lg single-point
  // text fallback, so that case renders nothing instead (see below).
  row: { width: 120, height: 36, padding: 3 },
};

// Same 0.7 cutoff MasteryView/AnswerResultView mirror elsewhere.
const MASTERED_THRESHOLD = 0.7;

export interface MasteryTrendProps {
  points: MasteryHistoryPoint[];
  size?: keyof typeof SIZES;
  showMasteryLine?: boolean;
}

export default function MasteryTrend({
  points,
  size = "sm",
  showMasteryLine = false,
}: MasteryTrendProps) {
  if (points.length === 0) return null;

  if (points.length === 1) {
    if (size === "row") return null;
    return (
      <div data-testid="mastery-trend" className="text-[15px] font-bold text-muted">
        {Math.round(points[0].p_mastery * 100)}% (not enough history yet for a trend)
      </div>
    );
  }

  const { width, height, padding } = SIZES[size];
  const coords = points.map((point, index) => {
    const x = padding + (index / (points.length - 1)) * (width - 2 * padding);
    const y = height - padding - point.p_mastery * (height - 2 * padding);
    return `${x},${y}`;
  });
  const masteryLineY = height - padding - MASTERED_THRESHOLD * (height - 2 * padding);

  return (
    <div data-testid="mastery-trend" className="flex flex-col gap-1">
      <svg
        data-testid="mastery-trend-line"
        width={size === "lg" ? "100%" : width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Mastery over time"
      >
        {showMasteryLine && (
          <line
            data-testid="mastery-trend-line-threshold"
            x1={0}
            x2={width}
            y1={masteryLineY}
            y2={masteryLineY}
            stroke="currentColor"
            className="text-heading"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
        )}
        <polyline
          points={coords.join(" ")}
          fill="none"
          stroke="currentColor"
          strokeWidth={size === "lg" ? 3 : 2.2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-primary"
        />
      </svg>
      {size === "lg" && (
        <div className="flex justify-between text-xs font-bold text-muted">
          <span>First answer</span>
          <span>Today</span>
        </div>
      )}
    </div>
  );
}

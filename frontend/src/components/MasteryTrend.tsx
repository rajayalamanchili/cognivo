import type { MasteryHistoryPoint } from "@/services/api";

// Spec 025 FR-012: a small trend line built from recorded mastery
// history. Native inline SVG -- no charting library, this project has
// none installed and a sparkline is a handful of lines of markup.

const WIDTH = 160;
const HEIGHT = 40;
const PADDING = 4;

export interface MasteryTrendProps {
  points: MasteryHistoryPoint[];
}

export default function MasteryTrend({ points }: MasteryTrendProps) {
  if (points.length === 0) return null;

  if (points.length === 1) {
    return (
      <div data-testid="mastery-trend" className="text-sm text-muted">
        {Math.round(points[0].p_mastery * 100)}% (not enough history yet for a trend)
      </div>
    );
  }

  const coords = points.map((point, index) => {
    const x = PADDING + (index / (points.length - 1)) * (WIDTH - 2 * PADDING);
    const y = HEIGHT - PADDING - point.p_mastery * (HEIGHT - 2 * PADDING);
    return `${x},${y}`;
  });

  return (
    <div data-testid="mastery-trend">
      <svg
        data-testid="mastery-trend-line"
        width={WIDTH}
        height={HEIGHT}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Mastery over time"
      >
        <polyline
          points={coords.join(" ")}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          className="text-primary"
        />
      </svg>
    </div>
  );
}

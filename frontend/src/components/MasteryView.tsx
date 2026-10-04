import type { MasteryBand, MasteryHistoryPoint, MasteryStateEntry } from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";
import { getExplanationCopyTier } from "@/lib/explainabilityCopy";
import MasteryTrend from "@/components/MasteryTrend";

// Presentational only -- takes already-fetched mastery entries so it can
// be reused both right after placement submission and on a standalone
// mastery page (Constitution Principle V: "why was I placed here" must
// be answerable anytime, not just once).

const BAND_LABEL: Record<MasteryBand, string> = {
  struggling: "Struggling",
  developing: "Developing",
  mastered: "Mastered",
};

const BAND_CLASSES: Record<MasteryBand, string> = {
  struggling: "bg-error/15 text-error",
  developing: "bg-warning/15 text-warning",
  mastered: "bg-success/15 text-success",
};

const BAND_BAR_CLASSES: Record<MasteryBand, string> = {
  struggling: "bg-error",
  developing: "bg-warning",
  mastered: "bg-primary",
};

// Same 0.7 raw-score cutoff `mastery_band_for` (backend/src/models/
// enums.py) uses for "mastered" -- a fixed global constant, not
// per-classroom configurable, so it's safe to mirror here purely to
// place the mastery-line tick mark on the bar below. Same pattern as
// AnswerResultView's own MASTERED_THRESHOLD_PCT.
const MASTERED_THRESHOLD_PCT = 70;

// Spec 025 FR-005/FR-006/FR-007: placement's own `MasteryStateEntry`
// response shape never carries decay/timestamp data (no equivalent
// concept in an immediate post-submission summary) -- these stay
// optional so that shape still type-checks and renders gracefully,
// rather than forcing a second, poorer-typed MasteryView variant.
type MasteryViewEntry = MasteryStateEntry & {
  last_updated_at?: string | null;
  effective_p_mastery?: number | null;
};

export interface MasteryViewProps {
  topics: MasteryViewEntry[];
  unlockedGrade?: number | null;
  // Mastery screen only (mockup's clickable topic-list/detail-panel
  // layout): when provided, each row becomes a selectable button
  // instead of a static list item. Omitted everywhere else (Dashboard's
  // mini list, Placement's end-of-placement summary), which keeps
  // their existing non-interactive rendering untouched.
  selectedTopicId?: string | null;
  onSelectTopic?: (topicId: string) => void;
  // Mastery screen mockup shows a mastery-line tick on every bar;
  // Dashboard's reuse of this same component does not -- opt-in per
  // caller rather than a blanket change to a shared component.
  showMasteryLine?: boolean;
  // Mastery screen only: a per-topic history map, pre-fetched by the
  // caller (Dashboard/Placement never pass this, so they never render
  // the row sparkline their own mockups don't show).
  historyByTopic?: Record<string, MasteryHistoryPoint[]>;
}

function elapsedDays(lastUpdatedAt: string): number {
  return Math.floor((Date.now() - new Date(lastUpdatedAt).getTime()) / 86_400_000);
}

const RELATIVE_TIME = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

function formatElapsed(lastUpdatedAt: string): string {
  const days = elapsedDays(lastUpdatedAt);
  if (days < 1) return "today";
  if (days < 7) return RELATIVE_TIME.format(-days, "day");
  if (days < 30) return RELATIVE_TIME.format(-Math.floor(days / 7), "week");
  if (days < 365) return RELATIVE_TIME.format(-Math.floor(days / 30), "month");
  return RELATIVE_TIME.format(-Math.floor(days / 365), "year");
}

// Discrete warmth tiers (FR-007's color intensity), same lookup-table
// idiom as BAND_CLASSES above rather than a continuous blend.
const WARMTH_TIERS: { maxDays: number; className: string }[] = [
  { maxDays: 7, className: "text-muted" },
  { maxDays: 30, className: "text-warning/60" },
  { maxDays: 90, className: "text-warning" },
  { maxDays: Infinity, className: "text-error" },
];

function warmthClass(days: number): string {
  return WARMTH_TIERS.find((tier) => days <= tier.maxDays)?.className ?? "text-muted";
}

export default function MasteryView({
  topics,
  unlockedGrade = null,
  selectedTopicId,
  onSelectTopic,
  showMasteryLine = false,
  historyByTopic,
}: MasteryViewProps) {
  return (
    <ul
      className="flex flex-col gap-1 rounded-card border border-border bg-surface p-3"
      data-testid="mastery-view"
    >
      {topics.map((topic) => {
        const selected = onSelectTopic && topic.topic_id === selectedTopicId;
        const rowClassName = `flex flex-col gap-2 rounded-[18px] px-4 py-3 text-left ${
          onSelectTopic
            ? `w-full border-2 ${selected ? "border-primary bg-surface-subtle" : "border-transparent"}`
            : ""
        }`;
        const content = (
          <>
            <div className="flex items-center justify-between">
              <span className="text-[17px] font-extrabold text-heading">
                {formatTopicId(topic.topic_id)}
              </span>
              {topic.status === "unknown" || topic.band === null ? (
                <span className="rounded-full bg-surface-subtle px-3 py-1 text-xs font-bold text-muted">
                  Not yet assessed
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-3 py-0.5 text-xs font-extrabold ${BAND_CLASSES[topic.band]}`}
                  >
                    {BAND_LABEL[topic.band]}
                  </span>
                  <MasteryFigures topic={topic} unlockedGrade={unlockedGrade} />
                </span>
              )}
            </div>
            <div className="flex items-center gap-5">
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <MasteryBar
                  band={topic.band}
                  peak={topic.p_mastery !== null ? Math.round(topic.p_mastery * 100) : null}
                  effective={
                    topic.p_mastery === null
                      ? null
                      : topic.effective_p_mastery != null
                        ? Math.round(topic.effective_p_mastery * 100)
                        : Math.round(topic.p_mastery * 100)
                  }
                  showMasteryLine={showMasteryLine}
                />
                {topic.status !== "unknown" &&
                  topic.band !== null &&
                  topic.last_updated_at != null && (
                    <LastPracticed topicId={topic.topic_id} lastUpdatedAt={topic.last_updated_at} />
                  )}
              </div>
              {historyByTopic && (
                <div className="w-[120px] flex-shrink-0 text-muted">
                  <MasteryTrend points={historyByTopic[topic.topic_id] ?? []} size="row" />
                </div>
              )}
            </div>
          </>
        );
        return (
          <li key={topic.topic_id} data-testid={`mastery-topic-${topic.topic_id}`}>
            {onSelectTopic ? (
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => onSelectTopic(topic.topic_id)}
                className={rowClassName}
              >
                {content}
              </button>
            ) : (
              <div className={rowClassName}>{content}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// Peak (dashed outline) vs. effective/decayed (solid fill) mastery, same
// two values `MasteryFigures` already renders as text -- no new data.
// The track itself always renders, even for a not-yet-assessed topic
// (`peak`/`effective` both null then) -- matching the mockup, which
// shows every topic's empty bar track for visual consistency down the
// list rather than only showing a bar once there's something to fill.
function MasteryBar({
  band,
  peak,
  effective,
  showMasteryLine = false,
}: {
  band: MasteryBand | null;
  peak: number | null;
  effective: number | null;
  showMasteryLine?: boolean;
}) {
  return (
    <div
      data-testid="mastery-bar"
      className="relative h-3 rounded-full bg-surface-subtle"
      aria-hidden="true"
    >
      {peak !== null && (
        <div
          className="absolute inset-y-0 left-0 box-border rounded-full border-2 border-dashed border-primary/40"
          style={{ width: `${peak}%` }}
        />
      )}
      {band !== null && effective !== null && (
        <div
          data-testid="mastery-bar-fill"
          className={`absolute inset-y-0 left-0 rounded-full ${BAND_BAR_CLASSES[band]}`}
          style={{ width: `${effective}%` }}
        />
      )}
      {showMasteryLine && (
        <div
          data-testid="mastery-line"
          className="absolute -top-0.5 -bottom-0.5 w-0.5 bg-heading"
          style={{ left: `${MASTERED_THRESHOLD_PCT}%` }}
        />
      )}
    </div>
  );
}

function MasteryFigures({
  topic,
  unlockedGrade,
}: {
  topic: MasteryViewEntry;
  unlockedGrade: number | null;
}) {
  if (topic.p_mastery === null) return null;
  const peak = Math.round(topic.p_mastery * 100);
  const effective =
    topic.effective_p_mastery != null ? Math.round(topic.effective_p_mastery * 100) : peak;

  if (effective === peak) {
    return <span className="text-sm text-muted">{peak}%</span>;
  }

  const tier = getExplanationCopyTier(unlockedGrade);
  return (
    <span className="flex flex-col items-end text-sm text-muted">
      <span>{effective}% (peak {peak}%)</span>
      <span className="text-xs">{tier.recoveryFraming}</span>
    </span>
  );
}

function LastPracticed({
  topicId,
  lastUpdatedAt,
}: {
  topicId: string;
  lastUpdatedAt: string;
}) {
  return (
    <span
      data-testid={`last-practiced-${topicId}`}
      className={`text-xs font-bold ${warmthClass(elapsedDays(lastUpdatedAt))}`}
    >
      Last practiced {formatElapsed(lastUpdatedAt)}
    </span>
  );
}

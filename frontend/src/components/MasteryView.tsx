import type { MasteryBand, MasteryStateEntry } from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";
import { getExplanationCopyTier } from "@/lib/explainabilityCopy";

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

export default function MasteryView({ topics, unlockedGrade = null }: MasteryViewProps) {
  return (
    <ul className="flex flex-col gap-2" data-testid="mastery-view">
      {topics.map((topic) => (
        <li
          key={topic.topic_id}
          data-testid={`mastery-topic-${topic.topic_id}`}
          className="flex flex-col gap-1 rounded-lg border border-border px-4 py-3"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium">{formatTopicId(topic.topic_id)}</span>
            {topic.status === "unknown" || topic.band === null ? (
              <span className="rounded-lg bg-muted/10 px-2 py-1 text-sm text-muted">
                Not yet assessed
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <span
                  className={`rounded-lg px-2 py-1 text-sm font-medium ${BAND_CLASSES[topic.band]}`}
                >
                  {BAND_LABEL[topic.band]}
                </span>
                <MasteryFigures topic={topic} unlockedGrade={unlockedGrade} />
              </span>
            )}
          </div>
          {topic.status !== "unknown" &&
            topic.band !== null &&
            topic.last_updated_at != null && (
              <LastPracticed topicId={topic.topic_id} lastUpdatedAt={topic.last_updated_at} />
            )}
        </li>
      ))}
    </ul>
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
    <span className="flex flex-col items-end text-sm text-muted" title={tier.recoveryFraming}>
      <span>{effective}% (peak {peak}%)</span>
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
      className={`text-xs ${warmthClass(elapsedDays(lastUpdatedAt))}`}
    >
      Last practiced {formatElapsed(lastUpdatedAt)}
    </span>
  );
}

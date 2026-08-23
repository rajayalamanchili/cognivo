import type { MasteryBand, MasteryStateEntry } from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";

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

export interface MasteryViewProps {
  topics: MasteryStateEntry[];
}

export default function MasteryView({ topics }: MasteryViewProps) {
  return (
    <ul className="flex flex-col gap-2" data-testid="mastery-view">
      {topics.map((topic) => (
        <li
          key={topic.topic_id}
          className="flex items-center justify-between rounded-lg border border-border px-4 py-3"
        >
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
              <span className="text-sm text-muted">
                {topic.p_mastery !== null ? `${Math.round(topic.p_mastery * 100)}%` : ""}
              </span>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

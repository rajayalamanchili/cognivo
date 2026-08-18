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
  struggling: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  developing: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  mastered: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
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
          className="flex items-center justify-between rounded border border-black/10 px-4 py-3 dark:border-white/10"
        >
          <span className="font-medium">{formatTopicId(topic.topic_id)}</span>
          {topic.status === "unknown" || topic.band === null ? (
            <span className="rounded bg-zinc-100 px-2 py-1 text-sm text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              Not yet assessed
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <span className={`rounded px-2 py-1 text-sm font-medium ${BAND_CLASSES[topic.band]}`}>
                {BAND_LABEL[topic.band]}
              </span>
              <span className="text-sm text-zinc-500 dark:text-zinc-400">
                {topic.p_mastery !== null ? `${Math.round(topic.p_mastery * 100)}%` : ""}
              </span>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

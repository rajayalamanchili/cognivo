import type { CareerConnectionEntry } from "@/services/api";

// Spec 039 FR-003/FR-007. Presentational only -- takes already-fetched
// career_connections entries (identical shape/derivation whether the
// caller is the demo learner's dashboard or a guardian's own learner
// view) so this one component serves both surfaces. The backend already
// omits a topic with no authored connection, and returns an empty list
// entirely when the learner's preference is off (FR-006) -- there is
// nothing for this component to filter or match itself.

export interface CareerConnectionsListProps {
  careerConnections: CareerConnectionEntry[];
}

export default function CareerConnectionsList({ careerConnections }: CareerConnectionsListProps) {
  if (careerConnections.length === 0) return null;

  return (
    <ul
      className="flex flex-col gap-1 rounded-card border border-border bg-surface p-3"
      data-testid="career-connections-list"
    >
      {careerConnections.map((entry) => (
        <li key={entry.topic_id} className="flex flex-col gap-1 rounded-[18px] px-4 py-3">
          <span className="text-[15px] font-extrabold text-heading">{entry.career}</span>
          <span className="text-[13px] text-muted">{entry.description}</span>
        </li>
      ))}
    </ul>
  );
}

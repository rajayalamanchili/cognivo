import type { RecommendationsResponse } from "@/services/api";
import { getExplanationCopyTier } from "@/lib/explainabilityCopy";

// Spec 025 User Story 6 (FR-013/FR-014): a learner-facing, softened
// rendering of the exact same Recommendation Agent report
// WeakAreaSection already shows an instructor -- reused as-is, never
// recomputed. Deliberately drops WeakAreaSection's raw percentage,
// reason-code labels, and misconception detail, none of which read as
// encouraging to a learner; keeps only the topic name and its
// next-step suggestion.

export interface WeakAreaSummaryProps {
  recommendations: RecommendationsResponse;
  unlockedGrade?: number | null;
}

export default function WeakAreaSummary({
  recommendations,
  unlockedGrade = null,
}: WeakAreaSummaryProps) {
  const { weak_areas } = recommendations;
  const tier = getExplanationCopyTier(unlockedGrade);

  if (weak_areas.length === 0) {
    return (
      <p data-testid="weak-area-summary" className="text-[15px] text-muted">
        {tier.weakAreaEmptyFraming}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3" data-testid="weak-area-summary">
      <p className="text-[15px] font-bold text-heading">{tier.weakAreaFraming}</p>
      <ul className="flex flex-col gap-2">
        {weak_areas.map((flag) => (
          <li
            key={flag.topic_id}
            data-testid={`weak-area-summary-item-${flag.topic_id}`}
            className="rounded-[16px] bg-surface-subtle px-4 py-3 text-[15px]"
          >
            <span className="font-extrabold text-heading">{flag.display_name}</span> -- try{" "}
            <strong>{flag.next_step.recommended_display_name}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

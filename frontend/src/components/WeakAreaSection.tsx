import type { DataSufficiency, RecommendationsResponse } from "@/services/api";

// Presentational only -- renders the Recommendation Agent's own report
// verbatim (FR-002): flagged weak areas, their next-step suggestions,
// and the agent's own data-sufficiency/broad-review framing, never
// paraphrased into a falsely confident summary. `DATA_SUFFICIENCY_LABEL`/
// `REASON_LABEL` are fixed 1:1 mappings from the agent's own enum values
// (mirroring MasteryView's BAND_LABEL), not invented wording.

const DATA_SUFFICIENCY_LABEL: Record<DataSufficiency, string> = {
  confident: "Confident",
  insufficient_data: "Not enough data yet to confidently flag weak areas.",
};

const REASON_LABEL: Record<string, string> = {
  direct_practice: "Direct practice recommended",
  prerequisite_gap: "Prerequisite gap identified",
  prerequisite_not_yet_assessed: "Prerequisite not yet assessed",
};

export interface WeakAreaSectionProps {
  recommendations: RecommendationsResponse;
}

export default function WeakAreaSection({ recommendations }: WeakAreaSectionProps) {
  const { data_sufficiency, broad_review_needed, weak_areas } = recommendations;

  return (
    <div className="flex flex-col gap-3" data-testid="weak-area-section">
      <p data-testid="data-sufficiency-framing" className="text-sm text-muted">
        {DATA_SUFFICIENCY_LABEL[data_sufficiency]}
      </p>
      {broad_review_needed && (
        <p
          data-testid="broad-review-framing"
          className="rounded-lg bg-warning/15 px-3 py-2 text-sm text-warning"
        >
          Broad review needed across this subject.
        </p>
      )}
      {weak_areas.length > 0 && (
        <ul className="flex flex-col gap-2">
          {weak_areas.map((flag) => (
            <li key={flag.topic_id} className="rounded-lg border border-border px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="font-medium">{flag.display_name}</span>
                <span className="text-sm text-muted">{Math.round(flag.p_mastery * 100)}%</span>
              </div>
              <p className="mt-1 text-sm text-muted">
                {REASON_LABEL[flag.next_step.reason] ?? flag.next_step.reason}: try{" "}
                <strong>{flag.next_step.recommended_display_name}</strong>
              </p>
              {flag.misconception && (
                <p
                  data-testid="misconception-enrichment"
                  className="mt-2 rounded-lg bg-muted/10 px-3 py-2 text-sm"
                >
                  Likely misconception: <strong>{flag.misconception.description}</strong>
                  <span className="text-muted">
                    {" "}
                    (based on {flag.misconception.evidence.length} answer
                    {flag.misconception.evidence.length === 1 ? "" : "s"})
                  </span>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

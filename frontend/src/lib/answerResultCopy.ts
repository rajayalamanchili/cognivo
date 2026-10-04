// Deterministic, client-side copy for the Answer Result screen's
// "YOUR MASTERY" / "WHAT TO DO NEXT" notes (027-learner-ui-redesign
// mockup gap-closing pass). Same spirit as explainabilityCopy.ts: no
// LLM, no new fetch -- every sentence is templated from fields the
// caller already has (prior/posterior mastery, band, refreshed, and
// the rubric criteria already rendered above it).

export interface AnswerResultCopyInput {
  correct: boolean;
  priorPMastery: number | null;
  posteriorPMastery: number;
  refreshed?: boolean;
  firstMissedCriterion: string | null;
}

function firstMissed(
  criteriaMissed?: string[] | null,
  stepResults?: { correct: boolean; criteria_missed: string[] }[] | null,
): string | null {
  if (criteriaMissed && criteriaMissed.length > 0) return criteriaMissed[0];
  const missedStep = stepResults?.find((step) => step.criteria_missed.length > 0);
  return missedStep?.criteria_missed[0] ?? null;
}

export function getFirstMissedCriterion(
  criteriaMissed?: string[] | null,
  stepResults?: { correct: boolean; criteria_missed: string[] }[] | null,
): string | null {
  return firstMissed(criteriaMissed, stepResults);
}

export function getMasteryNote({
  priorPMastery,
  posteriorPMastery,
  refreshed,
  firstMissedCriterion,
}: AnswerResultCopyInput): string | null {
  if (priorPMastery == null) return null;
  const delta = Math.round(posteriorPMastery * 100) - Math.round(priorPMastery * 100);

  if (refreshed) {
    return "Back above the mastery line. Your best score is unchanged -- you just topped it back up.";
  }
  if (delta > 0) {
    return `Up ${delta} point${delta === 1 ? "" : "s"}. Keep this up and you'll cross into the next band.`;
  }
  if (delta < 0) {
    const fix = firstMissedCriterion
      ? ` Fixing "${firstMissedCriterion}" is the quickest win.`
      : " Review this topic and try again.";
    return `Down ${Math.abs(delta)} point${Math.abs(delta) === 1 ? "" : "s"}.${fix}`;
  }
  return "No change this time.";
}

export function getNextNote({
  correct,
  refreshed,
  firstMissedCriterion,
}: AnswerResultCopyInput): string {
  if (correct) {
    return refreshed
      ? "This topic is locked back in -- nice work."
      : "Nice work -- keep the streak going with your next question.";
  }
  return firstMissedCriterion
    ? `Focus on: ${firstMissedCriterion}`
    : "Review this topic and give the next question a try.";
}

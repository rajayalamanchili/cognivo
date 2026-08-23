import type { AnswerResult } from "@/services/api";

// Presentational only (spec 007 FR-007/SC-004, User Story 2) -- renders
// the bare correct/incorrect outcome every question type already had,
// plus (free-text only) the rubric criteria behind that grade, so a
// learner sees more than a black-box verdict. `criteria_met`/
// `criteria_missed` are `null` for MC/numeric (contracts/api.md), so this
// section renders nothing for those question types.

export interface AnswerResultViewProps {
  result: AnswerResult;
}

export default function AnswerResultView({ result }: AnswerResultViewProps) {
  const hasCriteria =
    (result.criteria_met && result.criteria_met.length > 0) ||
    (result.criteria_missed && result.criteria_missed.length > 0);

  return (
    <div className="flex flex-col gap-4" data-testid="answer-result-view">
      <h1 className="text-2xl font-semibold">{result.correct ? "Correct!" : "Not quite."}</h1>
      <p className="text-muted">
        Topic: {result.topic_id} &mdash; now <strong>{result.band}</strong> (
        {Math.round(result.posterior_p_mastery * 100)}%)
      </p>

      {hasCriteria && (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-4">
          <p className="text-sm font-medium text-muted">Rubric criteria</p>
          <ul className="flex flex-col gap-1">
            {result.criteria_met?.map((criterion) => (
              <li key={criterion} className="flex items-start gap-2 text-sm">
                <span aria-hidden="true" className="text-success">
                  ✓
                </span>
                <span>{criterion}</span>
              </li>
            ))}
            {result.criteria_missed?.map((criterion) => (
              <li key={criterion} className="flex items-start gap-2 text-sm">
                <span aria-hidden="true" className="text-error">
                  ✗
                </span>
                <span>{criterion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

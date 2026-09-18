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
  const hasStepResults = result.step_results !== null && result.step_results.length > 0;

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

      {hasStepResults && (
        <div
          className="flex flex-col gap-3 rounded-lg border border-border p-4"
          data-testid="step-results"
        >
          <p className="text-sm font-medium text-muted">Step-by-step result</p>
          <ul className="flex flex-col gap-2">
            {result.step_results?.map((step) => (
              <li key={step.step_index} className="flex flex-col gap-1">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span
                    aria-hidden="true"
                    className={step.correct ? "text-success" : "text-error"}
                  >
                    {step.correct ? "✓" : "✗"}
                  </span>
                  <span>Step {step.step_index + 1}</span>
                </div>
                <ul className="ml-6 flex flex-col gap-1">
                  {step.criteria_met.map((criterion) => (
                    <li key={criterion} className="flex items-start gap-2 text-sm">
                      <span aria-hidden="true" className="text-success">
                        ✓
                      </span>
                      <span>{criterion}</span>
                    </li>
                  ))}
                  {step.criteria_missed.map((criterion) => (
                    <li key={criterion} className="flex items-start gap-2 text-sm">
                      <span aria-hidden="true" className="text-error">
                        ✗
                      </span>
                      <span>{criterion}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

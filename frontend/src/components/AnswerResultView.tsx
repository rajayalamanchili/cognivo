import type { AnswerResult } from "@/services/api";

// Presentational only (spec 007 FR-007/SC-004, User Story 2) -- renders
// the bare correct/incorrect outcome every question type already had,
// plus (free-text only) the rubric criteria behind that grade, so a
// learner sees more than a black-box verdict. `criteria_met`/
// `criteria_missed`/`step_results` are `null` or absent entirely for
// MC/numeric (contracts/api.md), so this section renders nothing for
// those question types.

// Spec 025 User Story 3: narrowed to only the fields this component
// actually renders, so a quiz summary's reconstructed per-question
// result (QuizAnswerResultEntry -- missing graduated_score/grading_
// logic_version/first_diverging_step_index, which this component never
// used anyway) satisfies this type without padding in unused fields.
export type AnswerResultViewData = Pick<
  AnswerResult,
  "correct" | "topic_id" | "posterior_p_mastery" | "band" | "criteria_met" | "criteria_missed" | "step_results"
>;

export interface AnswerResultViewProps {
  result: AnswerResultViewData;
}

export default function AnswerResultView({ result }: AnswerResultViewProps) {
  const hasCriteria =
    (result.criteria_met && result.criteria_met.length > 0) ||
    (result.criteria_missed && result.criteria_missed.length > 0);
  const hasStepResults = !!result.step_results && result.step_results.length > 0;

  const heroTone = result.correct
    ? "bg-success/15 text-success"
    : "bg-warning/15 text-warning";

  return (
    <div className="flex flex-col gap-5" data-testid="answer-result-view">
      <section className={`flex items-center gap-5 rounded-card px-8 py-7 ${heroTone}`}>
        <div
          aria-hidden="true"
          className={`flex h-[52px] w-[52px] flex-shrink-0 items-center justify-center rounded-full text-2xl font-bold ${result.correct ? "bg-success text-white" : "bg-warning text-white"}`}
        >
          {result.correct ? "✓" : "~"}
        </div>
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-[30px] font-bold leading-tight">
            {result.correct ? "Correct!" : "Not quite."}
          </h1>
          <p>
            Topic: {result.topic_id}
            {result.band != null && (
              <>
                {" "}
                &mdash; now <strong>{result.band}</strong> (
                {Math.round(result.posterior_p_mastery * 100)}%)
              </>
            )}
          </p>
        </div>
      </section>

      {hasCriteria && (
        <div className="flex flex-col gap-3 rounded-card border border-border bg-surface p-7">
          <p className="text-sm font-bold text-heading">Rubric criteria</p>
          <ul className="flex flex-col gap-2">
            {result.criteria_met?.map((criterion) => (
              <li key={criterion} className="flex items-start gap-3 text-[15px]">
                <span className="flex-shrink-0 rounded-full bg-success/15 px-2.5 py-0.5 text-xs font-bold text-success">
                  Met
                </span>
                <span>{criterion}</span>
              </li>
            ))}
            {result.criteria_missed?.map((criterion) => (
              <li key={criterion} className="flex items-start gap-3 text-[15px]">
                <span className="flex-shrink-0 rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-bold text-warning">
                  Missed
                </span>
                <span>{criterion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasStepResults && (
        <div
          className="flex flex-col gap-3 rounded-card border border-border bg-surface p-7"
          data-testid="step-results"
        >
          <p className="text-sm font-bold text-heading">Step-by-step result</p>
          <ul className="flex flex-col gap-3">
            {result.step_results?.map((step) => (
              <li
                key={step.step_index}
                className="flex flex-col gap-2 rounded-[16px] bg-surface-subtle p-4"
              >
                <div className="flex items-center gap-2 text-sm font-bold text-heading">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${step.correct ? "bg-success/15 text-success" : "bg-warning/15 text-warning"}`}
                  >
                    {step.correct ? "Met" : "Missed"}
                  </span>
                  <span>Step {step.step_index + 1}</span>
                </div>
                <ul className="ml-2 flex flex-col gap-1">
                  {step.criteria_met.map((criterion) => (
                    <li key={criterion} className="flex items-start gap-3 text-[15px]">
                      <span className="flex-shrink-0 rounded-full bg-success/15 px-2.5 py-0.5 text-xs font-bold text-success">
                        Met
                      </span>
                      <span>{criterion}</span>
                    </li>
                  ))}
                  {step.criteria_missed.map((criterion) => (
                    <li key={criterion} className="flex items-start gap-3 text-[15px]">
                      <span className="flex-shrink-0 rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-bold text-warning">
                        Missed
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

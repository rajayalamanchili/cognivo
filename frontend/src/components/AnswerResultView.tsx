import type { ReactNode } from "react";
import type { AnswerResult } from "@/services/api";
import { getFirstMissedCriterion, getMasteryNote, getNextNote } from "@/lib/answerResultCopy";

// Same 0.7 raw-score cutoff `mastery_band_for` (backend/src/models/
// enums.py) uses for "mastered" -- a fixed global constant, not
// per-classroom configurable, so it's safe to mirror here purely to
// place the mastery-line tick mark on the bar below.
const MASTERED_THRESHOLD_PCT = 70;

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
  | "correct"
  | "topic_id"
  | "prior_p_mastery"
  | "posterior_p_mastery"
  | "band"
  | "criteria_met"
  | "criteria_missed"
  | "step_results"
> & {
  // Optional: QuizAnswerResultEntry (spec 025 User Story 3) has no
  // `refreshed` either, same reason it has no `band` -- not derivable
  // from a reconstructed historical audit trail alone.
  refreshed?: boolean;
};

export interface AnswerResultViewProps {
  result: AnswerResultViewData;
  // Mockup's "WHAT TO DO NEXT" tile holds the page's own next-step
  // buttons (stacked, pinned to the tile's bottom via `mt-auto`) --
  // left as a slot rather than built into this component because
  // placement/quiz-summary (spec 025 User Story 3) render this same
  // component in an end-of-session list, where a "next question" nav
  // action per list item doesn't make sense (only practice-flow's
  // single immediate-feedback screen passes this).
  actions?: ReactNode;
}

export default function AnswerResultView({ result, actions }: AnswerResultViewProps) {
  const hasCriteria =
    (result.criteria_met && result.criteria_met.length > 0) ||
    (result.criteria_missed && result.criteria_missed.length > 0);
  const hasStepResults = !!result.step_results && result.step_results.length > 0;

  const firstMissedCriterion = getFirstMissedCriterion(result.criteria_missed, result.step_results);
  const copyInput = {
    correct: result.correct,
    priorPMastery: result.prior_p_mastery,
    posteriorPMastery: result.posterior_p_mastery,
    refreshed: result.refreshed,
    firstMissedCriterion,
  };
  const masteryNote = getMasteryNote(copyInput);
  const nextNote = getNextNote(copyInput);

  const heroTone = result.correct
    ? "bg-success/15 text-success"
    : "bg-warning/15 text-warning";

  return (
    <div className="flex flex-col gap-5" data-testid="answer-result-view">
      <section className={`flex items-center gap-5 rounded-card px-8 py-7 ${heroTone}`}>
        <div
          aria-hidden="true"
          className={`flex h-[60px] w-[60px] flex-shrink-0 items-center justify-center rounded-full text-white ${result.correct ? "bg-success" : "bg-warning"}`}
        >
          {result.correct ? (
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          ) : (
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5" />
              <path d="m5 12 7-7 7 7" />
            </svg>
          )}
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

      <div className={`grid grid-cols-1 gap-5 ${result.prior_p_mastery != null ? "sm:grid-cols-2" : ""}`}>
        {result.prior_p_mastery != null && (
          <section
            aria-labelledby="mastery-change-h"
            className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6"
          >
            <h2 id="mastery-change-h" className="text-xs font-extrabold tracking-[0.08em] text-primary">
              YOUR MASTERY
            </h2>
            <div className="flex items-baseline gap-3">
              <span className="font-heading text-[22px] font-bold text-muted">
                {Math.round(result.prior_p_mastery * 100)}%
              </span>
              <span aria-hidden="true" className="text-muted">
                →
              </span>
              <span className="font-heading text-[36px] font-bold leading-none text-heading">
                {Math.round(result.posterior_p_mastery * 100)}%
              </span>
            </div>
            <div className="relative h-3 rounded-full bg-surface-subtle" aria-hidden="true">
              <div
                className="absolute inset-y-0 left-0 rounded-full bg-primary/40"
                style={{ width: `${Math.round(result.prior_p_mastery * 100)}%` }}
              />
              <div
                className="absolute inset-y-0 left-0 rounded-full bg-primary"
                style={{ width: `${Math.round(result.posterior_p_mastery * 100)}%` }}
              />
              <div
                data-testid="mastery-line"
                className="absolute -top-1 -bottom-1 w-0.5 bg-heading"
                style={{ left: `${MASTERED_THRESHOLD_PCT}%` }}
              />
            </div>
            {masteryNote && <p className="text-[15px] text-muted">{masteryNote}</p>}
          </section>
        )}

        <section
          aria-labelledby="next-h"
          className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6"
        >
          <h2 id="next-h" className="text-xs font-extrabold tracking-[0.08em] text-primary">
            WHAT TO DO NEXT
          </h2>
          <p className="text-base font-semibold text-heading">{nextNote}</p>
          {actions && <div className="mt-auto flex flex-col gap-2.5">{actions}</div>}
        </section>
      </div>

      {hasCriteria && (
        <div className="flex flex-col gap-3 rounded-card border border-border bg-surface p-7">
          <h2 className="font-heading text-xl font-bold text-heading">How this was graded</h2>
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
          <h2 className="font-heading text-xl font-bold text-heading">How this was graded</h2>
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

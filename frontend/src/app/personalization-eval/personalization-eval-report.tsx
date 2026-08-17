"use client";

import { useEffect, useState } from "react";
import { getEvaluationReport, type EvaluationReport } from "@/services/api";

type Phase = "loading" | "loaded" | "error";

// Report data uses kebab-case/snake_case identifiers (e.g. "cold-start",
// "fixed_order") internally -- humanize them for a non-technical reader
// (FR-012; copy-reviewed per quickstart.md step 7 notes).
function humanize(slug: string): string {
  return slug
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function PersonalizationEvalReport() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEvaluationReport()
      .then((result) => {
        if (cancelled) return;
        setReport(result);
        setPhase("loaded");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (phase === "loading") {
    return <p className="p-8">Loading evaluation results&hellip;</p>;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-red-600">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  if (!report?.published) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 p-8">
        <h1 className="text-2xl font-semibold">Personalization Evidence</h1>
        <p>
          No evaluation has run yet. Check back once the evaluation harness has been run and its
          results published.
        </p>
      </div>
    );
  }

  const aggregate = report.aggregate ?? {};
  const sequencing = aggregate.sequencing;
  const random = aggregate.random;
  const conditionNames = Object.keys(aggregate);

  const reductionPercent =
    sequencing && random && random.mean > 0
      ? Math.round(((random.mean - sequencing.mean) / random.mean) * 100)
      : null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Personalization Evidence</h1>

      {sequencing && random ? (
        <p className="text-lg">
          On average, our AI-personalized question order reached full mastery in{" "}
          <strong>{sequencing.mean.toFixed(1)} questions</strong> &mdash; a random question order
          needed <strong>{random.mean.toFixed(1)} questions</strong>
          {reductionPercent !== null && reductionPercent > 0
            ? ` (${reductionPercent}% fewer questions).`
            : "."}
        </p>
      ) : (
        <p>Not enough data to compare the sequencing and random conditions yet.</p>
      )}

      <p className="text-sm text-gray-600">
        Covering {report.profiles?.length ?? 0} learner profile
        {report.profiles?.length === 1 ? "" : "s"}
        {report.profiles?.length
          ? ` (${report.profiles.map(humanize).join(", ")})`
          : ""} across {report.subjects?.length ?? 0} subject
        {report.subjects?.length === 1 ? "" : "s"}
        {report.subjects?.length ? ` (${report.subjects.map(humanize).join(", ")})` : ""}.
      </p>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            <th className="pr-4 pb-2">Condition</th>
            <th className="pr-4 pb-2">Mean questions</th>
            <th className="pr-4 pb-2">Median</th>
            <th className="pb-2">Non-converged</th>
          </tr>
        </thead>
        <tbody>
          {conditionNames.map((condition) => {
            const stats = aggregate[condition];
            return (
              <tr key={condition}>
                <td className="pr-4">{humanize(condition)}</td>
                <td className="pr-4">{stats.mean.toFixed(1)}</td>
                <td className="pr-4">{stats.median.toFixed(1)}</td>
                <td>
                  {stats.non_converged_count}/{stats.n} (
                  {(stats.non_converged_rate * 100).toFixed(0)}%)
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

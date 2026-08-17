import { Suspense } from "react";
import PersonalizationEvalReport from "./personalization-eval-report";

export default function PersonalizationEvalPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading evaluation results&hellip;</p>}>
      <PersonalizationEvalReport />
    </Suspense>
  );
}

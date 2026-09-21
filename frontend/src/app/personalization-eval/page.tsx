import { Suspense } from "react";
import PersonalizationEvalReport from "./personalization-eval-report";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function PersonalizationEvalPage() {
  return (
    <Suspense
      fallback={<LoadingIndicator message="Loading evaluation results…" variant="professional" />}
    >
      <PersonalizationEvalReport />
    </Suspense>
  );
}

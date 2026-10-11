import { Suspense } from "react";
import AssignmentFlow from "./assignment-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function AssignmentPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Finding your quiz…" />}>
      <AssignmentFlow />
    </Suspense>
  );
}

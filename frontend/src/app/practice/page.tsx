import { Suspense } from "react";
import PracticeFlow from "./practice-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function PracticePage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Finding your next question…" />}>
      <PracticeFlow />
    </Suspense>
  );
}

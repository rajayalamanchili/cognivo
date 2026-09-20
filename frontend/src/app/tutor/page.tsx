import { Suspense } from "react";
import TutorFlow from "./tutor-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function TutorPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Waking up your tutor…" />}>
      <TutorFlow />
    </Suspense>
  );
}

import { Suspense } from "react";
import MasteryFlow from "./mastery-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function MasteryPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Gathering your progress…" />}>
      <MasteryFlow />
    </Suspense>
  );
}

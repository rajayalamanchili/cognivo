import { Suspense } from "react";
import ReviewFlow from "./review-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function InstructorReviewPage() {
  return (
    <Suspense
      fallback={<LoadingIndicator message="Loading review queue…" variant="professional" />}
    >
      <ReviewFlow />
    </Suspense>
  );
}

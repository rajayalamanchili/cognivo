import { Suspense } from "react";
import ReviewFlow from "./review-flow";

export default function InstructorReviewPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading review queue&hellip;</p>}>
      <ReviewFlow />
    </Suspense>
  );
}

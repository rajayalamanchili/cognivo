import { Suspense } from "react";
import TutorFlow from "./tutor-flow";

export default function TutorPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading&hellip;</p>}>
      <TutorFlow />
    </Suspense>
  );
}

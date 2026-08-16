import { Suspense } from "react";
import PracticeFlow from "./practice-flow";

export default function PracticePage() {
  return (
    <Suspense fallback={<p className="p-8">Loading next question&hellip;</p>}>
      <PracticeFlow />
    </Suspense>
  );
}

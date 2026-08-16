import { Suspense } from "react";
import MasteryFlow from "./mastery-flow";

export default function MasteryPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading mastery state&hellip;</p>}>
      <MasteryFlow />
    </Suspense>
  );
}

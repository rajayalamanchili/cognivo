import { Suspense } from "react";
import PlacementFlow from "./placement-flow";

export default function PlacementPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading placement questions&hellip;</p>}>
      <PlacementFlow />
    </Suspense>
  );
}

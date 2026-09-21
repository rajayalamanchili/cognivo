import { Suspense } from "react";
import PlacementFlow from "./placement-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function PlacementPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Preparing your first questions…" />}>
      <PlacementFlow />
    </Suspense>
  );
}

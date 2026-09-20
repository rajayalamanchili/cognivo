import { Suspense } from "react";
import RostersFlow from "./rosters-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function InstructorRostersPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Loading rosters…" variant="professional" />}>
      <RostersFlow />
    </Suspense>
  );
}

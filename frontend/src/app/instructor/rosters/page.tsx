import { Suspense } from "react";
import RostersFlow from "./rosters-flow";

export default function InstructorRostersPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading rosters&hellip;</p>}>
      <RostersFlow />
    </Suspense>
  );
}

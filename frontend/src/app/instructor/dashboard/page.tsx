import { Suspense } from "react";
import InstructorDashboardFlow from "./instructor-dashboard-flow";

export default function InstructorDashboardPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading dashboard&hellip;</p>}>
      <InstructorDashboardFlow />
    </Suspense>
  );
}

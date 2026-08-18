import { Suspense } from "react";
import DashboardFlow from "./dashboard-flow";

export default function DashboardPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading dashboard&hellip;</p>}>
      <DashboardFlow />
    </Suspense>
  );
}

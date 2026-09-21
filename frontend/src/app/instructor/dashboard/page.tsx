import { Suspense } from "react";
import InstructorDashboardFlow from "./instructor-dashboard-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function InstructorDashboardPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Loading dashboard…" variant="professional" />}>
      <InstructorDashboardFlow />
    </Suspense>
  );
}

import { Suspense } from "react";
import DashboardFlow from "./dashboard-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function DashboardPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Getting your dashboard ready…" />}>
      <DashboardFlow />
    </Suspense>
  );
}

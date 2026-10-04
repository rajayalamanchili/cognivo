import { Suspense } from "react";
import SettingsFlow from "./settings-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function SettingsPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Loading your settings…" />}>
      <SettingsFlow />
    </Suspense>
  );
}

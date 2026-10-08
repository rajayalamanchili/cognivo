import { Suspense } from "react";
import InstructorSettingsFlow from "./instructor-settings-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function InstructorSettingsPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Loading settings…" variant="professional" />}>
      <InstructorSettingsFlow />
    </Suspense>
  );
}

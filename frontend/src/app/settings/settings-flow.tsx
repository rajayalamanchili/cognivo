"use client";

import { useEffect, useState } from "react";
import { getDemoLearner } from "@/services/api";
import CareerConnectionsToggle from "@/components/CareerConnectionsToggle";
import LoadingIndicator from "@/components/LoadingIndicator";

// Spec 039 FR-011. Demo-learner-only, no explicit route gate -- same
// precedent as /dashboard and /mastery, which both resolve the demo
// learner's id via getDemoLearner() unconditionally rather than
// checking a session first.
export default function SettingsFlow() {
  const [learnerId, setLearnerId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoLearner().then((learner) => {
      if (!cancelled) setLearnerId(learner.learner_id);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (learnerId === null) {
    return <LoadingIndicator message="Loading your settings…" />;
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <CareerConnectionsToggle learnerId={learnerId} />
    </div>
  );
}

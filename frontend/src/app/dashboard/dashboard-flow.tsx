"use client";

import { useEffect, useState } from "react";
import { getDemoLearner, getSubjects, type SubjectSummary } from "@/services/api";
import DashboardSubjectSection from "@/components/DashboardSubjectSection";

type Phase = "loading" | "loaded" | "error";

// Top-level phase covers only "did we get the subject list at all" --
// each subject section's mastery/weak-area/path data is fetched
// independently starting in Phase 3+ (research.md §5, FR-007/FR-008).
export default function DashboardFlow() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getDemoLearner(), getSubjects()])
      .then(([, subjectsResponse]) => {
        if (cancelled) return;
        setSubjects(subjectsResponse.subjects);
        setPhase("loaded");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (phase === "loading") {
    return <p className="p-8">Loading dashboard&hellip;</p>;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-red-600">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Your Dashboard</h1>
      {subjects.map((subject) => (
        <DashboardSubjectSection
          key={subject.subject_id}
          subjectId={subject.subject_id}
          displayName={subject.display_name}
        />
      ))}
    </div>
  );
}

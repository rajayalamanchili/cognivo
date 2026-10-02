"use client";

import { useEffect, useState } from "react";
import { getDemoLearner, getSubjects, type SubjectSummary } from "@/services/api";
import DashboardSubjectSection from "@/components/DashboardSubjectSection";
import LoadingIndicator from "@/components/LoadingIndicator";

type Phase = "loading" | "loaded" | "error";

// Top-level phase covers only "did we get the subject list at all" --
// each subject section's mastery/weak-area/path data is fetched
// independently starting in Phase 3+ (research.md §5, FR-007/FR-008).
export default function DashboardFlow() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // 027-learner-ui-redesign, second pass: a subject-pill toggle showing
  // one subject at a time, matching the mockup -- purely a display
  // choice over the same `subjects` list already fetched below, no new
  // data and no change to what each DashboardSubjectSection renders.
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getDemoLearner(), getSubjects()])
      .then(([learner, subjectsResponse]) => {
        if (cancelled) return;
        setLearnerId(learner.learner_id);
        setSubjects(subjectsResponse.subjects);
        setSelectedSubjectId(subjectsResponse.subjects[0]?.subject_id ?? null);
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

  if (phase === "loading" || !learnerId) {
    return <LoadingIndicator message="Getting your dashboard ready…" />;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  const selectedSubject =
    subjects.find((subject) => subject.subject_id === selectedSubjectId) ?? subjects[0] ?? null;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-heading text-[32px] font-bold text-heading">Your Dashboard</h1>
        {subjects.length > 1 && (
          <div
            role="group"
            aria-label="Subject"
            className="flex gap-1 rounded-full border border-border bg-surface p-1"
          >
            {subjects.map((subject) => {
              const active = subject.subject_id === selectedSubject?.subject_id;
              return (
                <button
                  key={subject.subject_id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setSelectedSubjectId(subject.subject_id)}
                  className={
                    "rounded-full px-5 py-2.5 text-[15px] font-extrabold " +
                    (active ? "bg-primary text-primary-foreground" : "text-muted")
                  }
                >
                  {subject.display_name}
                </button>
              );
            })}
          </div>
        )}
      </div>
      {selectedSubject && (
        <DashboardSubjectSection
          key={selectedSubject.subject_id}
          subjectId={selectedSubject.subject_id}
          displayName={selectedSubject.display_name}
          learnerId={learnerId}
        />
      )}
    </div>
  );
}

"use client";

// One dashboard section per subject. Each of the three sub-sections
// (mastery, weak-area, path) is fetched and rendered independently
// with its own loading/loaded/error phase, so a failure in one never
// blocks the others (FR-007, FR-008) -- US2/US3 add the weak-area and
// path slots' own fetches in later phases.

import { useEffect, useState } from "react";
import { getMasteryState, type MasteryTopicEntry } from "@/services/api";
import MasteryView from "@/components/MasteryView";

type SectionPhase = "loading" | "loaded" | "error";

export interface DashboardSubjectSectionProps {
  subjectId: string;
  displayName: string;
  learnerId: string;
}

export default function DashboardSubjectSection({
  subjectId,
  displayName,
  learnerId,
}: DashboardSubjectSectionProps) {
  const [masteryPhase, setMasteryPhase] = useState<SectionPhase>("loading");
  const [masteryTopics, setMasteryTopics] = useState<MasteryTopicEntry[]>([]);
  const [masteryError, setMasteryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Fetched fresh on every mount, never cached (FR-006).
    getMasteryState(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setMasteryTopics(result.topics);
        setMasteryPhase("loaded");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setMasteryError(error instanceof Error ? error.message : String(error));
        setMasteryPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  return (
    <section
      data-testid={`dashboard-subject-section-${subjectId}`}
      className="flex flex-col gap-4 rounded border border-black/10 p-6 dark:border-white/10"
    >
      <h2 className="text-xl font-semibold">{displayName}</h2>
      <div data-testid="dashboard-mastery-slot">
        {masteryPhase === "loading" && <p>Loading mastery state&hellip;</p>}
        {masteryPhase === "error" && (
          <p className="text-red-600">Couldn&rsquo;t load mastery state: {masteryError}</p>
        )}
        {masteryPhase === "loaded" && <MasteryView topics={masteryTopics} />}
      </div>
      <div data-testid="dashboard-weak-area-slot" />
      <div data-testid="dashboard-path-slot" />
    </section>
  );
}

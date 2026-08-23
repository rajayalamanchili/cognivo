"use client";

// One dashboard section per subject. Each of the three sub-sections
// (mastery, weak-area, path) is fetched and rendered independently
// with its own loading/loaded/error phase, so a failure in one never
// blocks the others (FR-007, FR-008) -- US2/US3 add the weak-area and
// path slots' own fetches in later phases.

import { useEffect, useState } from "react";
import {
  getMasteryState,
  getRecommendations,
  getTopicPriorityPreview,
  type MasteryTopicEntry,
  type RecommendationsResponse,
  type TopicPriorityPreview,
} from "@/services/api";
import MasteryView from "@/components/MasteryView";
import WeakAreaSection from "@/components/WeakAreaSection";
import PathVisualization from "@/components/PathVisualization";

type SectionPhase = "loading" | "loaded" | "error";

// Shared failure-state presentation (FR-010): every sub-section's
// "couldn't load" state uses this same pattern rather than an
// independently-styled variant, and none auto-retries within a page load.
function CouldntLoad({ what }: { what: string }) {
  return <p className="text-error">Couldn&rsquo;t load {what}.</p>;
}

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

  const [weakAreaPhase, setWeakAreaPhase] = useState<SectionPhase>("loading");
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);

  const [pathPhase, setPathPhase] = useState<SectionPhase>("loading");
  const [pathPreview, setPathPreview] = useState<TopicPriorityPreview | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Fetched fresh on every mount, never cached (FR-006).
    getMasteryState(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setMasteryTopics(result.topics);
        setMasteryPhase("loaded");
      })
      .catch(() => {
        if (cancelled) return;
        setMasteryPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  useEffect(() => {
    let cancelled = false;
    // Independent of the mastery fetch above: a failure here must not
    // affect the mastery view (FR-007), and vice versa.
    getRecommendations(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setRecommendations(result);
        setWeakAreaPhase("loaded");
      })
      .catch(() => {
        if (cancelled) return;
        setWeakAreaPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  useEffect(() => {
    let cancelled = false;
    // Independent of the mastery/weak-area fetches above: a failure
    // here must not affect either of them (FR-008).
    getTopicPriorityPreview(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setPathPreview(result);
        setPathPhase("loaded");
      })
      .catch(() => {
        if (cancelled) return;
        setPathPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  return (
    <section
      data-testid={`dashboard-subject-section-${subjectId}`}
      className="flex flex-col gap-4 rounded-lg border border-border p-6"
    >
      <h2 className="text-xl font-semibold">{displayName}</h2>
      <div data-testid="dashboard-mastery-slot">
        {masteryPhase === "loading" && <p>Loading mastery state&hellip;</p>}
        {masteryPhase === "error" && <CouldntLoad what="mastery state" />}
        {masteryPhase === "loaded" && <MasteryView topics={masteryTopics} />}
      </div>
      <div data-testid="dashboard-weak-area-slot">
        {weakAreaPhase === "loading" && <p>Loading weak areas&hellip;</p>}
        {weakAreaPhase === "error" && <CouldntLoad what="weak-area report" />}
        {weakAreaPhase === "loaded" && recommendations && (
          <WeakAreaSection recommendations={recommendations} />
        )}
      </div>
      <div data-testid="dashboard-path-slot">
        {pathPhase === "loading" && <p>Loading path&hellip;</p>}
        {pathPhase === "error" && <CouldntLoad what="path visualization" />}
        {pathPhase === "loaded" && pathPreview && (
          <PathVisualization
            assessedTopics={masteryTopics.filter((topic) => topic.status === "scored")}
            preview={pathPreview}
          />
        )}
      </div>
    </section>
  );
}

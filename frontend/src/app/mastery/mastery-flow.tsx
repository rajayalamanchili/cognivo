"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  getDemoLearner,
  getMasteryHistory,
  getMasteryState,
  type MasteryHistoryPoint,
  type MasteryTopicEntry,
} from "@/services/api";
import MasteryView from "@/components/MasteryView";
import MasteryTrend from "@/components/MasteryTrend";
import LoadingIndicator from "@/components/LoadingIndicator";
import { formatTopicId } from "@/lib/format-topic-id";

type Phase = "loading" | "loaded" | "error";

export default function MasteryFlow() {
  const searchParams = useSearchParams();
  const subjectId = searchParams.get("subject") ?? "algebra-1";

  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [topics, setTopics] = useState<MasteryTopicEntry[]>([]);
  const [unlockedGrade, setUnlockedGrade] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Spec 025 FR-012: fetched on demand per topic, not eagerly for every
  // topic on page load -- a learner may never look at most of them.
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [trendPoints, setTrendPoints] = useState<MasteryHistoryPoint[]>([]);

  useEffect(() => {
    let cancelled = false;
    getDemoLearner()
      .then((learner) => {
        if (cancelled) return null;
        setLearnerId(learner.learner_id);
        return getMasteryState(learner.learner_id, subjectId);
      })
      .then((result) => {
        if (cancelled || result === null) return;
        setTopics(result.topics);
        setUnlockedGrade(result.unlocked_grade);
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
  }, [subjectId]);

  useEffect(() => {
    // `MasteryTrend` is only rendered while `selectedTopicId` is set, so
    // stale `trendPoints` from a previous selection are never shown --
    // no reset needed when there's nothing selected.
    if (!learnerId || !selectedTopicId) return;
    let cancelled = false;
    getMasteryHistory(learnerId, subjectId, selectedTopicId)
      .then((result) => {
        if (!cancelled) setTrendPoints(result.points);
      })
      .catch(() => {
        if (!cancelled) setTrendPoints([]);
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId, selectedTopicId]);

  if (phase === "loading") {
    return <LoadingIndicator message="Gathering your progress…" />;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  // FR-012 edge case: an "unknown" topic has no mastery history to show.
  const scoredTopics = topics.filter((topic) => topic.status !== "unknown");

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Your Mastery</h1>
      <MasteryView topics={topics} unlockedGrade={unlockedGrade} />
      {scoredTopics.length > 0 && (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm font-medium">
            See a topic&apos;s trend over time
            <select
              value={selectedTopicId ?? ""}
              onChange={(event) => setSelectedTopicId(event.target.value || null)}
              className="rounded-lg border border-border px-3 py-2"
            >
              <option value="">Choose a topic</option>
              {scoredTopics.map((topic) => (
                <option key={topic.topic_id} value={topic.topic_id}>
                  {formatTopicId(topic.topic_id)}
                </option>
              ))}
            </select>
          </label>
          {selectedTopicId && <MasteryTrend points={trendPoints} />}
        </div>
      )}
    </div>
  );
}

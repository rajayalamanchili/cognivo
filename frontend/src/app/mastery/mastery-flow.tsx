"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getDemoLearner, getMasteryState, type MasteryTopicEntry } from "@/services/api";
import MasteryView from "@/components/MasteryView";

type Phase = "loading" | "loaded" | "error";

export default function MasteryFlow() {
  const searchParams = useSearchParams();
  const subjectId = searchParams.get("subject") ?? "algebra-1";

  const [phase, setPhase] = useState<Phase>("loading");
  const [topics, setTopics] = useState<MasteryTopicEntry[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoLearner()
      .then((learner) => getMasteryState(learner.learner_id, subjectId))
      .then((result) => {
        if (cancelled) return;
        setTopics(result.topics);
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

  if (phase === "loading") {
    return <p className="p-8">Loading mastery state&hellip;</p>;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Your Mastery</h1>
      <MasteryView topics={topics} />
    </div>
  );
}

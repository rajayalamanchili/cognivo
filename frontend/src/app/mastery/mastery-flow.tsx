"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  getDemoLearner,
  getMasteryHistory,
  getMasteryState,
  getSubjects,
  type MasteryHistoryPoint,
  type MasteryTopicEntry,
} from "@/services/api";
import { getRealLearnerSession } from "@/lib/visitor-state";
import MasteryView from "@/components/MasteryView";
import MasteryTrend from "@/components/MasteryTrend";
import LoadingIndicator from "@/components/LoadingIndicator";
import { formatTopicId } from "@/lib/format-topic-id";

type Phase = "loading" | "loaded" | "error";

// Same 0.7 cutoff mirrored in MasteryView/AnswerResultView/MasteryTrend.
const MASTERED_THRESHOLD_PCT = 70;

// Mastery.dc.html mockup's four status categories, derived entirely
// from fields the mastery-state response already carries (no new
// data): "unknown" status, or peak-vs-effective compared against the
// same 0.7 cutoff the backend itself uses for "mastered".
type TopicStatus = "not-started" | "refresh-due" | "mastered" | "in-progress";

function statusFor(topic: MasteryTopicEntry): TopicStatus {
  if (topic.status === "unknown" || topic.p_mastery === null) return "not-started";
  const peak = Math.round(topic.p_mastery * 100);
  const effective =
    topic.effective_p_mastery != null ? Math.round(topic.effective_p_mastery * 100) : peak;
  if (peak >= MASTERED_THRESHOLD_PCT && effective < MASTERED_THRESHOLD_PCT) return "refresh-due";
  if (effective >= MASTERED_THRESHOLD_PCT) return "mastered";
  return "in-progress";
}

const STATUS_COPY: Record<
  TopicStatus,
  { label: string; noteClass: string; cta: string }
> = {
  "not-started": {
    label: "Not started",
    noteClass: "bg-surface-subtle text-muted",
    cta: "Start practicing",
  },
  "refresh-due": {
    label: "Refresh due",
    noteClass: "bg-warning/15 text-warning",
    cta: "Refresh this topic",
  },
  mastered: {
    label: "Mastered",
    noteClass: "bg-primary-subtle text-heading",
    cta: "Practice anyway",
  },
  "in-progress": {
    label: "In progress",
    noteClass: "bg-primary/10 text-heading",
    cta: "Continue practicing",
  },
};

function noteFor(topic: MasteryTopicEntry, status: TopicStatus): string {
  switch (status) {
    case "not-started":
      return "Not yet assessed -- practice to get your first mastery estimate.";
    case "refresh-due":
      return "It's been a while, so a little has faded. A few questions should bring it right back to your best.";
    case "mastered":
      return "Locked in. It'll stay strong with occasional practice -- we'll let you know if a refresh is due.";
    case "in-progress": {
      const effective =
        topic.effective_p_mastery != null
          ? Math.round(topic.effective_p_mastery * 100)
          : topic.p_mastery != null
            ? Math.round(topic.p_mastery * 100)
            : 0;
      return `You're climbing -- ${Math.max(MASTERED_THRESHOLD_PCT - effective, 0)}% to the mastery line. Keep going.`;
    }
  }
}

export default function MasteryFlow() {
  const searchParams = useSearchParams();
  const subjectId = searchParams.get("subject") ?? "algebra-1";

  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [topics, setTopics] = useState<MasteryTopicEntry[]>([]);
  const [unlockedGrade, setUnlockedGrade] = useState<number | null>(null);
  const [subjectName, setSubjectName] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  // Mastery.dc.html's per-row sparkline needs every assessed topic's
  // history up front (the detail panel's own bigger chart reuses the
  // same map rather than a second fetch). A bounded fan-out -- one
  // small read-only query per topic in a subject, and a subject has at
  // most a handful -- not the kind of N+1 that scales badly here.
  const [historyByTopic, setHistoryByTopic] = useState<Record<string, MasteryHistoryPoint[]>>({});

  useEffect(() => {
    let cancelled = false;
    getSubjects()
      .then((result) => {
        if (cancelled) return;
        const match = result.subjects.find((subject) => subject.subject_id === subjectId);
        setSubjectName(match?.display_name ?? null);
      })
      .catch(() => {
        if (!cancelled) setSubjectName(null);
      });
    // spec 041 FR-016: a guardian's real-learner session resolves
    // `learnerId` here instead of the demo learner.
    const realSession = getRealLearnerSession();
    (realSession ? Promise.resolve({ learner_id: realSession.learnerId }) : getDemoLearner())
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

  // Default to the mockup's always-something-selected detail panel:
  // prefer the first assessed topic, falling back to the very first
  // topic if none are assessed yet. Derived, not stored -- avoids a
  // setState-in-effect just to seed an initial value.
  const effectiveSelectedTopicId =
    selectedTopicId ??
    (topics.find((topic) => topic.status !== "unknown") ?? topics[0])?.topic_id ??
    null;

  useEffect(() => {
    if (!learnerId || topics.length === 0) return;
    let cancelled = false;
    const scoredTopics = topics.filter((topic) => topic.status !== "unknown");
    Promise.all(
      scoredTopics.map((topic) =>
        getMasteryHistory(learnerId, subjectId, topic.topic_id)
          .then((result) => [topic.topic_id, result.points] as const)
          .catch(() => [topic.topic_id, []] as const)
      )
    ).then((entries) => {
      if (!cancelled) setHistoryByTopic(Object.fromEntries(entries));
    });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId, topics]);

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

  const selected = topics.find((topic) => topic.topic_id === effectiveSelectedTopicId) ?? null;
  const selectedStatus = selected ? statusFor(selected) : null;
  const trendPoints = effectiveSelectedTopicId ? (historyByTopic[effectiveSelectedTopicId] ?? []) : [];

  return (
    <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-6 p-8">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          {subjectName && (
            <p className="m-0 text-xs font-extrabold tracking-[0.08em] text-primary">
              {subjectName.toUpperCase()} &middot; {topics.length} TOPICS
            </p>
          )}
          <h1 className="font-heading text-[40px] font-bold leading-tight text-heading">
            Your mastery
          </h1>
          <p className="mt-1.5 max-w-[640px] text-[17px] text-muted">
            Mastery fades a little when a topic sits untouched -- that&apos;s normal. A short
            refresh brings it right back.
          </p>
        </div>
        <div
          className="flex flex-wrap gap-5 text-sm font-bold text-muted"
          aria-label="Legend"
        >
          <span className="flex items-center gap-2">
            <span className="h-2.5 w-7 rounded-full bg-primary" />
            Retained now
          </span>
          <span className="flex items-center gap-2">
            <span className="box-border h-2.5 w-7 rounded-full border-2 border-dashed border-primary/40" />
            Your best
          </span>
          <span className="flex items-center gap-2">
            <span className="h-4 w-0.5 bg-heading" />
            Mastery line ({MASTERED_THRESHOLD_PCT}%)
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1.55fr_1fr]">
        <MasteryView
          topics={topics}
          unlockedGrade={unlockedGrade}
          selectedTopicId={effectiveSelectedTopicId}
          onSelectTopic={setSelectedTopicId}
          showMasteryLine
          historyByTopic={historyByTopic}
        />

        {selected && selectedStatus && (
          <aside className="flex flex-col gap-5 rounded-card border border-border bg-surface p-7 lg:sticky lg:top-6">
            <div>
              <span
                className={`inline-block rounded-full px-3 py-0.5 text-xs font-extrabold ${STATUS_COPY[selectedStatus].noteClass}`}
              >
                {STATUS_COPY[selectedStatus].label}
              </span>
              <h2 className="mt-2 font-heading text-[28px] font-bold leading-tight text-heading">
                {formatTopicId(selected.topic_id)}
              </h2>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-2xl bg-surface-subtle p-4">
                <div className="text-sm font-bold text-muted">Retained now</div>
                <div className="font-heading text-[32px] font-bold leading-tight text-heading">
                  {selected.effective_p_mastery != null
                    ? `${Math.round(selected.effective_p_mastery * 100)}%`
                    : selected.p_mastery != null
                      ? `${Math.round(selected.p_mastery * 100)}%`
                      : "—"}
                </div>
              </div>
              <div className="rounded-2xl bg-surface-subtle p-4">
                <div className="text-sm font-bold text-muted">Your best</div>
                <div className="font-heading text-[32px] font-bold leading-tight text-heading">
                  {selected.p_mastery != null ? `${Math.round(selected.p_mastery * 100)}%` : "—"}
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-[15px] font-extrabold text-heading">Mastery over time</span>
              <MasteryTrend points={trendPoints} size="lg" showMasteryLine />
              {trendPoints.length === 0 && (
                <p className="text-sm text-muted">No history yet.</p>
              )}
            </div>

            <div
              className={`rounded-2xl px-4 py-3.5 text-[15px] font-semibold ${STATUS_COPY[selectedStatus].noteClass}`}
            >
              {noteFor(selected, selectedStatus)}
            </div>

            <div className="flex flex-col gap-1.5 text-sm text-muted">
              <span className="font-extrabold text-heading">How this number is worked out</span>
              <span>
                Your mastery estimate is updated by Cognivo&apos;s mastery model after every
                graded answer. &quot;Retained now&quot; adjusts it for time since you last
                practiced; &quot;Your best&quot; never goes down.
              </span>
            </div>

            <a
              href={`/practice?subject=${subjectId}`}
              className={`inline-flex min-h-[48px] items-center justify-center rounded-full px-6 text-[17px] font-extrabold no-underline ${
                selectedStatus === "refresh-due"
                  ? "bg-warning text-white"
                  : "bg-primary text-primary-foreground"
              }`}
            >
              {STATUS_COPY[selectedStatus].cta}
            </a>
          </aside>
        )}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import {
  getActivitySummary,
  getMasteryState,
  getTopicPriorityPreview,
  type MyLearnerEnrollment,
} from "@/services/api";
import JoinRosterForm from "@/components/JoinRosterForm";
import LearnerAssignments from "@/components/LearnerAssignments";
import GuardianLearnerStandards from "@/components/GuardianLearnerStandards";
import GuardianLearnerCareerConnections from "@/components/GuardianLearnerCareerConnections";
import CareerConnectionsToggle from "@/components/CareerConnectionsToggle";
import { formatTopicId } from "@/lib/format-topic-id";

// spec 041 FR-008/FR-016 (US1): a guardian's persisted learner, shown
// as a mockup-style card -- stat tiles (topics mastered, this week,
// working on) sourced from the exact already-ownership-gated endpoints
// Dashboard's own stat tiles use, just called with this real learner_id
// instead of the demo learner's (no new fetch shape). A learner not
// yet enrolled anywhere shows "Not in a class yet" (Clarifications --
// not the mockup's literal "Placement not taken", since real placement
// doesn't exist) and skips the subject-scoped stat tiles entirely.

// Spec 019 FR-009/research.md Decision 6's same grade bands, looked up
// independently here (not shared code with `lib/pacing.ts` or the
// backend's `MediationTier`, same precedent those already establish --
// each stays separately product-tunable).
function gradeBandTier(grade: number): { label: string; note: string } {
  if (grade <= 2) {
    return { label: "Sit together", note: "Start the quiz here and work through it together." };
  }
  if (grade <= 5) {
    return {
      label: "Check-in",
      note: "Start the quiz here and hand off -- we'll prompt you to check in partway.",
    };
  }
  if (grade <= 8) {
    return {
      label: "Opt-in nudges",
      note: "Start the quiz here and hand off. Turn on reminders in Settings if you'd like them.",
    };
  }
  return { label: "Independent", note: "Start the quiz here; they work on their own from there." };
}

export interface GuardianLearnerCardProps {
  learnerId: string;
  displayName: string;
  enrollment: MyLearnerEnrollment | null;
}

export default function GuardianLearnerCard({
  learnerId,
  displayName,
  enrollment,
}: GuardianLearnerCardProps) {
  const [topicsMastered, setTopicsMastered] = useState<number | null>(null);
  const [questionsThisWeek, setQuestionsThisWeek] = useState<number | null>(null);
  const [workingOn, setWorkingOn] = useState<string | null>(null);

  useEffect(() => {
    if (!enrollment) return;
    let cancelled = false;
    const { subject_id: subjectId } = enrollment;
    // Three independent, fail-silent fetches (same "secondary
    // enrichment, not the guardian's primary task" precedent
    // `GuardianLearnerStandards`/`GuardianLearnerCareerConnections`
    // already establish) -- a stat tile just stays blank on its own
    // failure rather than blocking the other two or the card itself.
    getMasteryState(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setTopicsMastered(result.topics.filter((topic) => topic.band === "mastered").length);
      })
      .catch(() => {});
    getActivitySummary(learnerId, subjectId)
      .then((result) => {
        if (!cancelled) setQuestionsThisWeek(result.questions_this_week);
      })
      .catch(() => {});
    getTopicPriorityPreview(learnerId, subjectId)
      .then((result) => {
        if (!cancelled) setWorkingOn(result.next_topic.display_name);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [learnerId, enrollment]);

  const tier = gradeBandTier(enrollment?.grade ?? 9);

  return (
    <article
      data-testid={`guardian-learner-card-${learnerId}`}
      className="flex flex-col gap-4.5 rounded-card border border-border bg-surface p-7"
    >
      <div className="flex flex-wrap items-center gap-4">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-subtle font-heading text-2xl font-bold text-heading">
          {displayName.charAt(0).toUpperCase()}
        </span>
        <div className="flex-grow">
          <h2 className="font-heading text-[26px] font-bold leading-tight text-heading">
            {displayName}
          </h2>
          <span className="text-[15px] text-muted">
            {enrollment
              ? `Grade ${enrollment.grade ?? "—"} · ${formatTopicId(enrollment.subject_id)}`
              : "Not in a class yet"}
          </span>
        </div>
        {enrollment && (
          <span className="rounded-full bg-primary-subtle px-3 py-0.5 text-[13px] font-extrabold text-heading">
            {tier.label}
          </span>
        )}
      </div>

      {enrollment ? (
        <>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-2xl bg-surface-subtle p-3.5">
              <div className="text-sm font-bold text-muted">Topics mastered</div>
              <div className="font-heading text-2xl font-bold">{topicsMastered ?? "—"}</div>
            </div>
            <div className="rounded-2xl bg-surface-subtle p-3.5">
              <div className="text-sm font-bold text-muted">This week</div>
              <div className="font-heading text-2xl font-bold">
                {questionsThisWeek === null ? "—" : `${questionsThisWeek} questions`}
              </div>
            </div>
            <div className="rounded-2xl bg-surface-subtle p-3.5">
              <div className="text-sm font-bold text-muted">Working on</div>
              <div className="pt-0.5 text-base font-extrabold">{workingOn ?? "—"}</div>
            </div>
          </div>

          <LearnerAssignments learnerId={learnerId} />
          <p className="text-sm text-muted">{tier.note}</p>
          <GuardianLearnerStandards learnerId={learnerId} />
          <CareerConnectionsToggle learnerId={learnerId} />
          <GuardianLearnerCareerConnections learnerId={learnerId} />
        </>
      ) : (
        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <p className="text-sm text-muted">
            {displayName}&apos;s class will send quizzes here once they join.
          </p>
          <JoinRosterForm learnerId={learnerId} />
        </div>
      )}
    </article>
  );
}

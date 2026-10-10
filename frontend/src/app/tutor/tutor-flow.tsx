"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  endTutorSession,
  getDemoLearner,
  getSubjects,
  getTopicPriorityPreview,
  openTutorSession,
  type SubjectSummary,
  type TopicPriorityPreview,
  type TutorRetrievedPassage,
} from "@/services/api";
import { getRealLearnerSession } from "@/lib/visitor-state";
import TutorChat, { fieldLabel } from "@/components/TutorChat";
import LoadingIndicator from "@/components/LoadingIndicator";
import { formatTopicId } from "@/lib/format-topic-id";

// Mirrors quiz-flow.tsx's initial demo-learner/subject-picker setup
// (FR-001's demo-learner path) -- once a subject is chosen, opens (or
// resumes, FR-014) that subject's Tutoring Session and hands off to
// TutorChat for the actual conversation.

type Phase = "loading" | "picking" | "opening" | "chatting" | "error";

export default function TutorFlow() {
  const searchParams = useSearchParams();
  // spec 044 FR-020 (US4): only Dashboard's own subject-scoped link
  // carries this today (Nav.tsx's plain "Tutor" entries carry no
  // subject, per FR-019/FR-023) -- its presence alone means "skip the
  // picker," no separate autostart flag needed.
  const urlSubjectId = searchParams.get("subject");

  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [topicPreview, setTopicPreview] = useState<TopicPriorityPreview | null>(null);
  const [sessionSources, setSessionSources] = useState<TutorRetrievedPassage[]>([]);

  const openSession = useCallback(async (currentLearnerId: string, subjectId: string) => {
    setPhase("opening");
    try {
      const session = await openTutorSession(currentLearnerId, subjectId);
      setSessionId(session.session_id);
      setPhase("chatting");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let resolvedLearnerId: string | null = null;
    // spec 041 FR-016: a guardian's real-learner session resolves
    // `learnerId` here instead of the demo learner.
    const realSession = getRealLearnerSession();
    (realSession ? Promise.resolve({ learner_id: realSession.learnerId }) : getDemoLearner())
      .then((learner) => {
        if (cancelled) return undefined;
        resolvedLearnerId = learner.learner_id;
        setLearnerId(learner.learner_id);
        return getSubjects();
      })
      .then((subjectsResponse) => {
        if (cancelled || !subjectsResponse) return;
        setSubjects(subjectsResponse.subjects);
        const subjectId = urlSubjectId ?? subjectsResponse.subjects[0]?.subject_id ?? null;
        setSelectedSubjectId(subjectId);
        // spec 044 FR-020 (US4): skip the picker entirely when arriving
        // with a subject already chosen.
        if (urlSubjectId && subjectId && resolvedLearnerId) {
          void openSession(resolvedLearnerId, subjectId);
          return;
        }
        setPhase("picking");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : String(error));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [urlSubjectId, openSession]);

  async function handleStart() {
    if (!learnerId || !selectedSubjectId) return;
    await openSession(learnerId, selectedSubjectId);
  }

  // 027-learner-ui-redesign, gap-closing pass: backs the mockup's "New
  // chat" button. `openTutorSession` is get-or-create (FR-014) -- ending
  // the current session first is what makes the next open create a
  // fresh one instead of just resuming this one.
  async function handleNewChat() {
    if (!sessionId) return;
    try {
      await endTutorSession(sessionId);
    } catch {
      // Best-effort: if ending it server-side fails, `handleStart`
      // below just resumes the still-active old session instead of
      // losing anything -- no worse than not having a "New chat"
      // button at all.
    }
    await handleStart();
  }

  // Independent of the chat itself (DashboardSubjectSection's pattern:
  // a failure here must not affect the conversation) -- the Sequencing
  // Agent's own next-topic pick (same one Dashboard's "up next" card
  // uses), not a new "current topic" concept invented for this screen.
  useEffect(() => {
    if (phase !== "chatting" || !learnerId || !selectedSubjectId) return;
    let cancelled = false;
    getTopicPriorityPreview(learnerId, selectedSubjectId)
      .then((result) => {
        if (!cancelled) setTopicPreview(result);
      })
      .catch(() => {
        if (!cancelled) setTopicPreview(null);
      });
    return () => {
      cancelled = true;
    };
  }, [phase, learnerId, selectedSubjectId]);

  if (phase === "loading" || phase === "opening") {
    return <LoadingIndicator message="Waking up your tutor…" />;
  }

  if (phase === "error") {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {errorMessage}</p>
      </div>
    );
  }

  if (phase === "chatting" && sessionId) {
    return (
      <div className="mx-auto grid w-full max-w-[1180px] grid-cols-1 gap-6 p-8 lg:grid-cols-[1fr_320px] lg:items-start">
        <section className="flex min-h-[760px] flex-col rounded-card border border-border bg-surface">
          <div className="flex items-center gap-3.5 border-b border-border px-7 py-5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-subtle">
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                className="text-primary"
              >
                <path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z" />
                <path d="M19 15l.8 1.9 1.9.8-1.9.8L19 20.5l-.8-1.9-1.9-.8 1.9-.8z" />
              </svg>
            </div>
            <div className="flex-grow">
              <h1 className="font-heading text-2xl font-bold leading-tight text-heading">
                AI Tutor
              </h1>
              <p className="m-0 text-sm text-muted">
                Answers come from your course material. It&apos;s an AI — your instructor has the
                final word.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleNewChat()}
              className="min-h-11 shrink-0 rounded-full border-2 border-primary/30 px-[18px] font-extrabold text-heading"
            >
              New chat
            </button>
          </div>
          <div className="flex-grow p-7">
            <TutorChat
              key={sessionId}
              sessionId={sessionId}
              onSourcesChange={setSessionSources}
              currentTopicDisplayName={topicPreview?.next_topic.display_name}
            />
          </div>
        </section>

        <aside className="flex flex-col gap-5">
          {topicPreview && (
            <section className="flex flex-col gap-3.5 rounded-card border border-border bg-surface p-6">
              <h2 className="m-0 text-xs font-extrabold uppercase tracking-[0.08em] text-primary">
                You&apos;re working on
              </h2>
              <div className="font-heading text-xl font-bold leading-tight text-heading">
                {topicPreview.next_topic.display_name}
              </div>
              <div className="flex flex-col gap-1.5">
                <div className="relative h-2.5 rounded-full bg-surface-subtle">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-primary/60"
                    style={{
                      width: `${Math.round((topicPreview.next_topic.p_mastery ?? 0) * 100)}%`,
                    }}
                  />
                </div>
                <span className="text-sm font-bold text-muted">
                  In progress · {Math.round((topicPreview.next_topic.p_mastery ?? 0) * 100)}%
                </span>
              </div>
              <p className="m-0 text-sm text-muted">
                Chatting here doesn&apos;t change your mastery — only graded practice does.
              </p>
              <a
                href={`/mastery?subject=${selectedSubjectId}`}
                className="self-start text-[15px] font-extrabold text-heading"
              >
                View in Mastery
              </a>
            </section>
          )}

          {sessionSources.length > 0 && (
            <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6">
              <h2 className="m-0 text-xs font-extrabold uppercase tracking-[0.08em] text-primary">
                Sources used in this chat
              </h2>
              <div className="flex flex-col gap-2.5 text-[15px]">
                {sessionSources.map((source) => (
                  <div key={`${source.topic_id}:${source.field}`} className="flex gap-2.5">
                    <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-primary" />
                    <span>
                      <strong className="text-heading">{formatTopicId(source.topic_id)}</strong>
                      <br />
                      <span className="text-muted">{fieldLabel(source.field)}</span>
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="flex flex-col gap-2 rounded-card bg-warning/15 p-6">
            <span className="font-extrabold text-heading">Ready to try it for real?</span>
            <span className="text-[15px] text-muted">
              Practice questions update your mastery and show how each answer was graded.
            </span>
            <a href="/practice" className="self-start font-extrabold text-heading">
              Go to practice →
            </a>
          </section>
        </aside>
      </div>
    );
  }

  return (
    <div
      className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8"
      data-testid="tutor-start-form"
    >
      <h1 className="font-heading text-[32px] font-bold text-heading">Ask the Tutor</h1>
      {subjects.length > 1 && (
        <label className="flex flex-col gap-1">
          Subject
          <select
            value={selectedSubjectId ?? ""}
            onChange={(event) => setSelectedSubjectId(event.target.value)}
            className="rounded-[14px] border-2 border-primary/30 px-[18px] py-3"
          >
            {subjects.map((subject) => (
              <option key={subject.subject_id} value={subject.subject_id}>
                {subject.display_name}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        type="button"
        disabled={!selectedSubjectId}
        onClick={() => void handleStart()}
        className="self-start rounded-full bg-primary px-7 py-3.5 text-[17px] font-extrabold text-primary-foreground disabled:opacity-40"
      >
        Start Tutoring
      </button>
    </div>
  );
}

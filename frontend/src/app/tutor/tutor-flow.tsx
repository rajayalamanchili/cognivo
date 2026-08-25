"use client";

import { useEffect, useState } from "react";
import { getDemoLearner, getSubjects, openTutorSession, type SubjectSummary } from "@/services/api";
import TutorChat from "@/components/TutorChat";

// Mirrors quiz-flow.tsx's initial demo-learner/subject-picker setup
// (FR-001's demo-learner path) -- once a subject is chosen, opens (or
// resumes, FR-014) that subject's Tutoring Session and hands off to
// TutorChat for the actual conversation.

type Phase = "loading" | "picking" | "opening" | "chatting" | "error";

export default function TutorFlow() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoLearner()
      .then((learner) => {
        if (cancelled) return undefined;
        setLearnerId(learner.learner_id);
        return getSubjects();
      })
      .then((subjectsResponse) => {
        if (cancelled || !subjectsResponse) return;
        setSubjects(subjectsResponse.subjects);
        setSelectedSubjectId(subjectsResponse.subjects[0]?.subject_id ?? null);
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
  }, []);

  async function handleStart() {
    if (!learnerId || !selectedSubjectId) return;
    setPhase("opening");
    try {
      const session = await openTutorSession(learnerId, selectedSubjectId);
      setSessionId(session.session_id);
      setPhase("chatting");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  if (phase === "loading" || phase === "opening") {
    return <p className="p-8">Loading&hellip;</p>;
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
      <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
        <h1 className="text-2xl font-semibold">Ask the Tutor</h1>
        <TutorChat sessionId={sessionId} />
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8" data-testid="tutor-start-form">
      <h1 className="text-2xl font-semibold">Ask the Tutor</h1>
      {subjects.length > 1 && (
        <label className="flex flex-col gap-1">
          Subject
          <select
            value={selectedSubjectId ?? ""}
            onChange={(event) => setSelectedSubjectId(event.target.value)}
            className="rounded-lg border border-border px-3 py-2"
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
        className="self-start rounded-lg bg-primary px-5 py-3 text-primary-foreground disabled:opacity-40"
      >
        Start Tutoring
      </button>
    </div>
  );
}

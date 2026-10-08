"use client";

import { useEffect, useState } from "react";
import { listFlaggedQuestions, resolveFlaggedQuestion, type FlaggedQuestion } from "@/services/api";
import LoadingIndicator from "@/components/LoadingIndicator";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function ReviewFlow() {
  const [flagged, setFlagged] = useState<FlaggedQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listFlaggedQuestions()
      .then((response) => {
        if (cancelled) return;
        setFlagged(response.flagged);
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setLoadError(errorText(error));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleResolve(questionId: string, action: "reactivate" | "reject") {
    setResolvingId(questionId);
    setResolveError(null);
    try {
      await resolveFlaggedQuestion(questionId, action);
      // "reactivate" moves validation_status away from "flagged", so a
      // re-fetch would already drop it from the queue; "reject" stays
      // "flagged" by design (data-model.md: no further state beyond
      // flagged/valid -- the CONTENT_REVIEW_RESOLVED audit event is
      // the durable record of the decision, not a queue-visible
      // status). Removing it from view here either way keeps a
      // resolved item from immediately reappearing within this
      // session, without inventing a status the backend doesn't have.
      setFlagged((previous) => previous.filter((question) => question.question_id !== questionId));
    } catch (error) {
      setResolveError(errorText(error));
    } finally {
      setResolvingId(null);
    }
  }

  if (loading) {
    return <LoadingIndicator message="Loading review queue…" variant="professional" />;
  }

  if (loadError) {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {loadError}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[900px] flex-col gap-5 p-8">
      <div>
        <h1 className="font-heading text-[40px] font-bold leading-tight text-heading">
          Flagged questions
        </h1>
        <p className="mt-1 text-[17px] text-muted">
          Learners flagged these while practising. Flagged questions are paused, so no one sees
          them until you decide.
        </p>
      </div>

      {resolveError && <p className="text-sm text-error">{resolveError}</p>}

      {flagged.length === 0 && (
        <div className="flex flex-col items-center gap-1.5 rounded-card border border-border bg-surface p-10 text-center">
          <svg
            width="40"
            height="40"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className="text-success"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
          <span className="font-heading text-2xl font-bold text-heading">
            Nothing to review right now.
          </span>
          <span className="text-muted">New flags will show up here.</span>
        </div>
      )}

      <div className="flex flex-col gap-4" data-testid="flagged-questions">
        {flagged.map((question) => (
          <article
            key={question.question_id}
            className="flex flex-col gap-3.5 rounded-card border border-border bg-surface p-7"
          >
            <p className="font-heading text-xl font-semibold leading-snug">{question.stem}</p>
            {question.flagged_reason && (
              <div className="flex gap-2.5 rounded-xl bg-warning/15 px-4 py-3 text-warning">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                  className="mt-0.5 shrink-0"
                >
                  <path d="M5 21V4" />
                  <path d="M5 4h11l-2 4 2 4H5" />
                </svg>
                <span>
                  <strong className="font-extrabold">Reason:</strong> {question.flagged_reason}
                </span>
              </div>
            )}
            <p className="text-sm text-muted">
              Flagged {new Date(question.flagged_at).toLocaleString()}
            </p>
            <div className="flex gap-2.5">
              <button
                type="button"
                disabled={resolvingId === question.question_id}
                onClick={() => handleResolve(question.question_id, "reactivate")}
                className="min-h-11 rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
              >
                Reactivate
              </button>
              <button
                type="button"
                disabled={resolvingId === question.question_id}
                onClick={() => handleResolve(question.question_id, "reject")}
                className="min-h-11 rounded-full border-2 border-primary/25 px-5 font-extrabold text-primary disabled:opacity-40"
              >
                Reject
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

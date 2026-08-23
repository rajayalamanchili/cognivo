"use client";

import { useEffect, useState } from "react";
import { listFlaggedQuestions, resolveFlaggedQuestion, type FlaggedQuestion } from "@/services/api";

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
    return <p className="p-8">Loading review queue&hellip;</p>;
  }

  if (loadError) {
    return (
      <div className="p-8">
        <p className="text-red-600">Something went wrong: {loadError}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Flagged questions</h1>

      {resolveError && <p className="text-sm text-red-600">{resolveError}</p>}

      {flagged.length === 0 && <p className="text-sm">Nothing to review right now.</p>}

      <div className="flex flex-col gap-4" data-testid="flagged-questions">
        {flagged.map((question) => (
          <div
            key={question.question_id}
            className="flex flex-col gap-2 rounded border border-black/20 p-4 dark:border-white/20"
          >
            <p>{question.stem}</p>
            {question.flagged_reason && (
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Reason: {question.flagged_reason}
              </p>
            )}
            <p className="text-sm text-zinc-500 dark:text-zinc-500">
              Flagged {new Date(question.flagged_at).toLocaleString()}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={resolvingId === question.question_id}
                onClick={() => handleResolve(question.question_id, "reactivate")}
                className="rounded bg-foreground px-3 py-1.5 text-sm text-background disabled:opacity-40"
              >
                Reactivate
              </button>
              <button
                type="button"
                disabled={resolvingId === question.question_id}
                onClick={() => handleResolve(question.question_id, "reject")}
                className="rounded border border-black/20 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-white/20"
              >
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

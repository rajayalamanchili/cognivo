"use client";

import { useState, type FormEvent } from "react";
import { ApiError, createLearner } from "@/services/api";
import JoinRosterForm from "@/components/JoinRosterForm";

interface AddedLearner {
  learner_id: string;
  display_name: string;
}

export default function GuardianLearnersPage() {
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [addedLearners, setAddedLearners] = useState<AddedLearner[]>([]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorText(null);
    try {
      const result = await createLearner(displayName);
      setAddedLearners((previous) => [
        ...previous,
        { learner_id: result.learner_id, display_name: displayName },
      ]);
      setDisplayName("");
    } catch (error) {
      setErrorText(
        error instanceof ApiError && error.status === 401
          ? "Please sign in as a guardian first."
          : error instanceof Error
            ? error.message
            : String(error),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Add a learner</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Learner&apos;s name
          <input
            type="text"
            required
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
          />
        </label>
        {errorText && (
          <p className="text-sm text-red-600" data-testid="add-learner-error">
            {errorText}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting || displayName.trim() === ""}
          className="rounded bg-foreground px-5 py-3 text-background disabled:opacity-40"
        >
          {submitting ? "Adding…" : "Add learner"}
        </button>
      </form>
      {addedLearners.length > 0 && (
        <ul className="flex flex-col gap-4 text-sm" data-testid="added-learners">
          {addedLearners.map((learner) => (
            <li key={learner.learner_id} className="flex flex-col gap-2">
              <span>{learner.display_name} added.</span>
              <JoinRosterForm learnerId={learner.learner_id} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

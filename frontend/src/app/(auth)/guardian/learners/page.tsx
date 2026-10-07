"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ApiError, createLearner, listMyLearners, type MyLearner } from "@/services/api";
import JoinRosterForm from "@/components/JoinRosterForm";
import ClassDirectoryBrowse from "@/components/ClassDirectoryBrowse";
import LearnerAssignments from "@/components/LearnerAssignments";
import GuardianLearnerStandards from "@/components/GuardianLearnerStandards";
import GuardianLearnerCareerConnections from "@/components/GuardianLearnerCareerConnections";
import CareerConnectionsToggle from "@/components/CareerConnectionsToggle";
import GuardianLearnerCard from "@/components/GuardianLearnerCard";

// spec 041 FR-008/FR-016/FR-023 (US1): the per-learner card dashboard,
// fetched from `GET /api/learners/mine` (T007) so a learner added in a
// prior browser session still shows up here, not just ones added this
// tab (the gap `addedLearners` below -- unchanged from before this
// feature, kept purely for its own instant "added"/join-roster
// confirmation -- never closed on its own).

interface AddedLearner {
  learner_id: string;
  display_name: string;
}

export default function GuardianLearnersPage() {
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [addedLearners, setAddedLearners] = useState<AddedLearner[]>([]);

  const [learners, setLearners] = useState<MyLearner[]>([]);
  const [loadingLearners, setLoadingLearners] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listMyLearners()
      .then((result) => {
        if (!cancelled) setLearners(result.learners);
      })
      .finally(() => {
        if (!cancelled) setLoadingLearners(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
    <div className="mx-auto grid w-full max-w-[1180px] grid-cols-1 items-start gap-6 p-8 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="flex flex-col gap-5">
        <div>
          <h1 className="font-heading text-[40px] font-bold leading-tight text-heading">
            My learners
          </h1>
          <p className="mt-1 text-[17px] text-muted">
            Open a learner&apos;s practice, start assigned quizzes, and find a class.
          </p>
        </div>

        {!loadingLearners && learners.length === 0 && (
          <p className="text-sm text-muted">No learners yet -- add one from the sidebar.</p>
        )}
        {learners.map((learner) => (
          <GuardianLearnerCard
            key={learner.learner_id}
            learnerId={learner.learner_id}
            displayName={learner.display_name}
            enrollment={learner.enrollment}
          />
        ))}
      </div>

      <aside className="flex flex-col gap-5">
        <section className="flex flex-col gap-3.5 rounded-card border border-border bg-surface p-6">
          <h2 className="font-heading text-xl font-bold text-heading">Add a learner</h2>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5 text-[15px] font-extrabold">
              Learner&apos;s name
              <input
                type="text"
                required
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                className="min-h-12 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
              />
            </label>
            {errorText && (
              <p className="text-sm text-error" data-testid="add-learner-error">
                {errorText}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting || displayName.trim() === ""}
              className="min-h-12 rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
            >
              {submitting ? "Adding…" : "Add learner"}
            </button>
          </form>
          <p className="text-sm text-muted">
            Learners don&apos;t get their own login. You open their learning from this page.
          </p>
          {addedLearners.length > 0 && (
            <ul className="flex flex-col gap-4 text-sm" data-testid="added-learners">
              {addedLearners.map((learner) => (
                <li
                  key={learner.learner_id}
                  data-testid="added-learner"
                  data-learner-id={learner.learner_id}
                  className="flex flex-col gap-2 border-t border-border pt-4"
                >
                  <span>{learner.display_name} added.</span>
                  <JoinRosterForm learnerId={learner.learner_id} />
                  <ClassDirectoryBrowse learnerId={learner.learner_id} />
                  <GuardianLearnerStandards learnerId={learner.learner_id} />
                  <CareerConnectionsToggle learnerId={learner.learner_id} />
                  <GuardianLearnerCareerConnections learnerId={learner.learner_id} />
                  <LearnerAssignments learnerId={learner.learner_id} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-2 rounded-card bg-surface-subtle p-6">
          <h2 className="font-extrabold">How quiz start works</h2>
          <p className="text-sm text-muted">
            You always start an assigned quiz from your account, on this device.
          </p>
          <ul className="flex flex-col gap-1.5 pl-4.5 text-sm text-muted">
            <li>
              <strong className="font-extrabold">Grades 1–2:</strong> sit together. The quiz
              stays under your sign-in the whole time.
            </li>
            <li>
              <strong className="font-extrabold">Grades 3–5:</strong> start it, hand them the
              device, and we&apos;ll prompt you to check in.
            </li>
            <li>
              <strong className="font-extrabold">Grades 6–8:</strong> start it and hand over.
              Reminders only if you opt in.
            </li>
            <li>
              <strong className="font-extrabold">Grades 9–12:</strong> start it and hand over.
              They finish on their own.
            </li>
          </ul>
        </section>
      </aside>
    </div>
  );
}

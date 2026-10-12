"use client";

import { useEffect, useState } from "react";
import {
  listLearnerAssignments,
  type AssignmentStatus,
  type LearnerAssignment,
} from "@/services/api";
import LoadingIndicator from "@/components/LoadingIndicator";

// A per-learner assignment list (spec 011, User Story 2) -- "Start"/
// "Resume" open the dedicated `/assignment` page (mirrors "Start
// practice"/"Take placement" navigating to `/practice`/`/placement`,
// spec 044's own precedent) rather than answering inline here; this
// component now only ever shows the list + status.

const STATUS_LABEL: Record<AssignmentStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
  ended_early: "Ended early",
};

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export interface LearnerAssignmentsProps {
  learnerId: string;
  // spec 044 FR-002 (US1): scope to one enrollment's own assignments
  // (the selected card tab) -- undefined keeps today's "every
  // assignment across every roster" list.
  rosterId?: string;
  // Navigates to `/assignment?assignmentId=...` for both a fresh start
  // and a resume -- the dedicated page's own mount effect decides which
  // based on the assignment's current status (same single-URL precedent
  // `handleStart`/`handleResume` used to share here before this moved).
  onOpenAssignment: (assignmentId: string) => void;
}

export default function LearnerAssignments({
  learnerId,
  rosterId,
  onOpenAssignment,
}: LearnerAssignmentsProps) {
  const [assignments, setAssignments] = useState<LearnerAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  function refreshAssignments() {
    setLoading(true);
    setLoadError(null);
    listLearnerAssignments(learnerId, rosterId)
      .then((result) => {
        setAssignments(result.assignments);
        setLoading(false);
      })
      .catch((error: unknown) => {
        setLoadError(errorText(error));
        setLoading(false);
      });
  }

  useEffect(() => {
    let cancelled = false;
    listLearnerAssignments(learnerId, rosterId)
      .then((result) => {
        if (cancelled) return;
        setAssignments(result.assignments);
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
  }, [learnerId, rosterId]);

  if (loading) {
    return <LoadingIndicator message="Finding your quizzes…" />;
  }

  if (loadError) {
    return (
      <p className="text-sm text-error" data-testid="learner-assignments-error">
        {loadError}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4" data-testid="learner-assignments">
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-lg font-bold text-heading">Assigned quizzes</h3>
        <button type="button" onClick={refreshAssignments} className="text-sm text-muted underline">
          Refresh
        </button>
      </div>
      {assignments.length === 0 && <p className="text-sm">No assignments yet.</p>}
      {assignments.map((assignment) => {
        const startable = assignment.status === "not_started" && !assignment.cancelled_at;
        // Covers an attempt abandoned mid-session (e.g. the guardian
        // navigated away before finishing) -- without this, an
        // `in_progress` assignment has no action at all once `startable`
        // goes false, leaving it permanently stuck.
        const resumable =
          assignment.status === "in_progress" &&
          !assignment.cancelled_at &&
          assignment.quiz_session_id !== null;
        return (
          <div
            key={assignment.assignment_id}
            data-testid={`learner-assignment-${assignment.assignment_id}`}
            className="flex flex-wrap items-center justify-between gap-3.5 rounded-2xl border border-border px-4.5 py-3.5 text-sm"
          >
            <div className="flex flex-col gap-0.5">
              <span className="font-extrabold text-heading">
                {assignment.topic_ids.join(", ")} &middot; {assignment.question_count} questions
                {assignment.has_unviewed_activity && (
                  <span
                    data-testid={`learner-assignment-unviewed-${assignment.assignment_id}`}
                    className="ml-2 inline-block h-2 w-2 rounded-full bg-primary align-middle"
                    title="New activity"
                  />
                )}
              </span>
              <span className="text-muted">
                {STATUS_LABEL[assignment.status]}
                {assignment.due_at && ` · due ${new Date(assignment.due_at).toLocaleString()}`}
                {assignment.cancelled_at && (
                  <span data-testid={`learner-assignment-cancelled-${assignment.assignment_id}`}>
                    {" "}
                    &middot; cancelled
                  </span>
                )}
              </span>
            </div>
            {startable && (
              <button
                type="button"
                onClick={() => onOpenAssignment(assignment.assignment_id)}
                className="min-h-11 rounded-full border-2 border-primary/25 bg-surface px-5 font-extrabold text-heading"
              >
                Start
              </button>
            )}
            {resumable && (
              <button
                type="button"
                onClick={() => onOpenAssignment(assignment.assignment_id)}
                className="min-h-11 rounded-full border-2 border-primary/25 bg-surface px-5 font-extrabold text-heading"
              >
                Resume
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

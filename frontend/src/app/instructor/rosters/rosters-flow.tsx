"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  approveRosterRequest,
  cancelAssignment,
  createAssignment,
  createRoster,
  declineRosterRequest,
  getSubjects,
  listRosterAssignments,
  listRosterEnrollments,
  listRosterRequests,
  listRosters,
  unenrollLearner,
  updateRosterEnrollmentMode,
  type EnrolledLearner,
  type EnrollmentMode,
  type EnrollmentRequestEntry,
  type QuizAssignmentSummary,
  type RosterSummary,
  type SubjectSummary,
} from "@/services/api";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function RostersFlow() {
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [rosters, setRosters] = useState<RosterSummary[]>([]);
  const [joinCodes, setJoinCodes] = useState<Record<string, string | null>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [newSubjectId, setNewSubjectId] = useState("");
  const [newMode, setNewMode] = useState<EnrollmentMode>("open");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [selectedRosterId, setSelectedRosterId] = useState<string | null>(null);
  const [requests, setRequests] = useState<EnrollmentRequestEntry[]>([]);
  const [enrollments, setEnrollments] = useState<EnrolledLearner[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [assignments, setAssignments] = useState<QuizAssignmentSummary[]>([]);
  const [assignTopicIds, setAssignTopicIds] = useState("");
  const [assignQuestionCount, setAssignQuestionCount] = useState(5);
  const [assignDueAt, setAssignDueAt] = useState("");
  const [assignTargetMode, setAssignTargetMode] = useState<"all" | "subset">("all");
  const [assignSelectedLearnerIds, setAssignSelectedLearnerIds] = useState<string[]>([]);
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listRosters(), getSubjects()])
      .then(([rostersResponse, subjectsResponse]) => {
        if (cancelled) return;
        setRosters(rostersResponse.rosters);
        setSubjects(subjectsResponse.subjects);
        if (subjectsResponse.subjects.length > 0) {
          setNewSubjectId(subjectsResponse.subjects[0].subject_id);
        }
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

  const loadDetail = useCallback((rosterId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    Promise.all([
      listRosterRequests(rosterId),
      listRosterEnrollments(rosterId),
      listRosterAssignments(rosterId),
    ])
      .then(([requestsResponse, enrollmentsResponse, assignmentsResponse]) => {
        setRequests(requestsResponse.requests);
        setEnrollments(enrollmentsResponse.enrollments);
        setAssignments(assignmentsResponse.assignments);
        setDetailLoading(false);
      })
      .catch((error: unknown) => {
        setDetailError(errorText(error));
        setDetailLoading(false);
      });
  }, []);

  function selectRoster(rosterId: string) {
    setSelectedRosterId(rosterId);
    setAssignTopicIds("");
    setAssignQuestionCount(5);
    setAssignDueAt("");
    setAssignTargetMode("all");
    setAssignSelectedLearnerIds([]);
    setAssignError(null);
    loadDetail(rosterId);
  }

  function toggleAssignLearner(learnerId: string) {
    setAssignSelectedLearnerIds((previous) =>
      previous.includes(learnerId)
        ? previous.filter((id) => id !== learnerId)
        : [...previous, learnerId],
    );
  }

  async function handleCreateAssignment(event: FormEvent) {
    event.preventDefault();
    if (!selectedRosterId) return;
    const topicIds = assignTopicIds
      .split(",")
      .map((id) => id.trim())
      .filter((id) => id.length > 0);
    setAssigning(true);
    setAssignError(null);
    try {
      await createAssignment(selectedRosterId, {
        topicIds,
        questionCount: assignQuestionCount,
        dueAt: assignDueAt ? new Date(assignDueAt).toISOString() : null,
        learnerIds: assignTargetMode === "all" ? "all" : assignSelectedLearnerIds,
      });
      setAssignTopicIds("");
      setAssignQuestionCount(5);
      setAssignDueAt("");
      setAssignTargetMode("all");
      setAssignSelectedLearnerIds([]);
      loadDetail(selectedRosterId);
    } catch (error) {
      setAssignError(errorText(error));
    } finally {
      setAssigning(false);
    }
  }

  async function handleCancelAssignment(assignmentId: string) {
    if (!selectedRosterId) return;
    try {
      await cancelAssignment(selectedRosterId, assignmentId);
      loadDetail(selectedRosterId);
    } catch (error) {
      setDetailError(errorText(error));
    }
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const roster = await createRoster(newSubjectId, newMode);
      setRosters((previous) => [
        ...previous,
        {
          roster_id: roster.roster_id,
          subject_id: roster.subject_id,
          enrollment_mode: roster.enrollment_mode,
        },
      ]);
      setJoinCodes((previous) => ({ ...previous, [roster.roster_id]: roster.join_code }));
      selectRoster(roster.roster_id);
    } catch (error) {
      setCreateError(errorText(error));
    } finally {
      setCreating(false);
    }
  }

  async function handleSetMode(rosterId: string, mode: EnrollmentMode) {
    try {
      const roster = await updateRosterEnrollmentMode(rosterId, mode);
      setRosters((previous) =>
        previous.map((r) =>
          r.roster_id === rosterId ? { ...r, enrollment_mode: roster.enrollment_mode } : r,
        ),
      );
      setJoinCodes((previous) => ({ ...previous, [rosterId]: roster.join_code }));
    } catch (error) {
      setDetailError(errorText(error));
    }
  }

  async function handleApprove(requestId: string) {
    if (!selectedRosterId) return;
    try {
      await approveRosterRequest(selectedRosterId, requestId);
      loadDetail(selectedRosterId);
    } catch (error) {
      setDetailError(errorText(error));
    }
  }

  async function handleDecline(requestId: string) {
    if (!selectedRosterId) return;
    try {
      await declineRosterRequest(selectedRosterId, requestId);
      loadDetail(selectedRosterId);
    } catch (error) {
      setDetailError(errorText(error));
    }
  }

  async function handleUnenroll(learnerId: string) {
    if (!selectedRosterId) return;
    try {
      await unenrollLearner(selectedRosterId, learnerId);
      loadDetail(selectedRosterId);
    } catch (error) {
      setDetailError(errorText(error));
    }
  }

  if (loading) {
    return <p className="p-8">Loading rosters&hellip;</p>;
  }

  if (loadError) {
    return (
      <div className="p-8">
        <p className="text-red-600">Something went wrong: {loadError}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 p-8">
      <h1 className="text-2xl font-semibold">Your rosters</h1>

      <form
        onSubmit={handleCreate}
        className="flex flex-col gap-4 rounded border border-black/20 p-4 dark:border-white/20"
      >
        <h2 className="font-medium">Create a roster</h2>
        <label className="flex flex-col gap-1 text-sm">
          Subject
          <select
            value={newSubjectId}
            onChange={(event) => setNewSubjectId(event.target.value)}
            className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
          >
            {subjects.map((subject) => (
              <option key={subject.subject_id} value={subject.subject_id}>
                {subject.display_name}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="flex gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="enrollment_mode"
              checked={newMode === "open"}
              onChange={() => setNewMode("open")}
            />
            Open (self-serve via join code)
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="enrollment_mode"
              checked={newMode === "closed"}
              onChange={() => setNewMode("closed")}
            />
            Closed (requires approval)
          </label>
        </fieldset>
        {createError && (
          <p className="text-sm text-red-600" data-testid="create-roster-error">
            {createError}
          </p>
        )}
        <button
          type="submit"
          disabled={creating || !newSubjectId}
          className="self-start rounded bg-foreground px-5 py-3 text-background disabled:opacity-40"
        >
          {creating ? "Creating…" : "Create roster"}
        </button>
      </form>

      <div className="flex flex-col gap-2" data-testid="roster-list">
        {rosters.length === 0 && <p className="text-sm">No rosters yet.</p>}
        {rosters.map((roster) => (
          <div
            key={roster.roster_id}
            className="flex items-center justify-between rounded border border-black/20 px-4 py-3 dark:border-white/20"
          >
            <div className="flex flex-col gap-1">
              <span className="font-medium">{roster.subject_id}</span>
              <span className="text-sm">
                {roster.enrollment_mode}
                {joinCodes[roster.roster_id] && ` • code: ${joinCodes[roster.roster_id]}`}
              </span>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleSetMode(roster.roster_id, roster.enrollment_mode)}
                className="rounded border border-black/20 px-3 py-1.5 text-sm dark:border-white/20"
              >
                Show code
              </button>
              <button
                type="button"
                onClick={() =>
                  handleSetMode(
                    roster.roster_id,
                    roster.enrollment_mode === "open" ? "closed" : "open",
                  )
                }
                className="rounded border border-black/20 px-3 py-1.5 text-sm dark:border-white/20"
              >
                Switch to {roster.enrollment_mode === "open" ? "closed" : "open"}
              </button>
              <button
                type="button"
                onClick={() => selectRoster(roster.roster_id)}
                className="rounded bg-foreground px-3 py-1.5 text-sm text-background"
              >
                Manage
              </button>
            </div>
          </div>
        ))}
      </div>

      {selectedRosterId && (
        <div className="flex flex-col gap-6 rounded border border-black/20 p-4 dark:border-white/20">
          <h2 className="font-medium">Managing roster {selectedRosterId}</h2>
          {detailLoading && <p className="text-sm">Loading&hellip;</p>}
          {detailError && (
            <p className="text-sm text-red-600" data-testid="roster-detail-error">
              {detailError}
            </p>
          )}

          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">Pending requests</h3>
            {requests.length === 0 && <p className="text-sm">No pending requests.</p>}
            {requests.map((request) => (
              <div
                key={request.enrollment_request_id}
                className="flex items-center justify-between text-sm"
              >
                <span>Learner {request.learner_id}</span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleApprove(request.enrollment_request_id)}
                    className="rounded bg-foreground px-3 py-1 text-background"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDecline(request.enrollment_request_id)}
                    className="rounded border border-black/20 px-3 py-1 dark:border-white/20"
                  >
                    Decline
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">Enrolled learners</h3>
            {enrollments.length === 0 && <p className="text-sm">No learners enrolled yet.</p>}
            {enrollments.map((learner) => (
              <div key={learner.learner_id} className="flex items-center justify-between text-sm">
                <span>{learner.display_name}</span>
                <button
                  type="button"
                  onClick={() => handleUnenroll(learner.learner_id)}
                  className="rounded border border-black/20 px-3 py-1 dark:border-white/20"
                >
                  Unenroll
                </button>
              </div>
            ))}
          </div>

          <form
            onSubmit={handleCreateAssignment}
            data-testid="assign-quiz-form"
            className="flex flex-col gap-3 rounded border border-black/20 p-4 dark:border-white/20"
          >
            <h3 className="text-sm font-medium">Assign a quiz</h3>
            <label className="flex flex-col gap-1 text-sm">
              Topic ids (comma-separated)
              <input
                type="text"
                value={assignTopicIds}
                onChange={(event) => setAssignTopicIds(event.target.value)}
                data-testid="assign-topic-ids"
                className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Question count
              <input
                type="number"
                min={1}
                max={50}
                value={assignQuestionCount}
                onChange={(event) => setAssignQuestionCount(Number(event.target.value))}
                data-testid="assign-question-count"
                className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Due date (optional)
              <input
                type="datetime-local"
                value={assignDueAt}
                onChange={(event) => setAssignDueAt(event.target.value)}
                data-testid="assign-due-at"
                className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
              />
            </label>
            <fieldset className="flex flex-col gap-2 text-sm">
              <div className="flex gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="assign_target_mode"
                    checked={assignTargetMode === "all"}
                    onChange={() => setAssignTargetMode("all")}
                    data-testid="assign-target-all"
                  />
                  All enrolled learners
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="assign_target_mode"
                    checked={assignTargetMode === "subset"}
                    onChange={() => setAssignTargetMode("subset")}
                    data-testid="assign-target-subset"
                  />
                  Choose learners
                </label>
              </div>
              {assignTargetMode === "subset" && (
                <div className="flex flex-col gap-1 pl-2">
                  {enrollments.length === 0 && (
                    <p className="text-sm">No learners enrolled yet.</p>
                  )}
                  {enrollments.map((learner) => (
                    <label key={learner.learner_id} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={assignSelectedLearnerIds.includes(learner.learner_id)}
                        onChange={() => toggleAssignLearner(learner.learner_id)}
                        data-testid={`assign-learner-${learner.learner_id}`}
                      />
                      {learner.display_name}
                    </label>
                  ))}
                </div>
              )}
            </fieldset>
            {assignError && (
              <p className="text-sm text-red-600" data-testid="assign-quiz-error">
                {assignError}
              </p>
            )}
            <button
              type="submit"
              disabled={
                assigning ||
                assignTopicIds.trim().length === 0 ||
                (assignTargetMode === "subset" && assignSelectedLearnerIds.length === 0)
              }
              className="self-start rounded bg-foreground px-5 py-3 text-background disabled:opacity-40"
            >
              {assigning ? "Assigning…" : "Assign quiz"}
            </button>
          </form>

          <div className="flex flex-col gap-2" data-testid="assignment-list">
            <h3 className="text-sm font-medium">Assignments</h3>
            {assignments.length === 0 && <p className="text-sm">No assignments yet.</p>}
            {assignments.map((assignment) => (
              <div
                key={assignment.assignment_id}
                data-testid={`assignment-${assignment.assignment_id}`}
                className="flex items-center justify-between text-sm"
              >
                <span>
                  {assignment.topic_ids.join(", ")} &middot; {assignment.question_count} questions
                  {assignment.due_at && ` · due ${new Date(assignment.due_at).toLocaleString()}`}
                  {assignment.cancelled_at && (
                    <span data-testid={`assignment-cancelled-${assignment.assignment_id}`}>
                      {" "}
                      · cancelled
                    </span>
                  )}
                </span>
                {!assignment.cancelled_at && (
                  <button
                    type="button"
                    onClick={() => handleCancelAssignment(assignment.assignment_id)}
                    className="rounded border border-black/20 px-3 py-1 dark:border-white/20"
                  >
                    Cancel
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

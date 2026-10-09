"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  approveRosterRequest,
  cancelAssignment,
  createAssignment,
  createRoster,
  declineRosterRequest,
  getAssignmentDetail,
  getSubjects,
  getWhoAmI,
  listRosterAssignments,
  listRosterEnrollments,
  listRosterRequests,
  listRosters,
  unenrollLearner,
  updateInstructorDisplayName,
  updateRosterEnrollmentMode,
  updateRosterListing,
  type AssignmentDetail,
  type EnrolledLearner,
  type EnrollmentMode,
  type EnrollmentRequestEntry,
  type QuizAssignmentSummary,
  type RosterSummary,
  type SubjectSummary,
} from "@/services/api";
import LoadingIndicator from "@/components/LoadingIndicator";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// spec 041 FR-017/FR-018 (T049): distinguishes the one error code the
// "List in directory" toggle handles specially (an inline prompt) from
// every other failure (shown as plain error text).
function apiErrorCode(error: unknown): string | null {
  if (error instanceof ApiError && typeof error.body === "object" && error.body !== null) {
    const detail = (error.body as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : null;
  }
  return null;
}

// spec 043 FR-009: pre-fills the assign-quiz form's due date from the
// instructor's `default_due_date_offset_days`, formatted for a
// `datetime-local` input in the browser's own local time (not UTC --
// `toISOString` would shift the displayed value away from what a
// due-at-end-of-day offset actually means to the instructor).
function localDateTimeInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
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

  const [resultsAssignmentId, setResultsAssignmentId] = useState<string | null>(null);
  const [resultsDetail, setResultsDetail] = useState<AssignmentDetail | null>(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState<string | null>(null);

  // spec 041 FR-017/FR-018 (T049): "List in directory" toggle state,
  // keyed by roster_id -- plus the inline display-name prompt shown
  // only when a toggle attempt hits instructor_display_name_required.
  const [listingBusyRosterId, setListingBusyRosterId] = useState<string | null>(null);
  const [listingErrors, setListingErrors] = useState<Record<string, string>>({});
  const [displayNamePromptRosterId, setDisplayNamePromptRosterId] = useState<string | null>(null);
  const [displayNameInput, setDisplayNameInput] = useState("");
  const [settingDisplayName, setSettingDisplayName] = useState(false);

  // spec 043 FR-009: the signed-in instructor's classroom defaults,
  // read once via whoami -- pre-fills the create-roster form's mode
  // and the assign-quiz form's due date (selectRoster below), both
  // still fully overridable before submit, and never applied
  // retroactively to an already-created roster or assignment.
  const [defaultDueDateOffsetDays, setDefaultDueDateOffsetDays] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listRosters(), getSubjects(), getWhoAmI()])
      .then(([rostersResponse, subjectsResponse, who]) => {
        if (cancelled) return;
        setRosters(rostersResponse.rosters);
        setSubjects(subjectsResponse.subjects);
        if (subjectsResponse.subjects.length > 0) {
          setNewSubjectId(subjectsResponse.subjects[0].subject_id);
        }
        setNewMode(who.default_enrollment_mode ?? "open");
        setDefaultDueDateOffsetDays(who.default_due_date_offset_days ?? null);
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
    setAssignDueAt(
      defaultDueDateOffsetDays != null
        ? localDateTimeInputValue(
            new Date(Date.now() + defaultDueDateOffsetDays * 24 * 60 * 60 * 1000),
          )
        : "",
    );
    setAssignTargetMode("all");
    setAssignSelectedLearnerIds([]);
    setAssignError(null);
    setResultsAssignmentId(null);
    setResultsDetail(null);
    setResultsError(null);
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

  async function handleViewResults(assignmentId: string) {
    if (!selectedRosterId) return;
    setResultsAssignmentId(assignmentId);
    setResultsLoading(true);
    setResultsError(null);
    try {
      const detail = await getAssignmentDetail(selectedRosterId, assignmentId);
      setResultsDetail(detail);
    } catch (error) {
      setResultsError(errorText(error));
    } finally {
      setResultsLoading(false);
    }
  }

  function handleCloseResults() {
    setResultsAssignmentId(null);
    setResultsDetail(null);
    setResultsError(null);
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
          is_listed: roster.is_listed,
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
          r.roster_id === rosterId
            ? { ...r, enrollment_mode: roster.enrollment_mode, is_listed: roster.is_listed }
            : r,
        ),
      );
      setJoinCodes((previous) => ({ ...previous, [rosterId]: roster.join_code }));
    } catch (error) {
      setDetailError(errorText(error));
    }
  }

  async function handleToggleListing(roster: RosterSummary, nextIsListed: boolean) {
    setListingBusyRosterId(roster.roster_id);
    setListingErrors((previous) => ({ ...previous, [roster.roster_id]: "" }));
    try {
      const updated = await updateRosterListing(
        roster.roster_id,
        roster.enrollment_mode,
        nextIsListed,
      );
      setRosters((previous) =>
        previous.map((r) =>
          r.roster_id === roster.roster_id ? { ...r, is_listed: updated.is_listed } : r,
        ),
      );
      setDisplayNamePromptRosterId(null);
    } catch (error) {
      if (apiErrorCode(error) === "instructor_display_name_required") {
        setDisplayNamePromptRosterId(roster.roster_id);
      } else {
        setListingErrors((previous) => ({ ...previous, [roster.roster_id]: errorText(error) }));
      }
    } finally {
      setListingBusyRosterId(null);
    }
  }

  async function handleSetDisplayNameAndRetryListing(roster: RosterSummary) {
    setSettingDisplayName(true);
    try {
      await updateInstructorDisplayName(displayNameInput.trim());
      setDisplayNameInput("");
      await handleToggleListing(roster, true);
    } catch (error) {
      setListingErrors((previous) => ({ ...previous, [roster.roster_id]: errorText(error) }));
    } finally {
      setSettingDisplayName(false);
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
    return <LoadingIndicator message="Loading rosters…" variant="professional" />;
  }

  if (loadError) {
    return (
      <div className="p-8">
        <p className="text-error">Something went wrong: {loadError}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-[1180px] grid-cols-1 gap-6 p-8 lg:grid-cols-[320px_minmax(0,1fr)] lg:items-start">
      <aside className="flex flex-col gap-4">
        <h1 className="font-heading text-[36px] font-bold leading-tight text-heading">
          Rosters
        </h1>

        <div className="flex flex-col gap-3" data-testid="roster-list">
          {rosters.length === 0 && <p className="text-sm text-muted">No rosters yet.</p>}
          {rosters.map((roster) => (
            <div
              key={roster.roster_id}
              className={`flex flex-col gap-2.5 rounded-2xl border-2 bg-surface px-4.5 py-3.5 ${
                selectedRosterId === roster.roster_id ? "border-primary" : "border-border"
              }`}
              data-testid={`roster-row-${roster.roster_id}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex flex-col gap-0.5">
                  <span className="font-extrabold text-heading">{roster.subject_id}</span>
                  <span className="text-sm text-muted">
                    {roster.enrollment_mode}
                    {joinCodes[roster.roster_id] && ` • code: ${joinCodes[roster.roster_id]}`}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => selectRoster(roster.roster_id)}
                  className="min-h-9 shrink-0 rounded-full bg-primary px-4 text-sm font-extrabold text-primary-foreground"
                >
                  Manage
                </button>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleSetMode(roster.roster_id, roster.enrollment_mode)}
                  className="min-h-9 rounded-full border-2 border-primary/25 px-3.5 text-sm font-bold text-primary"
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
                  className="min-h-9 rounded-full border-2 border-primary/25 px-3.5 text-sm font-bold text-primary"
                >
                  Switch to {roster.enrollment_mode === "open" ? "closed" : "open"}
                </button>
              </div>

              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={roster.is_listed}
                  disabled={
                    roster.enrollment_mode === "closed" || listingBusyRosterId === roster.roster_id
                  }
                  onChange={(event) => handleToggleListing(roster, event.target.checked)}
                />
                List in directory
              </label>
              <p className="text-xs text-muted">
                Visible to every guardian: your display name and this roster&apos;s join code.
              </p>
              {listingErrors[roster.roster_id] && (
                <p
                  className="text-sm text-error"
                  data-testid={`listing-error-${roster.roster_id}`}
                >
                  {listingErrors[roster.roster_id]}
                </p>
              )}
              {displayNamePromptRosterId === roster.roster_id && (
                <div
                  className="flex items-center gap-2"
                  data-testid={`display-name-prompt-${roster.roster_id}`}
                >
                  <input
                    type="text"
                    placeholder="Your display name"
                    value={displayNameInput}
                    onChange={(event) => setDisplayNameInput(event.target.value)}
                    className="min-h-9 rounded-xl border-2 border-primary/25 px-2.5 text-sm"
                  />
                  <button
                    type="button"
                    disabled={settingDisplayName || displayNameInput.trim() === ""}
                    onClick={() => handleSetDisplayNameAndRetryListing(roster)}
                    className="min-h-9 rounded-full bg-primary px-3.5 text-sm font-extrabold text-primary-foreground disabled:opacity-40"
                  >
                    {settingDisplayName ? "Saving…" : "Set your display name"}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        <form
          onSubmit={handleCreate}
          className="flex flex-col gap-3 rounded-2xl border-2 border-dashed border-primary/25 bg-surface px-4.5 py-4"
        >
          <h2 className="font-extrabold text-primary">+ Create a roster</h2>
          <label className="flex flex-col gap-1 text-sm font-extrabold">
            Subject
            <select
              value={newSubjectId}
              onChange={(event) => setNewSubjectId(event.target.value)}
              className="min-h-11 rounded-xl border-2 border-primary/25 px-3 font-bold"
            >
              {subjects.map((subject) => (
                <option key={subject.subject_id} value={subject.subject_id}>
                  {subject.display_name}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="flex flex-col gap-1.5 text-sm">
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
            <p className="text-sm text-error" data-testid="create-roster-error">
              {createError}
            </p>
          )}
          <button
            type="submit"
            disabled={creating || !newSubjectId}
            className="min-h-11 self-start rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
          >
            {creating ? "Creating…" : "Create roster"}
          </button>
        </form>
      </aside>

      {selectedRosterId && (
        <div className="flex flex-col gap-5">
          {detailLoading && <LoadingIndicator variant="professional" compact />}
          {detailError && (
            <p className="text-sm text-error" data-testid="roster-detail-error">
              {detailError}
            </p>
          )}

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6">
              <h3 className="text-[13px] font-extrabold tracking-[0.08em] text-primary">
                PENDING REQUESTS
              </h3>
              {requests.length === 0 && <p className="text-sm text-muted">No pending requests.</p>}
              {requests.map((request) => (
                <div
                  key={request.enrollment_request_id}
                  className="flex items-center justify-between gap-3 rounded-2xl bg-warning/10 px-3.5 py-3 text-sm"
                >
                  <span>Learner {request.learner_id}</span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleApprove(request.enrollment_request_id)}
                      className="min-h-9 rounded-full bg-primary px-3.5 font-extrabold text-primary-foreground"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDecline(request.enrollment_request_id)}
                      className="min-h-9 rounded-full border-2 border-primary/25 px-3.5 font-bold text-primary"
                    >
                      Decline
                    </button>
                  </div>
                </div>
              ))}
            </section>

            <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6">
              <h3 className="text-[13px] font-extrabold tracking-[0.08em] text-primary">
                ENROLLED LEARNERS · {enrollments.length}
              </h3>
              {enrollments.length === 0 && <p className="text-sm text-muted">No learners enrolled yet.</p>}
              <div className="flex flex-col gap-1.5">
                {enrollments.map((learner) => (
                  <div
                    key={learner.learner_id}
                    className="flex items-center justify-between gap-3 text-sm"
                  >
                    <span className="rounded-full border border-border bg-surface-subtle px-3.5 py-1.5 font-bold">
                      {learner.display_name}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleUnenroll(learner.learner_id)}
                      className="min-h-8 rounded-full border-2 border-primary/25 px-3 text-sm font-bold text-primary"
                    >
                      Unenroll
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <form
            onSubmit={handleCreateAssignment}
            data-testid="assign-quiz-form"
            className="flex flex-col gap-4 rounded-card border border-border bg-surface p-7"
          >
            <h3 className="font-heading text-2xl font-bold text-heading">Assign a quiz</h3>
            <label className="flex flex-col gap-1.5 text-sm font-extrabold">
              Topic ids (comma-separated)
              <input
                type="text"
                value={assignTopicIds}
                onChange={(event) => setAssignTopicIds(event.target.value)}
                data-testid="assign-topic-ids"
                className="min-h-11 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
              />
            </label>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <label className="flex flex-col gap-1.5 text-sm font-extrabold">
                Question count
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={assignQuestionCount}
                  onChange={(event) => setAssignQuestionCount(Number(event.target.value))}
                  data-testid="assign-question-count"
                  className="min-h-11 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-sm font-extrabold">
                Due date (optional)
                <input
                  type="datetime-local"
                  value={assignDueAt}
                  onChange={(event) => setAssignDueAt(event.target.value)}
                  data-testid="assign-due-at"
                  className="min-h-11 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
                />
              </label>
              <fieldset className="flex flex-col gap-1.5 text-sm">
                <legend className="font-extrabold">Assign to</legend>
                <label className="flex min-h-7 items-center gap-2">
                  <input
                    type="radio"
                    name="assign_target_mode"
                    checked={assignTargetMode === "all"}
                    onChange={() => setAssignTargetMode("all")}
                    data-testid="assign-target-all"
                  />
                  All enrolled learners
                </label>
                <label className="flex min-h-7 items-center gap-2">
                  <input
                    type="radio"
                    name="assign_target_mode"
                    checked={assignTargetMode === "subset"}
                    onChange={() => setAssignTargetMode("subset")}
                    data-testid="assign-target-subset"
                  />
                  Choose learners
                </label>
              </fieldset>
            </div>
            {assignTargetMode === "subset" && (
              <div className="flex flex-col gap-1 pl-2">
                {enrollments.length === 0 && <p className="text-sm">No learners enrolled yet.</p>}
                {enrollments.map((learner) => (
                  <label key={learner.learner_id} className="flex items-center gap-2 text-sm">
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
            {assignError && (
              <p className="text-sm text-error" data-testid="assign-quiz-error">
                {assignError}
              </p>
            )}
            <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
              <span className="text-sm text-muted">
                Difficulty adapts to each learner during the quiz.
              </span>
              <button
                type="submit"
                disabled={
                  assigning ||
                  assignTopicIds.trim().length === 0 ||
                  (assignTargetMode === "subset" && assignSelectedLearnerIds.length === 0)
                }
                className="min-h-12 rounded-full bg-primary px-6 font-extrabold text-primary-foreground disabled:opacity-40"
              >
                {assigning ? "Assigning…" : "Assign quiz"}
              </button>
            </div>
          </form>

          <section
            className="flex flex-col gap-3 rounded-card border border-border bg-surface p-7"
            data-testid="assignment-list"
          >
            <h3 className="font-heading text-2xl font-bold text-heading">Assignments</h3>
            {assignments.length === 0 && <p className="text-sm text-muted">No assignments yet.</p>}
            {assignments.map((assignment) => (
              <div
                key={assignment.assignment_id}
                data-testid={`assignment-${assignment.assignment_id}`}
                className="flex items-center justify-between gap-3 rounded-2xl bg-surface-subtle px-4.5 py-3.5 text-sm"
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
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleViewResults(assignment.assignment_id)}
                    className="min-h-9 rounded-full border-2 border-primary/25 px-3.5 text-sm font-bold text-primary"
                  >
                    View results
                  </button>
                  {!assignment.cancelled_at && (
                    <button
                      type="button"
                      onClick={() => handleCancelAssignment(assignment.assignment_id)}
                      className="min-h-9 rounded-full border-2 border-primary/25 px-3.5 text-sm font-bold text-primary"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            ))}
          </section>

          {resultsAssignmentId && (
            <section
              className="flex flex-col gap-3 rounded-card border border-border bg-surface p-7"
              data-testid="assignment-results"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-heading text-xl font-bold text-heading">Results</h3>
                <button
                  type="button"
                  onClick={handleCloseResults}
                  className="text-sm font-bold text-muted underline"
                >
                  Close
                </button>
              </div>
              {resultsLoading && <LoadingIndicator variant="professional" compact />}
              {resultsError && (
                <p className="text-sm text-error" data-testid="assignment-results-error">
                  {resultsError}
                </p>
              )}
              {resultsDetail && (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-[13px] font-extrabold tracking-[0.06em] text-muted">
                      <th className="pb-2 font-extrabold">LEARNER</th>
                      <th className="pb-2 font-extrabold">STATUS</th>
                      <th className="pb-2 font-extrabold">SCORE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultsDetail.learners.map((learner) => (
                      <tr
                        key={learner.learner_id}
                        data-testid={`assignment-result-${learner.learner_id}`}
                        className="border-t border-border"
                      >
                        <td className="py-2 font-bold">{learner.display_name}</td>
                        <td className="py-2">{learner.status}</td>
                        <td className="py-2 font-extrabold">
                          {learner.score
                            ? `${learner.score.correct} / ${learner.score.total}`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getActivitySummary,
  getMasteryState,
  getTopicPriorityPreview,
  listLearnerEnrollments,
  unenrollLearner,
  type MyLearnerEnrollment,
} from "@/services/api";
import { enterRealLearnerSession } from "@/lib/visitor-state";
import { avatarClassName } from "@/lib/avatar-color";
import JoinRosterForm from "@/components/JoinRosterForm";
import ClassDirectoryBrowse from "@/components/ClassDirectoryBrowse";
import LearnerAssignments from "@/components/LearnerAssignments";
import GuardianAssignQuiz from "@/components/GuardianAssignQuiz";
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
//
// spec 044 FR-002-FR-006 (US1): a learner can now show *every*
// enrollment, not just one -- one tab per enrollment, switching which
// enrollment's stat tiles/assignments/standards/careers are shown,
// "Add a subject" offered regardless of count, no tab chrome for
// exactly one enrollment.

// Spec 019 FR-009/research.md Decision 6's same grade bands, looked up
// independently here (not shared code with `lib/pacing.ts` or the
// backend's `MediationTier`, same precedent those already establish --
// each stays separately product-tunable).
function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

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
  enrollments: MyLearnerEnrollment[];
  // spec 044 FR-004: after a successful "Add a subject" join, the card
  // needs the guardian's fresh enrollment list (with `grade` -- not
  // returned by `listLearnerEnrollments`) to select the new tab --
  // cheapest source of that is re-running the same `GET /api/learners/
  // mine` fetch the parent page already made, not a second endpoint.
  onEnrollmentsChanged?: () => void;
}

export default function GuardianLearnerCard({
  learnerId,
  displayName,
  enrollments,
  onEnrollmentsChanged,
}: GuardianLearnerCardProps) {
  const router = useRouter();
  const [topicsMastered, setTopicsMastered] = useState<number | null>(null);
  const [questionsThisWeek, setQuestionsThisWeek] = useState<number | null>(null);
  const [workingOn, setWorkingOn] = useState<string | null>(null);
  // v041 mockup: "Join a class" is a two-tab switcher (Browse classes /
  // Have a code?), not both forms stacked -- defaults to Browse, same
  // as the mockup's own default state.
  const [joinTab, setJoinTab] = useState<"browse" | "code">("browse");
  // spec 044 FR-003/FR-006: "Add a subject" button is always visible
  // directly under the name/enrollment-summary line for a 0- or
  // 1-enrollment learner (never hidden behind its own open form, unlike
  // the >1 tablist's trigger which already behaved this way). Starts
  // open for a brand-new, zero-enrollment learner so the join form is
  // the first thing they see, same nudge as before this fix.
  const [addOpen, setAddOpen] = useState(enrollments.length === 0);
  const [selected, setSelected] = useState(0);
  // Bumped after a successful GuardianAssignQuiz submission to force
  // LearnerAssignments to remount and refetch, since the two components
  // are siblings with no shared data/refresh callback otherwise.
  const [assignmentsRefreshKey, setAssignmentsRefreshKey] = useState(0);
  // spec 044 FR-024 (US5): one round-trip, keyed by roster_id -- the
  // same `listLearnerEnrollments` call GuardianAssignQuiz already makes
  // per-roster, reused here to decide "Take placement" per tile.
  // Defaults to true (hidden) for a roster not yet resolved, matching
  // the fail-silent-enrichment precedent the rest of this card already
  // follows for stat tiles.
  const [hasStartingGradeByRosterId, setHasStartingGradeByRosterId] = useState<
    Record<string, boolean>
  >({});
  // spec 044 FR-034/FR-035 (US7): confirmation-gated removal of the
  // selected tab's enrollment -- `unenrollLearner` already exists
  // (api.ts), already used by the instructor-side roster flow; this is
  // its first guardian-side caller.
  const [removeConfirmOpen, setRemoveConfirmOpen] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listLearnerEnrollments(learnerId)
      .then((result) => {
        if (cancelled) return;
        setHasStartingGradeByRosterId(
          Object.fromEntries(result.enrollments.map((e) => [e.roster_id, e.has_starting_grade])),
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [learnerId]);

  // spec 044 FR-004: when the guardian's fresh enrollment list grows by
  // one (a successful join), select that new tab; every other existing
  // tab stays exactly as it was. Diffs by roster_id rather than array
  // identity/length alone, since `onEnrollmentsChanged` re-fetches the
  // guardian's whole learner list and always returns a new array.
  const previousRosterIdsRef = useRef<Set<string> | null>(null);
  useEffect(() => {
    const currentIds = enrollments.map((e) => e.roster_id);
    const previousIds = previousRosterIdsRef.current;
    if (previousIds) {
      const newIndex = currentIds.findIndex((id) => !previousIds.has(id));
      if (newIndex !== -1) {
        setSelected(newIndex);
        setAddOpen(false);
      } else {
        setSelected((current) => Math.min(current, Math.max(currentIds.length - 1, 0)));
        // spec 044 FR-037 (US7): removing the last enrollment reverts to
        // the same zero-enrollment state a learner who never joined
        // anything starts in -- including the join section already
        // being open (this component's own initial-mount default).
        if (currentIds.length === 0) setAddOpen(true);
      }
    }
    previousRosterIdsRef.current = new Set(currentIds);
  }, [enrollments]);

  const selectedEnrollment = enrollments[selected] ?? null;

  // spec 041 FR-016/T039: opens this learner's own real session
  // (Dashboard/Practice/Mastery/Tutor), mirroring the demo learner's
  // flow -- omitted entirely for a learner not yet in a class.
  function handleOpenDashboard() {
    enterRealLearnerSession(learnerId, displayName);
    router.push("/dashboard");
  }

  // spec 044 FR-007/FR-009 (US2): same real-session hand-off as "Open
  // {name}'s learning", but landing directly on a running 15-minute
  // timed session for this one tile's subject instead of the dashboard.
  function handleStartPractice(subjectId: string) {
    enterRealLearnerSession(learnerId, displayName);
    router.push(`/practice?subject=${subjectId}&autostart=1`);
  }

  // spec 044 FR-024/FR-025 (US5): same real-session hand-off, landing on
  // that subject's existing placement flow directly.
  function handleTakePlacement(subjectId: string) {
    enterRealLearnerSession(learnerId, displayName);
    router.push(`/placement?subject=${subjectId}`);
  }

  // Same real-session hand-off, landing on the dedicated assigned-quiz
  // page -- used for both a fresh "Start" and a "Resume" of a stuck
  // in_progress attempt; the page's own mount effect decides which
  // based on the assignment's current status.
  function handleOpenAssignment(assignmentId: string) {
    enterRealLearnerSession(learnerId, displayName);
    router.push(`/assignment?assignmentId=${assignmentId}`);
  }

  function handleJoined() {
    setAddOpen(false);
    onEnrollmentsChanged?.();
  }

  // spec 044 FR-034/FR-036/FR-037 (US7): deletes only the `Enrollment`
  // row (`DELETE /api/rosters/{roster_id}/enrollments/{learner_id}`,
  // already in production use on the instructor side) -- every other
  // table (MasteryState, GeneratedQuestion, GradeProgress) is untouched,
  // and removing the learner's last enrollment is allowed, reverting the
  // card to FR-006's zero-enrollment state once `onEnrollmentsChanged`
  // re-fetches.
  async function handleRemoveSubject() {
    if (!selectedEnrollment) return;
    setRemoving(true);
    setRemoveError(null);
    try {
      await unenrollLearner(selectedEnrollment.roster_id, learnerId);
      setRemoveConfirmOpen(false);
      onEnrollmentsChanged?.();
    } catch (error) {
      setRemoveError(errorText(error));
    } finally {
      setRemoving(false);
    }
  }

  useEffect(() => {
    if (!selectedEnrollment) return;
    let cancelled = false;
    const { subject_id: subjectId } = selectedEnrollment;
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
  }, [learnerId, selectedEnrollment]);

  const tier = gradeBandTier(selectedEnrollment?.grade ?? 9);
  const hasEnrollments = enrollments.length > 0;

  const joinSection = (
    <section className="flex flex-col gap-3.5 border-t border-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-heading text-xl font-bold text-heading">
          {hasEnrollments ? "Add a subject" : "Join a class"}
        </h3>
        <div role="tablist" aria-label="How to join" className="flex gap-1 rounded-full bg-surface-subtle p-1">
          <button
            type="button"
            role="tab"
            aria-selected={joinTab === "browse"}
            onClick={() => setJoinTab("browse")}
            className={`min-h-10 rounded-full px-4 text-sm font-extrabold ${joinTab === "browse" ? "bg-surface text-heading shadow-sm" : "text-muted"}`}
          >
            Browse classes
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={joinTab === "code"}
            onClick={() => setJoinTab("code")}
            className={`min-h-10 rounded-full px-4 text-sm font-extrabold ${joinTab === "code" ? "bg-surface text-heading shadow-sm" : "text-muted"}`}
          >
            Have a code?
          </button>
        </div>
      </div>
      {joinTab === "browse" ? (
        <ClassDirectoryBrowse
          learnerId={learnerId}
          onNeedCode={() => setJoinTab("code")}
          onJoined={handleJoined}
        />
      ) : (
        <JoinRosterForm learnerId={learnerId} onJoined={handleJoined} />
      )}
    </section>
  );

  return (
    <article
      data-testid={`guardian-learner-card-${learnerId}`}
      className="flex flex-col gap-4.5 rounded-card border border-border bg-surface p-7"
    >
      <div className="flex flex-wrap items-center gap-4">
        <span
          className={`flex h-14 w-14 items-center justify-center rounded-2xl font-heading text-2xl font-bold ${avatarClassName(learnerId)}`}
        >
          {displayName.charAt(0).toUpperCase()}
        </span>
        <div className="flex-grow">
          <h2 className="font-heading text-[26px] font-bold leading-tight text-heading">
            {displayName}
          </h2>
          <span className="text-[15px] text-muted">
            {!hasEnrollments
              ? "Not in a class yet"
              : enrollments.length === 1
                ? `Grade ${enrollments[0].grade ?? "—"} · ${formatTopicId(enrollments[0].subject_id)}`
                : `${enrollments.length} classes · ${enrollments.map((e) => formatTopicId(e.subject_id)).join(", ")}`}
          </span>
        </div>
        {hasEnrollments && (
          <span className="rounded-full bg-primary-subtle px-3 py-0.5 text-[13px] font-extrabold text-heading">
            {tier.label}
          </span>
        )}
        {hasEnrollments && (
          <button
            type="button"
            onClick={handleOpenDashboard}
            className="inline-flex min-h-12 items-center gap-2 rounded-full bg-primary px-5.5 text-[15px] font-extrabold text-primary-foreground"
          >
            Open {displayName}&apos;s learning
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M5 12h14" />
              <path d="m13 6 6 6-6 6" />
            </svg>
          </button>
        )}
      </div>

      {(!hasEnrollments || enrollments.length === 1) && (
        <button
          type="button"
          onClick={() => setAddOpen((open) => !open)}
          aria-expanded={addOpen}
          className="flex min-h-12 w-fit items-center gap-2 rounded-full border-2 border-dashed border-border px-4.5 font-extrabold text-primary"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 5v14" />
            <path d="M5 12h14" />
          </svg>
          Add a subject
        </button>
      )}

      {(!hasEnrollments || enrollments.length === 1) && addOpen && joinSection}

      {hasEnrollments && (
        <>
          {enrollments.length > 1 && (
            <div
              role="tablist"
              aria-label={`${displayName}'s subjects`}
              className="flex flex-wrap gap-2"
            >
              {enrollments.map((enrollment, index) => {
                const active = index === selected;
                return (
                  <button
                    key={enrollment.roster_id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setSelected(index)}
                    className={`flex min-h-14 flex-col items-start justify-center rounded-2xl px-4 py-1.5 text-left ${
                      active
                        ? "bg-primary text-primary-foreground"
                        : "border-2 border-border bg-surface text-heading"
                    }`}
                  >
                    <span className="text-[15px] font-extrabold">
                      {formatTopicId(enrollment.subject_id)}
                    </span>
                    <span className="text-[13px] font-bold opacity-85">
                      {enrollment.grade != null ? `Grade ${enrollment.grade}` : "Ungraded"}
                    </span>
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => setAddOpen((open) => !open)}
                aria-expanded={addOpen}
                className="flex min-h-14 items-center gap-2 rounded-2xl border-2 border-dashed border-border px-4.5 font-extrabold text-primary"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 5v14" />
                  <path d="M5 12h14" />
                </svg>
                Add a subject
              </button>
            </div>
          )}

          {enrollments.length > 1 && addOpen && joinSection}

          {selectedEnrollment && (
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
              <p className="-mt-2 text-sm text-muted">
                Opens {displayName}&apos;s dashboard, practice, mastery and AI Tutor on this device.
                Return here to end the session.
              </p>

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => handleStartPractice(selectedEnrollment.subject_id)}
                  className="flex min-h-11 w-fit items-center gap-2 rounded-full border-2 border-border px-4.5 font-extrabold text-heading"
                >
                  Start practice
                </button>
                {hasStartingGradeByRosterId[selectedEnrollment.roster_id] === false && (
                  <button
                    type="button"
                    onClick={() => handleTakePlacement(selectedEnrollment.subject_id)}
                    className="flex min-h-11 w-fit items-center gap-2 rounded-full border-2 border-border px-4.5 font-extrabold text-heading"
                  >
                    Take placement
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setRemoveError(null);
                    setRemoveConfirmOpen(true);
                  }}
                  className="flex min-h-11 w-fit items-center gap-2 rounded-full border-2 border-border px-4.5 font-extrabold text-error"
                >
                  Remove
                </button>
              </div>

              <LearnerAssignments
                key={assignmentsRefreshKey}
                learnerId={learnerId}
                rosterId={selectedEnrollment.roster_id}
                onOpenAssignment={handleOpenAssignment}
              />
              <p className="text-sm text-muted">{tier.note}</p>
              <GuardianAssignQuiz
                learnerId={learnerId}
                rosterId={selectedEnrollment.roster_id}
                onAssigned={() => setAssignmentsRefreshKey((key) => key + 1)}
              />

              <details className="border-t border-border pt-3.5">
                <summary className="flex min-h-11 cursor-pointer items-center font-extrabold text-primary">
                  Standards covered
                </summary>
                <div className="flex flex-col gap-2 pt-1.5">
                  <GuardianLearnerStandards
                    learnerId={learnerId}
                    subjectId={selectedEnrollment.subject_id}
                  />
                </div>
              </details>

              <div className="flex flex-col gap-3.5 border-t border-border pt-3.5">
                <CareerConnectionsToggle learnerId={learnerId} displayName={displayName} />
                <details>
                  <summary className="flex min-h-11 cursor-pointer items-center font-extrabold text-primary">
                    See the career connections
                  </summary>
                  <div className="flex flex-col gap-2 pt-1.5">
                    <GuardianLearnerCareerConnections
                      learnerId={learnerId}
                      subjectId={selectedEnrollment.subject_id}
                    />
                  </div>
                </details>
              </div>
            </>
          )}
        </>
      )}

      {removeConfirmOpen && selectedEnrollment && (
        <div
          role="alertdialog"
          aria-modal="true"
          data-testid="remove-subject-dialog"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        >
          <div className="flex max-w-sm flex-col gap-4 rounded-card border border-border bg-surface p-6">
            <p className="text-[15px] font-bold text-heading">
              Remove {displayName} from {formatTopicId(selectedEnrollment.subject_id)}? They&apos;ll
              need to rejoin to see it again.
            </p>
            {removeError && <p className="text-sm text-error">{removeError}</p>}
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setRemoveConfirmOpen(false)}
                disabled={removing}
                className="min-h-11 rounded-full border-2 border-border px-4.5 font-extrabold text-heading disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRemoveSubject}
                disabled={removing}
                className="min-h-11 rounded-full bg-error px-4.5 font-extrabold text-white disabled:opacity-40"
              >
                {removing ? "Removing…" : "Remove"}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

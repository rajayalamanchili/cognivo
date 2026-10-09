"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  ApiError,
  changeInstructorPassword,
  getDeletionRequestStatus,
  getWhoAmI,
  listRosterEnrollments,
  listRosters,
  submitDeletionRequest,
  updateInstructorMe,
  type DeletionRequestStatusResponse,
  type DeletionTargetType,
  type EnrollmentMode,
  type InstructorMeUpdate,
  type Theme,
} from "@/services/api";
import LoadingIndicator from "@/components/LoadingIndicator";
import ToggleSwitch from "@/components/ToggleSwitch";
import { notifySessionChanged } from "@/lib/visitor-state";

// spec 043 FR-007/FR-008/FR-009/FR-010/FR-011/FR-012: a genuinely new
// Settings screen for the instructor role, built directly in the
// mockup's visual language (InstructorSettings.dc.html) -- almost
// entirely a mirror of the guardian Settings page (spec 041) with its
// instructor-specific field set swapped in.

interface InstructorState {
  instructorId: string | null;
  isDemo: boolean;
  email: string | null;
  displayName: string;
  theme: Theme;
  largerText: boolean;
  reduceMotion: boolean;
  notificationsEnabled: boolean;
  defaultEnrollmentMode: EnrollmentMode;
  defaultDueDateOffsetDays: number | null;
}

interface PickableLearner {
  learnerId: string;
  displayName: string;
  subjectId: string;
}

const SETTINGS_SECTIONS = [
  { id: "account", label: "Account" },
  { id: "classroom", label: "Classroom defaults" },
  { id: "notify", label: "Notifications" },
  { id: "display", label: "Display" },
  { id: "privacy", label: "Privacy & data" },
] as const;

function SectionCard({
  id,
  title,
  children,
}: {
  id: (typeof SETTINGS_SECTIONS)[number]["id"];
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="flex flex-col gap-3 rounded-card border border-border bg-surface p-7">
      <h2 className="font-heading text-2xl font-bold text-heading">{title}</h2>
      {children}
    </section>
  );
}

function ToggleRow({
  title,
  subtitle,
  checked,
  onChange,
  disabled,
}: {
  title: string;
  subtitle?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-5 border-t border-border py-3 first:border-t-0">
      <span>
        <strong className="font-extrabold">{title}</strong>
        {subtitle && <span className="block text-sm text-muted">{subtitle}</span>}
      </span>
      <ToggleSwitch checked={checked} onChange={onChange} disabled={disabled} />
    </label>
  );
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function InstructorSettingsFlow() {
  const [instructor, setInstructor] = useState<InstructorState | null>(null);
  const [learners, setLearners] = useState<PickableLearner[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [displayNameInput, setDisplayNameInput] = useState("");
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [accountSaved, setAccountSaved] = useState(false);

  const [pwOpen, setPwOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordChanged, setPasswordChanged] = useState(false);

  const [dueDateInput, setDueDateInput] = useState("");
  const [classroomSaving, setClassroomSaving] = useState(false);
  const [classroomError, setClassroomError] = useState<string | null>(null);
  const [classroomSaved, setClassroomSaved] = useState(false);

  const [deleteLearnerId, setDeleteLearnerId] = useState("");
  const [learnerDeletion, setLearnerDeletion] = useState<DeletionRequestStatusResponse | null>(
    null,
  );
  const [accountDeletion, setAccountDeletion] = useState<DeletionRequestStatusResponse | null>(
    null,
  );
  const [deletionError, setDeletionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getWhoAmI()
      .then(async (who) => {
        if (cancelled) return;
        if (who.account_type !== "instructor" && who.account_type !== "demo_instructor") {
          setLoadError("Please sign in as an instructor first.");
          return;
        }
        const isDemo = who.account_type === "demo_instructor";
        setInstructor({
          instructorId: who.instructor_id ?? null,
          isDemo,
          email: isDemo ? null : who.identifier ?? null,
          displayName: who.name ?? "",
          theme: who.theme ?? "system",
          largerText: who.larger_text ?? false,
          reduceMotion: who.reduce_motion ?? false,
          notificationsEnabled: who.notifications_enabled ?? true,
          defaultEnrollmentMode: who.default_enrollment_mode ?? "open",
          defaultDueDateOffsetDays: who.default_due_date_offset_days ?? null,
        });
        setDisplayNameInput(who.name ?? "");
        setDueDateInput(
          who.default_due_date_offset_days != null ? String(who.default_due_date_offset_days) : "",
        );

        if (isDemo) return;
        const rostersResponse = await listRosters();
        const perRoster = await Promise.all(
          rostersResponse.rosters.map((roster) => listRosterEnrollments(roster.roster_id)),
        );
        if (cancelled) return;
        setLearners(
          rostersResponse.rosters.flatMap((roster, index) =>
            perRoster[index].enrollments.map((learner) => ({
              learnerId: learner.learner_id,
              displayName: learner.display_name,
              subjectId: roster.subject_id,
            })),
          ),
        );
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(errorText(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function savePreference(update: InstructorMeUpdate) {
    if (!instructor) return;
    const result = await updateInstructorMe(update);
    setInstructor((previous) =>
      previous && {
        ...previous,
        displayName: result.display_name ?? "",
        theme: result.theme ?? previous.theme,
        largerText: result.larger_text ?? previous.largerText,
        reduceMotion: result.reduce_motion ?? previous.reduceMotion,
        notificationsEnabled: result.notifications_enabled ?? previous.notificationsEnabled,
        defaultEnrollmentMode: result.default_enrollment_mode ?? previous.defaultEnrollmentMode,
        defaultDueDateOffsetDays: result.default_due_date_offset_days,
      },
    );
    // Display/accessibility prefs (theme/larger text/reduce motion) are
    // applied globally by AccountDisplayPreferences.tsx -- without this
    // signal, a toggle here would persist but not visibly apply until
    // the next full page load (same reasoning guardian Settings follows).
    notifySessionChanged();
  }

  async function handleSaveAccount(event: FormEvent) {
    event.preventDefault();
    setAccountSaving(true);
    setAccountError(null);
    setAccountSaved(false);
    try {
      await savePreference({ display_name: displayNameInput });
      setAccountSaved(true);
    } catch (error) {
      setAccountError(errorText(error));
    } finally {
      setAccountSaving(false);
    }
  }

  async function handleChangePassword(event: FormEvent) {
    event.preventDefault();
    setPasswordSaving(true);
    setPasswordError(null);
    setPasswordChanged(false);
    try {
      await changeInstructorPassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setPasswordChanged(true);
    } catch (error) {
      setPasswordError(
        error instanceof ApiError && error.status === 401
          ? "Current password is incorrect."
          : errorText(error),
      );
    } finally {
      setPasswordSaving(false);
    }
  }

  async function handleSaveClassroomDefaults(event: FormEvent) {
    event.preventDefault();
    if (!instructor) return;
    setClassroomSaving(true);
    setClassroomError(null);
    setClassroomSaved(false);
    const trimmed = dueDateInput.trim();
    const parsed = trimmed === "" ? null : Number(trimmed);
    if (parsed !== null && (!Number.isInteger(parsed) || parsed <= 0)) {
      setClassroomError("Due after must be a positive number of days, or left blank.");
      setClassroomSaving(false);
      return;
    }
    try {
      await savePreference({
        default_enrollment_mode: instructor.defaultEnrollmentMode,
        default_due_date_offset_days: parsed,
      });
      setClassroomSaved(true);
    } catch (error) {
      setClassroomError(errorText(error));
    } finally {
      setClassroomSaving(false);
    }
  }

  async function requestDeletion(targetType: DeletionTargetType, targetId: string) {
    setDeletionError(null);
    try {
      const submitted = await submitDeletionRequest(targetType, targetId);
      const status: DeletionRequestStatusResponse = { ...submitted, completed_at: null };
      if (targetType === "learner") setLearnerDeletion(status);
      else setAccountDeletion(status);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const existingId = (error.body as { deletion_request_id?: string } | undefined)
          ?.deletion_request_id;
        if (existingId) {
          const current = await getDeletionRequestStatus(existingId);
          if (targetType === "learner") setLearnerDeletion(current);
          else setAccountDeletion(current);
          return;
        }
      }
      setDeletionError(errorText(error));
    }
  }

  if (loadError) {
    return (
      <div className="p-8">
        <p className="text-error">{loadError}</p>
      </div>
    );
  }

  if (!instructor) {
    return <LoadingIndicator message="Loading your settings…" variant="professional" />;
  }

  const demo = instructor.isDemo;

  return (
    <div className="mx-auto grid w-full max-w-[1180px] grid-cols-1 gap-8 p-8 lg:grid-cols-[240px_minmax(0,1fr)] lg:items-start">
      <nav aria-label="Settings sections" className="flex flex-col gap-1 lg:sticky lg:top-6">
        <h1 className="mb-2 font-heading text-[36px] font-bold leading-tight text-heading">
          Settings
        </h1>
        {SETTINGS_SECTIONS.map((section) => (
          <a
            key={section.id}
            href={`#${section.id}`}
            className="rounded-xl px-3.5 py-2.5 font-bold text-muted hover:bg-surface-subtle hover:text-heading"
          >
            {section.label}
          </a>
        ))}
      </nav>

      <div className="flex flex-col gap-5">
        <SectionCard id="account" title="Account">
          <form onSubmit={handleSaveAccount} className="grid grid-cols-2 gap-4">
            <label className="flex flex-col gap-1.5 text-sm font-extrabold">
              Display name
              <span className="font-normal text-sm text-muted">
                Shown to learners and guardians on assigned quizzes
              </span>
              <input
                type="text"
                value={displayNameInput}
                onChange={(event) => setDisplayNameInput(event.target.value)}
                className="min-h-12 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
              />
            </label>
            {instructor.email && (
              <label className="flex flex-col gap-1.5 text-sm font-extrabold">
                Email
                <span className="font-normal text-sm text-muted">
                  Used to sign in; never shown to learners
                </span>
                <input
                  type="email"
                  value={instructor.email}
                  disabled
                  className="min-h-12 rounded-xl border-2 border-border bg-surface-subtle px-3.5 font-normal text-muted"
                />
              </label>
            )}
            <div className="col-span-2 flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={accountSaving}
                className="min-h-11 rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
              >
                {accountSaving ? "Saving…" : "Save changes"}
              </button>
              {!demo && (
                <button
                  type="button"
                  onClick={() => setPwOpen((open) => !open)}
                  aria-expanded={pwOpen}
                  className="min-h-11 rounded-full border-2 border-primary/25 px-5 font-extrabold text-primary"
                >
                  Change password
                </button>
              )}
              {accountSaved && <span className="text-sm text-success">Saved.</span>}
              {accountError && <span className="text-sm text-error">{accountError}</span>}
            </div>
          </form>
          {pwOpen && !demo && (
            <form
              onSubmit={handleChangePassword}
              className="grid grid-cols-1 items-end gap-3 rounded-2xl bg-surface-subtle p-4.5 sm:grid-cols-3"
            >
              <label className="flex flex-col gap-1.5 text-sm font-extrabold">
                Current password
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  className="min-h-11 rounded-xl border-2 border-primary/25 bg-surface px-3.5 font-normal"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-sm font-extrabold">
                New password
                <input
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  className="min-h-11 rounded-xl border-2 border-primary/25 bg-surface px-3.5 font-normal"
                />
              </label>
              <button
                type="submit"
                disabled={passwordSaving}
                className="min-h-11 rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
              >
                {passwordSaving ? "Changing…" : "Update password"}
              </button>
              {passwordChanged && (
                <span className="col-span-full text-sm text-success">Password changed.</span>
              )}
              {passwordError && (
                <span className="col-span-full text-sm text-error">{passwordError}</span>
              )}
            </form>
          )}
        </SectionCard>

        <SectionCard id="classroom" title="Classroom defaults">
          <p className="-mt-1 text-sm text-muted">
            Starting values for new rosters and quizzes. You can still change each one.
          </p>
          <form onSubmit={handleSaveClassroomDefaults} className="flex flex-col gap-4">
            <fieldset className="flex flex-col gap-2">
              <legend className="text-sm font-extrabold">New rosters are</legend>
              <div className="grid grid-cols-2 gap-2.5">
                {(["open", "closed"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    role="radio"
                    aria-checked={instructor.defaultEnrollmentMode === mode}
                    onClick={() =>
                      setInstructor((previous) =>
                        previous && { ...previous, defaultEnrollmentMode: mode },
                      )
                    }
                    className={`rounded-2xl px-4.5 py-3.5 text-left font-bold ${
                      instructor.defaultEnrollmentMode === mode
                        ? "border-2 border-primary bg-primary-subtle text-heading"
                        : "border-2 border-border bg-surface text-muted"
                    }`}
                  >
                    {mode === "open" ? "Open" : "Closed"}
                  </button>
                ))}
              </div>
            </fieldset>
            <label className="flex flex-col gap-1.5 text-sm font-extrabold">
              Due after (days, optional)
              <input
                type="number"
                min={1}
                placeholder="No due date"
                value={dueDateInput}
                onChange={(event) => setDueDateInput(event.target.value)}
                className="min-h-12 max-w-[200px] rounded-xl border-2 border-primary/25 px-3.5 font-normal"
              />
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={classroomSaving || demo}
                className="min-h-11 self-start rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
              >
                {classroomSaving ? "Saving…" : "Save changes"}
              </button>
              {classroomSaved && <span className="text-sm text-success">Saved.</span>}
              {classroomError && <span className="text-sm text-error">{classroomError}</span>}
            </div>
          </form>
        </SectionCard>

        <SectionCard id="notify" title="Notifications">
          <ToggleRow
            title="Notify me"
            subtitle="Saved to your account -- Cognivo doesn't send any notifications yet"
            checked={instructor.notificationsEnabled}
            disabled={demo}
            onChange={(next) => savePreference({ notifications_enabled: next })}
          />
        </SectionCard>

        <SectionCard id="display" title="Display">
          <ToggleRow
            title="Larger text"
            subtitle="Bumps body text up a size across instructor pages"
            checked={instructor.largerText}
            disabled={demo}
            onChange={(next) => savePreference({ larger_text: next })}
          />
          <ToggleRow
            title="Reduce motion"
            subtitle="Turns off celebration animations"
            checked={instructor.reduceMotion}
            disabled={demo}
            onChange={(next) => savePreference({ reduce_motion: next })}
          />
          <label className="flex items-center justify-between gap-5 border-t border-border py-3">
            <span>
              <strong className="font-extrabold">Theme</strong>
              <span className="block text-sm text-muted">Match this device, or pick one</span>
            </span>
            <select
              value={instructor.theme}
              disabled={demo}
              onChange={(event) => savePreference({ theme: event.target.value as Theme })}
              className="min-h-11 rounded-xl border-2 border-primary/25 px-3 font-bold disabled:opacity-40"
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
        </SectionCard>

        <SectionCard id="privacy" title="Privacy & data">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-surface-subtle p-4">
              <strong className="font-extrabold">What you can see</strong>
              <p className="mt-1 text-sm text-muted">
                Only learners enrolled in your own rosters, and only their work in those
                classes. Learner logins belong to their guardians.
              </p>
            </div>
            <div className="rounded-2xl bg-surface-subtle p-4">
              <strong className="font-extrabold">How long we keep it</strong>
              <p className="mt-1 text-sm text-muted">
                Class data stays while the roster exists. A guardian can delete their
                learner&apos;s data at any time.
              </p>
            </div>
          </div>

          {demo && (
            <div
              role="status"
              data-testid="settings-demo-notice"
              className="flex items-start gap-3 rounded-2xl bg-warning/15 px-4.5 py-3.5 text-warning"
            >
              <span className="text-sm">
                <strong className="font-extrabold">This is a demo account.</strong> It and its
                learners reset to their starting state on a schedule, so deletion requests are
                turned off here.
              </span>
            </div>
          )}

          <div className="flex flex-col gap-3 rounded-2xl border-2 border-warning/30 p-5">
            <div>
              <h3 className="font-extrabold">Request a learner&apos;s data be deleted</h3>
              <p className="mt-1 text-sm text-muted">
                Removes the learner&apos;s account and everything attached to it, in every
                class -- not just yours. To only take someone out of a class, remove them from
                the roster instead.
              </p>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <select
                value={deleteLearnerId}
                disabled={demo}
                onChange={(event) => setDeleteLearnerId(event.target.value)}
                className="min-h-11 min-w-[220px] rounded-xl border-2 border-primary/25 px-3 font-bold disabled:opacity-40"
              >
                <option value="">Choose a learner</option>
                {learners.map((learner) => (
                  <option key={learner.learnerId} value={learner.learnerId}>
                    {learner.displayName} · {learner.subjectId}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={demo || !deleteLearnerId}
                onClick={() => requestDeletion("learner", deleteLearnerId)}
                className="min-h-11 rounded-full bg-error px-5 font-extrabold text-white disabled:opacity-40"
              >
                Request deletion
              </button>
            </div>
            {learnerDeletion && (
              <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-warning/15 px-4 py-3 text-warning">
                <span className="rounded-full bg-surface px-3 py-0.5 text-[13px] font-extrabold">
                  {learnerDeletion.status === "pending" ? "Pending" : "Completed"}
                </span>
                <span className="text-[15px]">Status: {learnerDeletion.status}.</span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-4">
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm">
                <strong className="font-extrabold">Delete my instructor account</strong>
              </span>
              <button
                type="button"
                disabled={demo || !instructor.instructorId}
                onClick={() => requestDeletion("instructor", instructor.instructorId ?? "")}
                className="min-h-11 rounded-full border-2 border-error/40 px-4.5 font-extrabold text-error disabled:opacity-40"
              >
                Request account deletion
              </button>
            </div>
            {accountDeletion && (
              <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-warning/15 px-4 py-3 text-warning">
                <span className="rounded-full bg-surface px-3 py-0.5 text-[13px] font-extrabold">
                  {accountDeletion.status === "pending" ? "Pending" : "Completed"}
                </span>
                <span className="text-[15px]">Status: {accountDeletion.status}.</span>
              </div>
            )}
          </div>
          {deletionError && <p className="text-sm text-error">{deletionError}</p>}
        </SectionCard>
      </div>
    </div>
  );
}

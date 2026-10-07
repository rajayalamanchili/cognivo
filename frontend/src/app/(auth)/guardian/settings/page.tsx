"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  ApiError,
  changeGuardianPassword,
  getDeletionRequestStatus,
  getPracticeRemindersPreference,
  getWhoAmI,
  listMyLearners,
  setPracticeRemindersPreference,
  submitDeletionRequest,
  updateGuardianMe,
  type DeletionRequestStatusResponse,
  type DeletionTargetType,
  type GuardianMeUpdate,
  type MyLearner,
  type Theme,
} from "@/services/api";
import LoadingIndicator from "@/components/LoadingIndicator";

// spec 041 FR-009/FR-010/FR-011/FR-012: a genuinely new, real Settings
// page -- not a restyled mockup of nothing (spec.md's User Story 2).
// Built directly in the mockup's visual language since there is no
// pre-existing page to preserve behavior on, unlike Phase 3's restyles.

interface GuardianState {
  guardianId: string;
  name: string;
  email: string;
  readAloudDefault: boolean;
  largerText: boolean;
  reduceMotion: boolean;
  theme: Theme;
  quizFinishedEmailEnabled: boolean;
  weeklySummaryEnabled: boolean;
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
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="h-5 w-9 accent-primary disabled:opacity-40"
      />
    </label>
  );
}

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-7">
      <h2 className="font-heading text-2xl font-bold text-heading">{title}</h2>
      {children}
    </section>
  );
}

export default function GuardianSettingsPage() {
  const [guardian, setGuardian] = useState<GuardianState | null>(null);
  const [learners, setLearners] = useState<MyLearner[]>([]);
  const [practiceReminders, setPracticeReminders] = useState<Record<string, boolean>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [accountSaved, setAccountSaved] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordChanged, setPasswordChanged] = useState(false);

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
    Promise.all([getWhoAmI(), listMyLearners()])
      .then(async ([who, myLearners]) => {
        if (cancelled) return;
        if (who.account_type !== "guardian" || !who.guardian_id) {
          setLoadError("Please sign in as a guardian first.");
          return;
        }
        setGuardian({
          guardianId: who.guardian_id,
          name: who.name ?? "",
          email: who.identifier ?? "",
          readAloudDefault: who.read_aloud_default ?? false,
          largerText: who.larger_text ?? false,
          reduceMotion: who.reduce_motion ?? false,
          theme: who.theme ?? "system",
          quizFinishedEmailEnabled: who.quiz_finished_email_enabled ?? true,
          weeklySummaryEnabled: who.weekly_summary_enabled ?? false,
        });
        setName(who.name ?? "");
        setEmail(who.identifier ?? "");
        setLearners(myLearners.learners);

        const preferenceEntries = await Promise.all(
          myLearners.learners.map((learner) =>
            getPracticeRemindersPreference(learner.learner_id).then(
              (preference) => [learner.learner_id, preference.enabled] as const,
              () => [learner.learner_id, false] as const,
            ),
          ),
        );
        if (!cancelled) setPracticeReminders(Object.fromEntries(preferenceEntries));
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setLoadError(error instanceof Error ? error.message : String(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function savePreference(update: GuardianMeUpdate) {
    if (!guardian) return;
    const result = await updateGuardianMe(update);
    setGuardian((previous) =>
      previous && {
        ...previous,
        name: result.name ?? "",
        email: result.email,
        readAloudDefault: result.read_aloud_default,
        largerText: result.larger_text,
        reduceMotion: result.reduce_motion,
        theme: result.theme,
        quizFinishedEmailEnabled: result.quiz_finished_email_enabled,
        weeklySummaryEnabled: result.weekly_summary_enabled,
      },
    );
  }

  async function handleSaveAccount(event: FormEvent) {
    event.preventDefault();
    setAccountSaving(true);
    setAccountError(null);
    setAccountSaved(false);
    try {
      await savePreference({ name, email });
      setAccountSaved(true);
    } catch (error) {
      setAccountError(
        error instanceof ApiError && error.status === 409
          ? "That email is already in use."
          : error instanceof Error
            ? error.message
            : String(error),
      );
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
      await changeGuardianPassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setPasswordChanged(true);
    } catch (error) {
      setPasswordError(
        error instanceof ApiError && error.status === 401
          ? "Current password is incorrect."
          : error instanceof Error
            ? error.message
            : String(error),
      );
    } finally {
      setPasswordSaving(false);
    }
  }

  async function handlePracticeReminderToggle(learnerId: string, enabled: boolean) {
    const result = await setPracticeRemindersPreference(learnerId, enabled);
    setPracticeReminders((previous) => ({ ...previous, [learnerId]: result.enabled }));
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
      setDeletionError(error instanceof Error ? error.message : String(error));
    }
  }

  async function refreshDeletionStatus(
    targetType: DeletionTargetType,
    deletionRequestId: string,
  ) {
    const current = await getDeletionRequestStatus(deletionRequestId);
    if (targetType === "learner") setLearnerDeletion(current);
    else setAccountDeletion(current);
  }

  if (loadError) {
    return (
      <div className="p-8">
        <p className="text-error">{loadError}</p>
      </div>
    );
  }

  if (!guardian) {
    return <LoadingIndicator message="Loading your settings…" />;
  }

  return (
    <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-7 p-8">
      <h1 className="font-heading text-[40px] font-bold leading-tight text-heading">Settings</h1>

      <SectionCard title="Account">
        <form onSubmit={handleSaveAccount} className="grid grid-cols-2 gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-extrabold">
            Name
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="min-h-12 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-extrabold">
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="min-h-12 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
            />
          </label>
          <div className="col-span-2 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={accountSaving}
              className="min-h-11 rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
            >
              {accountSaving ? "Saving…" : "Save changes"}
            </button>
            {accountSaved && <span className="text-sm text-success">Saved.</span>}
            {accountError && <span className="text-sm text-error">{accountError}</span>}
          </div>
        </form>
        <form
          onSubmit={handleChangePassword}
          className="flex flex-wrap items-end gap-3 border-t border-border pt-4"
        >
          <label className="flex flex-col gap-1.5 text-sm font-extrabold">
            Current password
            <input
              type="password"
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              className="min-h-12 w-56 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
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
              className="min-h-12 w-56 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
            />
          </label>
          <button
            type="submit"
            disabled={passwordSaving}
            className="min-h-11 rounded-full border-2 border-primary/25 px-5 font-extrabold text-primary disabled:opacity-40"
          >
            {passwordSaving ? "Changing…" : "Change password"}
          </button>
          {passwordChanged && <span className="text-sm text-success">Password changed.</span>}
          {passwordError && <span className="text-sm text-error">{passwordError}</span>}
        </form>
      </SectionCard>

      <SectionCard title="Learners">
        {learners.length === 0 ? (
          <p className="text-sm text-muted">No learners yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {learners.map((learner) => (
              <li
                key={learner.learner_id}
                className="flex flex-col gap-3 border-t border-border py-3 first:border-t-0 sm:flex-row sm:items-center sm:justify-between"
              >
                <span>
                  <strong className="font-extrabold">{learner.display_name}</strong>
                  <span className="block text-sm text-muted">
                    {learner.enrollment
                      ? `Grade ${learner.enrollment.grade ?? "—"} · ${learner.enrollment.subject_id}`
                      : "Not in a class yet"}
                  </span>
                </span>
                <label className="flex items-center gap-3 text-sm">
                  Practice reminders for {learner.display_name}
                  <input
                    type="checkbox"
                    role="switch"
                    checked={practiceReminders[learner.learner_id] ?? false}
                    onChange={(event) =>
                      handlePracticeReminderToggle(learner.learner_id, event.target.checked)
                    }
                    className="h-5 w-9 accent-primary"
                  />
                </label>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard title="Display &amp; accessibility">
        <ToggleRow
          title="Read-aloud by default"
          checked={guardian.readAloudDefault}
          onChange={(next) => savePreference({ read_aloud_default: next })}
        />
        <ToggleRow
          title="Larger text"
          checked={guardian.largerText}
          onChange={(next) => savePreference({ larger_text: next })}
        />
        <ToggleRow
          title="Reduce motion"
          checked={guardian.reduceMotion}
          onChange={(next) => savePreference({ reduce_motion: next })}
        />
        <label className="flex items-center justify-between gap-5 border-t border-border py-3">
          <span>
            <strong className="font-extrabold">Theme</strong>
            <span className="block text-sm text-muted">Match this device, or pick one</span>
          </span>
          <select
            value={guardian.theme}
            onChange={(event) => savePreference({ theme: event.target.value as Theme })}
            className="min-h-11 rounded-xl border-2 border-primary/25 px-3 font-bold"
          >
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </label>
      </SectionCard>

      <SectionCard title="Notifications">
        <ToggleRow
          title="Quiz-finished email"
          checked={guardian.quizFinishedEmailEnabled}
          onChange={(next) => savePreference({ quiz_finished_email_enabled: next })}
        />
        <ToggleRow
          title="Weekly summary"
          checked={guardian.weeklySummaryEnabled}
          onChange={(next) => savePreference({ weekly_summary_enabled: next })}
        />
      </SectionCard>

      <SectionCard title="Privacy &amp; data">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-2xl bg-surface-subtle p-4">
            <strong className="font-extrabold">How long we keep it</strong>
            <p className="mt-1 text-sm text-muted">
              For as long as the account is active, then removed.
            </p>
          </div>
          <div className="rounded-2xl bg-surface-subtle p-4">
            <strong className="font-extrabold">Who can see it</strong>
            <p className="mt-1 text-sm text-muted">
              You, your learner, and the instructor of any class they&apos;ve joined.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <h3 className="font-extrabold">Delete a learner&apos;s data</h3>
          <p className="text-sm text-muted">
            Removes the learner&apos;s login, answers, mastery history, tutor chats and class
            enrollments. This can&apos;t be undone.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <select
              value={deleteLearnerId}
              onChange={(event) => setDeleteLearnerId(event.target.value)}
              className="min-h-11 min-w-[200px] rounded-xl border-2 border-primary/25 px-3 font-bold"
            >
              <option value="">Choose a learner</option>
              {learners.map((learner) => (
                <option key={learner.learner_id} value={learner.learner_id}>
                  {learner.display_name}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!deleteLearnerId}
              onClick={() => requestDeletion("learner", deleteLearnerId)}
              className="min-h-11 rounded-full bg-error px-5 font-extrabold text-white disabled:opacity-40"
            >
              Request deletion
            </button>
            {learnerDeletion && (
              <span className="text-sm text-muted">
                Status: {learnerDeletion.status}.{" "}
                {learnerDeletion.status === "pending" && (
                  <button
                    type="button"
                    onClick={() => refreshDeletionStatus("learner", learnerDeletion.deletion_request_id)}
                    className="underline"
                  >
                    Check status
                  </button>
                )}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
          <span className="text-sm">
            <strong className="font-extrabold">Delete my guardian account</strong> — also deletes
            every learner you manage.
          </span>
          <button
            type="button"
            onClick={() => requestDeletion("guardian", guardian.guardianId)}
            className="min-h-11 rounded-full border-2 border-error/40 px-4.5 font-extrabold text-error"
          >
            Delete account
          </button>
        </div>
        {accountDeletion && (
          <span className="text-sm text-muted">
            Status: {accountDeletion.status}.{" "}
            {accountDeletion.status === "pending" && (
              <button
                type="button"
                onClick={() => refreshDeletionStatus("guardian", accountDeletion.deletion_request_id)}
                className="underline"
              >
                Check status
              </button>
            )}
          </span>
        )}
        {deletionError && <p className="text-sm text-error">{deletionError}</p>}
      </SectionCard>
    </div>
  );
}

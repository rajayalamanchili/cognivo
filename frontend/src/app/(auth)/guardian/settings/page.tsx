"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import {
  ApiError,
  changeGuardianPassword,
  getDeletionRequestStatus,
  getWhoAmI,
  listMyLearners,
  submitDeletionRequest,
  updateGuardianMe,
  type DeletionRequestStatusResponse,
  type DeletionTargetType,
  type GuardianMeUpdate,
  type MyLearner,
  type Theme,
} from "@/services/api";
import LoadingIndicator from "@/components/LoadingIndicator";
import ToggleSwitch from "@/components/ToggleSwitch";
import { avatarClassName } from "@/lib/avatar-color";
import { notifySessionChanged } from "@/lib/visitor-state";

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
      <ToggleSwitch checked={checked} onChange={onChange} disabled={disabled} />
    </label>
  );
}

const SETTINGS_SECTIONS = [
  { id: "account", label: "Account" },
  { id: "learners", label: "Learners" },
  { id: "access", label: "Display & accessibility" },
  { id: "notify", label: "Notifications" },
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

export default function GuardianSettingsPage() {
  const [guardian, setGuardian] = useState<GuardianState | null>(null);
  const [learners, setLearners] = useState<MyLearner[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [accountSaved, setAccountSaved] = useState(false);

  const [pwOpen, setPwOpen] = useState(false);
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
  // Deletion requests are picked up by a scheduled job, not executed
  // synchronously (spec 020) -- re-checking status while it's still
  // pending is expected to come back unchanged. Without its own
  // "checking…" feedback, that looked indistinguishable from the
  // button doing nothing at all.
  const [checkingLearnerStatus, setCheckingLearnerStatus] = useState(false);
  const [checkingAccountStatus, setCheckingAccountStatus] = useState(false);
  const [learnerStatusCheckedAt, setLearnerStatusCheckedAt] = useState<Date | null>(null);
  const [accountStatusCheckedAt, setAccountStatusCheckedAt] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getWhoAmI(), listMyLearners()])
      .then(([who, myLearners]) => {
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
    // Display/accessibility prefs (theme/larger text/reduce motion) are
    // applied globally by AccountDisplayPreferences.tsx, which only
    // re-fetches on this same session-changed signal Nav/DemoBadge
    // already rely on -- without it, a toggle here would persist but
    // not visibly apply until the next full page load.
    notifySessionChanged();
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
    const setChecking = targetType === "learner" ? setCheckingLearnerStatus : setCheckingAccountStatus;
    setChecking(true);
    try {
      const current = await getDeletionRequestStatus(deletionRequestId);
      if (targetType === "learner") {
        setLearnerDeletion(current);
        setLearnerStatusCheckedAt(new Date());
      } else {
        setAccountDeletion(current);
        setAccountStatusCheckedAt(new Date());
      }
    } catch (error) {
      setDeletionError(error instanceof Error ? error.message : String(error));
    } finally {
      setChecking(false);
    }
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
              <span className="text-sm font-normal text-muted">You&apos;ll use this to sign in</span>
            </label>
            <div className="col-span-2 flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={accountSaving}
                className="min-h-11 rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
              >
                {accountSaving ? "Saving…" : "Save changes"}
              </button>
              <button
                type="button"
                onClick={() => setPwOpen((open) => !open)}
                aria-expanded={pwOpen}
                className="min-h-11 rounded-full border-2 border-primary/25 px-5 font-extrabold text-primary"
              >
                Change password
              </button>
              {accountSaved && <span className="text-sm text-success">Saved.</span>}
              {accountError && <span className="text-sm text-error">{accountError}</span>}
            </div>
          </form>
          {pwOpen && (
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
              <span className="col-span-full text-sm text-muted">
                You&apos;ll be signed out on your other devices.
              </span>
              {passwordChanged && (
                <span className="col-span-full text-sm text-success">Password changed.</span>
              )}
              {passwordError && (
                <span className="col-span-full text-sm text-error">{passwordError}</span>
              )}
            </form>
          )}
        </SectionCard>

        <SectionCard id="learners" title="Learners">
          <p className="-mt-1 text-sm text-muted">
            Learners use Cognivo through your account, so there are no learner passwords to
            manage.
          </p>
          {learners.length === 0 ? (
            <p className="text-sm text-muted">No learners yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {learners.map((learner) => (
                <li
                  key={learner.learner_id}
                  className="flex flex-wrap items-center gap-3.5 border-t border-border py-3.5 first:border-t-0"
                >
                  <span
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl font-extrabold ${avatarClassName(learner.learner_id)}`}
                  >
                    {learner.display_name.charAt(0).toUpperCase()}
                  </span>
                  <span className="flex-grow">
                    <strong className="font-extrabold">{learner.display_name}</strong>
                    <span className="block text-sm text-muted">
                      {learner.enrollment
                        ? `Grade ${learner.enrollment.grade ?? "—"} · ${learner.enrollment.subject_id}`
                        : "Not in a class yet"}
                    </span>
                  </span>
                  <Link href="/guardian/learners" className="text-[15px] font-extrabold text-primary">
                    Manage
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard id="access" title="Display &amp; accessibility">
          <ToggleRow
            title="Read-aloud button"
            subtitle="Offered on questions for younger grades. Never plays on its own."
            checked={guardian.readAloudDefault}
            onChange={(next) => savePreference({ read_aloud_default: next })}
          />
          <ToggleRow
            title="Larger text"
            subtitle="Bumps question and answer text up a size"
            checked={guardian.largerText}
            onChange={(next) => savePreference({ larger_text: next })}
          />
          <ToggleRow
            title="Reduce motion"
            subtitle="Turns off celebration animations"
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

        <SectionCard id="notify" title="Notifications">
          <ToggleRow
            title="Quiz finished"
            subtitle="Email me when a learner completes an assigned quiz"
            checked={guardian.quizFinishedEmailEnabled}
            onChange={(next) => savePreference({ quiz_finished_email_enabled: next })}
          />
          <ToggleRow
            title="Weekly summary"
            subtitle="One email each Sunday with progress and weak areas"
            checked={guardian.weeklySummaryEnabled}
            onChange={(next) => savePreference({ weekly_summary_enabled: next })}
          />
          <p className="mt-1 text-sm text-muted">
            Saved to your account, so these follow you to any device you sign in on.
          </p>
        </SectionCard>

        <SectionCard id="privacy" title="Privacy &amp; data">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-surface-subtle p-4">
              <strong className="font-extrabold">How long we keep it</strong>
              <p className="mt-1 text-sm text-muted">
                For as long as the account is active, then removed. See the full list of what we
                store and why.
              </p>
            </div>
            <div className="rounded-2xl bg-surface-subtle p-4">
              <strong className="font-extrabold">Who can see it</strong>
              <p className="mt-1 text-sm text-muted">
                You, and the instructor of any class your learner has joined, only for that
                class.
              </p>
            </div>
          </div>

          <details className="rounded-2xl bg-surface-subtle p-4">
            <summary className="flex min-h-11 cursor-pointer items-center font-extrabold text-primary">
              What Cognivo stores
            </summary>
            <ul className="flex flex-col gap-2.5 pt-2.5 text-sm text-muted">
              <li>
                <strong className="font-extrabold text-heading">Learner identity</strong> — name,
                which guardian manages them, and which classes they&apos;ve joined.
              </li>
              <li>
                <strong className="font-extrabold text-heading">Answers and mastery</strong> —
                every question answered, how it was graded, and the mastery estimate for each
                topic.
              </li>
              <li>
                <strong className="font-extrabold text-heading">AI Tutor conversations</strong> —
                the full back-and-forth of any tutoring chat.
              </li>
              <li>
                <strong className="font-extrabold text-heading">Practice and quiz sessions</strong>{" "}
                — when each one started and ended, and how it was scored.
              </li>
              <li>
                <strong className="font-extrabold text-heading">Account details</strong> — your
                name, email, and preferences.
              </li>
            </ul>
            <p className="pt-2.5 text-sm text-muted">
              Deleting a learner (or your account) permanently removes all of the above — see
              &quot;Delete a learner&apos;s data&quot; below.
            </p>
          </details>

          <div className="flex flex-col gap-4 rounded-2xl border-2 border-warning/30 p-5">
            <div className="flex flex-col gap-2">
              <h3 className="font-extrabold">Delete a learner&apos;s data</h3>
              <p className="text-sm text-muted">
                Removes the learner&apos;s answers, mastery history, tutor chats and class
                enrollments. This can&apos;t be undone, and their &quot;why was I shown
                this&quot; history goes with it.
              </p>
            </div>
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
            </div>
            {learnerDeletion && (
              <div className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-warning/15 px-4 py-3 text-warning">
                  <span className="rounded-full bg-surface px-3 py-0.5 text-[13px] font-extrabold">
                    {learnerDeletion.status === "pending" ? "Pending" : "Completed"}
                  </span>
                  <span className="text-[15px]">
                    Status: {learnerDeletion.status}.{" "}
                    {learnerDeletion.status === "pending" &&
                      "Deletions run on a schedule, not instantly."}
                  </span>
                  {learnerDeletion.status === "pending" && (
                    <button
                      type="button"
                      disabled={checkingLearnerStatus}
                      onClick={() =>
                        refreshDeletionStatus("learner", learnerDeletion.deletion_request_id)
                      }
                      className="text-[15px] font-extrabold underline disabled:opacity-60"
                    >
                      {checkingLearnerStatus ? "Checking…" : "Check status"}
                    </button>
                  )}
                </div>
                {learnerStatusCheckedAt && learnerDeletion.status === "pending" && (
                  <span className="text-sm text-muted">
                    Still pending as of {learnerStatusCheckedAt.toLocaleTimeString()}.
                  </span>
                )}
              </div>
            )}

            <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
              <span className="text-sm">
                <strong className="font-extrabold">Delete my guardian account</strong> also
                deletes every learner you manage.
              </span>
              <button
                type="button"
                onClick={() => requestDeletion("guardian", guardian.guardianId)}
                className="min-h-11 rounded-full border-2 border-error/40 px-4.5 font-extrabold text-error"
              >
                Request account deletion
              </button>
            </div>
            {accountDeletion && (
              <div className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-warning/15 px-4 py-3 text-warning">
                  <span className="rounded-full bg-surface px-3 py-0.5 text-[13px] font-extrabold">
                    {accountDeletion.status === "pending" ? "Pending" : "Completed"}
                  </span>
                  <span className="text-[15px]">
                    Status: {accountDeletion.status}.{" "}
                    {accountDeletion.status === "pending" &&
                      "Deletions run on a schedule, not instantly."}
                  </span>
                  {accountDeletion.status === "pending" && (
                    <button
                      type="button"
                      disabled={checkingAccountStatus}
                      onClick={() =>
                        refreshDeletionStatus("guardian", accountDeletion.deletion_request_id)
                      }
                      className="text-[15px] font-extrabold underline disabled:opacity-60"
                    >
                      {checkingAccountStatus ? "Checking…" : "Check status"}
                    </button>
                  )}
                </div>
                {accountStatusCheckedAt && accountDeletion.status === "pending" && (
                  <span className="text-sm text-muted">
                    Still pending as of {accountStatusCheckedAt.toLocaleTimeString()}.
                  </span>
                )}
              </div>
            )}
          </div>
          {deletionError && <p className="text-sm text-error">{deletionError}</p>}
        </SectionCard>
      </div>
    </div>
  );
}

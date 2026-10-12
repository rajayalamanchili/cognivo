"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  resetPasswordGuardian,
  resetPasswordInstructor,
  type AuthErrorBody,
  type GuardianAuthResponse,
  type InstructorAuthResponse,
} from "@/services/api";
import { exitDemoLearnerMode, notifySessionChanged } from "@/lib/visitor-state";

export type AccountType = "guardian" | "instructor";

const RESET: Record<
  AccountType,
  (token: string, newPassword: string) => Promise<GuardianAuthResponse | InstructorAuthResponse>
> = {
  guardian: resetPasswordGuardian,
  instructor: resetPasswordInstructor,
};

function successRedirect(accountType: AccountType): string {
  return accountType === "guardian" ? "/guardian/learners" : "/instructor/rosters";
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body && typeof error.body === "object") {
    const detail = (error.body as AuthErrorBody).detail;
    if (detail === "reset_token_invalid") {
      return "This reset link is no longer valid. Request a new one.";
    }
    if (detail === "reset_token_expired") {
      return "This reset link has expired. Request a new one.";
    }
  }
  return error instanceof Error ? error.message : String(error);
}

function ResetPasswordFormInner({ accountType }: { accountType: AccountType }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // Captured once at mount, not re-read from `searchParams` later --
  // the effect below strips `?token=...` from the visible URL right
  // after this.
  const [token] = useState(() => searchParams.get("token") ?? "");
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  useEffect(() => {
    // The reset token is a single-use credential that arrived in the
    // URL's query string -- strip it from the visible URL/history once
    // read, so it isn't left sitting there or leaked via a Referer
    // header if this page ever links out.
    if (searchParams.get("token")) {
      router.replace(pathname);
    }
    // Only ever needs to run once, right after the initial token read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorText(null);
    try {
      await RESET[accountType](token, newPassword);
      exitDemoLearnerMode();
      notifySessionChanged();
      router.push(successRedirect(accountType));
    } catch (error) {
      setErrorText(errorMessage(error));
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[460px] flex-col gap-[22px] rounded-card border border-border bg-surface p-9">
      <h1 className="font-heading text-[34px] font-bold leading-tight text-heading">
        Set a new password
      </h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5 text-[15px] font-extrabold">
          New password
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            className="min-h-[52px] rounded-2xl border-2 border-primary/25 px-4 text-[17px] font-normal"
          />
        </label>
        {errorText && (
          <p className="text-sm text-error" data-testid="auth-error">
            {errorText}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting || !token}
          className="min-h-[52px] rounded-full bg-primary text-[17px] font-extrabold text-primary-foreground disabled:opacity-40"
        >
          {submitting ? "Please wait…" : "Set new password"}
        </button>
      </form>
      <Link
        href={`/${accountType}/forgot-password`}
        className="text-center text-[15px] font-extrabold text-link"
      >
        Request a new link
      </Link>
    </div>
  );
}

export default function ResetPasswordForm({ accountType }: { accountType: AccountType }) {
  return (
    <Suspense fallback={<div className="p-8" />}>
      <ResetPasswordFormInner accountType={accountType} />
    </Suspense>
  );
}

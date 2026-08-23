"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  loginGuardian,
  loginInstructor,
  registerGuardian,
  registerInstructor,
  type AuthErrorBody,
} from "@/services/api";

export type AccountType = "guardian" | "instructor";
export type AuthMode = "register" | "sign-in";

export interface AuthFormProps {
  accountType: AccountType;
  mode: AuthMode;
}

const ACCOUNT_LABEL: Record<AccountType, string> = {
  guardian: "guardian",
  instructor: "instructor",
};

// Only a guardian has somewhere useful to land post-auth in this phase
// (add-a-learner) -- the instructor dashboard doesn't exist until
// Milestone 7's User Story 3, so an instructor just sees an inline
// confirmation instead of a redirect to a page that isn't built yet.
function successRedirect(accountType: AccountType): string | null {
  return accountType === "guardian" ? "/guardian/learners" : null;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body && typeof error.body === "object") {
    const detail = (error.body as AuthErrorBody).detail;
    if (detail === "email_taken") return "An account with this email already exists.";
    if (detail === "invalid_credentials") return "Incorrect email or password.";
  }
  return error instanceof Error ? error.message : String(error);
}

export default function AuthForm({ accountType, mode }: AuthFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [succeeded, setSucceeded] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorText(null);
    try {
      if (accountType === "guardian") {
        await (mode === "register" ? registerGuardian : loginGuardian)(email, password);
      } else {
        await (mode === "register" ? registerInstructor : loginInstructor)(email, password);
      }
      const redirectTo = successRedirect(accountType);
      if (redirectTo) {
        router.push(redirectTo);
        return;
      }
      setSucceeded(true);
    } catch (error) {
      setErrorText(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  const otherModeHref = `/${accountType}/${mode === "register" ? "sign-in" : "register"}`;
  const otherModeLabel = mode === "register" ? "Sign in instead" : "Create an account instead";

  if (succeeded) {
    return (
      <div className="mx-auto flex max-w-sm flex-col gap-4 p-8">
        <h1 className="text-2xl font-semibold">You&apos;re signed in</h1>
        <p className="text-sm">
          Signed in as {ACCOUNT_LABEL[accountType]} <strong>{email}</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">
        {mode === "register" ? "Create" : "Sign in to"} your {ACCOUNT_LABEL[accountType]} account
      </h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            type="password"
            required
            minLength={8}
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
          />
        </label>
        {errorText && (
          <p className="text-sm text-red-600" data-testid="auth-error">
            {errorText}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-foreground px-5 py-3 text-background disabled:opacity-40"
        >
          {submitting ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}
        </button>
      </form>
      <Link href={otherModeHref} className="text-sm text-blue-600 underline">
        {otherModeLabel}
      </Link>
    </div>
  );
}

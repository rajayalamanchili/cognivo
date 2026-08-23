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
import { exitDemoLearnerMode, notifySessionChanged } from "@/lib/visitor-state";

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

// Both account types now have somewhere real to land post-auth
// (Milestone 7's instructor rosters page exists) -- mirrors the demo
// instructor entry point's own redirect target.
function successRedirect(accountType: AccountType): string {
  return accountType === "guardian" ? "/guardian/learners" : "/instructor/rosters";
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
      exitDemoLearnerMode();
      notifySessionChanged();
      router.push(successRedirect(accountType));
    } catch (error) {
      setErrorText(errorMessage(error));
      setSubmitting(false);
    }
  }

  const otherModeHref = `/${accountType}/${mode === "register" ? "sign-in" : "register"}`;
  const otherModeLabel = mode === "register" ? "Sign in instead" : "Create an account instead";

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

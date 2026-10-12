"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { forgotPasswordGuardian, forgotPasswordInstructor } from "@/services/api";

export type AccountType = "guardian" | "instructor";

const SEND: Record<AccountType, (email: string) => Promise<void>> = {
  guardian: forgotPasswordGuardian,
  instructor: forgotPasswordInstructor,
};

export default function ForgotPasswordForm({ accountType }: { accountType: AccountType }) {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await SEND[accountType](email);
    } finally {
      // Same confirmation whether or not the email matched a real
      // account (SC-003: no account-enumeration signal) -- this isn't
      // conditioned on success/failure at all.
      setSubmitting(false);
      setSubmitted(true);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[460px] flex-col gap-[22px] rounded-card border border-border bg-surface p-9">
      <h1 className="font-heading text-[34px] font-bold leading-tight text-heading">
        Reset your password
      </h1>
      {submitted ? (
        <p className="text-[15px] text-body">
          If that email matches an account, a reset link is on its way. Check your inbox.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-[15px] font-extrabold">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="min-h-[52px] rounded-2xl border-2 border-primary/25 px-4 text-[17px] font-normal"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="min-h-[52px] rounded-full bg-primary text-[17px] font-extrabold text-primary-foreground disabled:opacity-40"
          >
            {submitting ? "Please wait…" : "Send reset link"}
          </button>
        </form>
      )}
      <Link
        href={`/${accountType}/sign-in`}
        className="text-center text-[15px] font-extrabold text-link"
      >
        Back to sign in
      </Link>
    </div>
  );
}

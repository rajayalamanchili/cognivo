"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, getDemoInstructor } from "@/services/api";
import { enterDemoLearnerMode, notifySessionChanged } from "@/lib/visitor-state";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function DemoEntryPage() {
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  async function handleTryAsInstructor() {
    setStarting(true);
    setErrorText(null);
    try {
      await getDemoInstructor();
      notifySessionChanged();
      router.push("/instructor/rosters");
    } catch (error) {
      setErrorText(
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : String(error),
      );
      setStarting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-[960px] flex-col gap-7 px-8 py-10">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="font-heading text-[44px] font-bold leading-tight text-heading">
          Try Cognivo
        </h1>
        <p className="max-w-[560px] text-lg text-muted">
          Jump straight in with a ready-made account. Everything inside is made-up data, so
          explore freely.
        </p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="flex flex-col gap-3.5 rounded-card border border-border bg-surface p-8">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-warning/15 font-heading text-2xl font-bold text-warning">
            S
          </span>
          <h2 className="font-heading text-[28px] font-bold text-heading">Demo learner</h2>
          <p className="text-muted">
            Meet Sam, partway through Algebra I and Biology. See practice, mastery, the AI Tutor,
            and why each question was picked.
          </p>
          <Link
            href="/practice"
            onClick={enterDemoLearnerMode}
            className="mt-auto flex min-h-[52px] items-center justify-center rounded-full bg-primary font-extrabold text-primary-foreground"
          >
            Try as a demo learner
          </Link>
        </div>
        <div className="flex flex-col gap-3.5 rounded-card border border-border bg-surface p-8">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-subtle font-heading text-2xl font-bold text-heading">
            R
          </span>
          <h2 className="font-heading text-[28px] font-bold text-heading">Demo instructor</h2>
          <p className="text-muted">
            Ms. Rivera&apos;s Period 3 class: a roster, assigned quizzes, the class dashboard, and
            the flagged-question queue.
          </p>
          <button
            type="button"
            onClick={handleTryAsInstructor}
            disabled={starting}
            className="mt-auto flex min-h-[52px] items-center justify-center rounded-full border-2 border-primary/25 bg-surface font-extrabold text-heading disabled:opacity-40"
          >
            {starting ? (
              <LoadingIndicator variant="professional" compact />
            ) : (
              "Try as a demo instructor"
            )}
          </button>
        </div>
      </div>

      <div className="flex items-start gap-3.5 rounded-2xl bg-warning/15 p-5 text-warning">
        <span>
          <strong className="font-extrabold">Demo accounts are always labelled</strong> with a
          yellow banner and reset to their starting state regularly. They&apos;re separate from
          real sign-up -- nothing you do here creates a real account.
        </span>
      </div>

      {errorText && <p className="text-sm text-error">{errorText}</p>}
    </div>
  );
}

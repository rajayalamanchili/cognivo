"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, getDemoInstructor } from "@/services/api";
import { enterDemoLearnerMode, notifySessionChanged } from "@/lib/visitor-state";

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
    <div className="mx-auto flex max-w-sm flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Try Cognivo</h1>
      <p className="text-sm">
        No sign-up needed -- explore either side of the classroom with seeded, synthetic data.
      </p>

      <div className="flex flex-col gap-3">
        <Link
          href="/practice"
          onClick={enterDemoLearnerMode}
          className="rounded bg-foreground px-5 py-3 text-center text-background"
        >
          Try as a demo learner
        </Link>
        <button
          type="button"
          onClick={handleTryAsInstructor}
          disabled={starting}
          className="rounded border border-black/20 px-5 py-3 disabled:opacity-40 dark:border-white/20"
        >
          {starting ? "Starting…" : "Try as a demo instructor"}
        </button>
      </div>

      {errorText && <p className="text-sm text-red-600">{errorText}</p>}
    </div>
  );
}

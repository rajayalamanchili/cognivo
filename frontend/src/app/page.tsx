"use client";

import Link from "next/link";
import { enterDemoLearnerMode } from "@/lib/visitor-state";

export default function Home() {
  return (
    <div className="mx-auto flex max-w-2xl flex-1 flex-col items-start justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold">Cognivo</h1>
      <p className="text-muted">
        A domain-agnostic learning platform that personalizes sequencing based on a real mastery
        model, and generates assessments dynamically.
      </p>
      <div className="flex gap-4">
        <Link
          href="/placement?subject=algebra-1"
          onClick={enterDemoLearnerMode}
          className="rounded-lg bg-primary px-5 py-3 text-primary-foreground"
        >
          Start Algebra I Placement
        </Link>
        <Link
          href="/placement?subject=biology"
          onClick={enterDemoLearnerMode}
          className="rounded-lg bg-primary px-5 py-3 text-primary-foreground"
        >
          Start Biology Placement
        </Link>
      </div>
    </div>
  );
}

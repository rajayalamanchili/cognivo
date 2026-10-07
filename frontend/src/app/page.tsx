"use client";

import Link from "next/link";
import CognivoMark from "@/components/CognivoMark";
import { enterDemoLearnerMode } from "@/lib/visitor-state";

const FEATURES = [
  {
    title: "Bayesian mastery",
    body: "Explainable per-topic tracking, not chat inference.",
  },
  {
    title: "Rubric-first questions",
    body: "Every item authored with its own answer key.",
  },
  {
    title: "Tutor on demand",
    body: "Grounded answers from the subject's own content.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <div className="mx-auto grid w-full max-w-[1180px] flex-1 items-center gap-12 px-8 py-16 md:grid-cols-2">
        <div className="flex flex-col gap-6">
          <div className="inline-flex w-fit items-center gap-2 rounded-full bg-primary-subtle px-3.5 py-1.5 text-sm font-bold text-heading">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Algebra I &amp; Biology live now
          </div>
          <h1 className="font-heading text-4xl font-bold leading-tight tracking-tight text-heading md:text-[60px]">
            A learning platform that adapts to <span className="text-primary">how you learn</span>.
          </h1>
          <p className="max-w-[44ch] text-lg leading-relaxed text-muted">
            Cognivo sequences what you see next from a real mastery model -- not a guess -- and
            generates every assessment on the spot, rubric first.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/placement?subject=algebra-1"
              onClick={enterDemoLearnerMode}
              className="min-h-[54px] rounded-full bg-primary px-6 py-3.5 font-extrabold text-primary-foreground"
            >
              Start Algebra I Placement
            </Link>
            <Link
              href="/placement?subject=biology"
              onClick={enterDemoLearnerMode}
              className="min-h-[54px] rounded-full border-2 border-primary/25 bg-surface px-6 py-3.5 font-extrabold text-heading"
            >
              Start Biology Placement
            </Link>
          </div>
        </div>

        <div className="relative hidden items-center justify-center md:flex">
          <div className="absolute h-[280px] w-[280px] rounded-full bg-primary-subtle" />
          <CognivoMark size={200} className="relative" />
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-[1180px] gap-5 px-8 pb-14 md:grid-cols-3">
        {FEATURES.map((feature) => (
          <div
            key={feature.title}
            className="flex flex-col gap-2.5 rounded-card border border-border bg-surface p-7"
          >
            <div className="font-heading text-xl font-bold text-heading">{feature.title}</div>
            <div className="text-muted">{feature.body}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

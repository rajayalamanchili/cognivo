"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import AuthForm, { type AccountType } from "@/components/AuthForm";

// spec 041 FR-004: a single page with a two-way Guardian/Instructor tab
// switcher (not the mockup's three-way Learner/Guardian/Instructor --
// Clarifications: no real learner login exists), reusing the existing
// `AuthForm` per tab with each role's own id-field label, redirect
// target, contextual note, and registration-availability link already
// built into it -- no new auth logic here, only the tab chrome.
// `(auth)/guardian/sign-in` and `(auth)/instructor/sign-in` become thin
// redirects into this page's correct tab (`?tab=...`) rather than
// duplicating the form.

const TABS: { value: AccountType; label: string }[] = [
  { value: "guardian", label: "Guardian" },
  { value: "instructor", label: "Instructor" },
];

function isAccountType(value: string | null): value is AccountType {
  return value === "guardian" || value === "instructor";
}

function tabClassName(active: boolean): string {
  return (
    "min-h-11 rounded-full px-4 font-extrabold " +
    (active ? "bg-surface text-heading shadow-sm" : "bg-transparent text-muted")
  );
}

function SignInTabs() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab");
  const [tab, setTab] = useState<AccountType>(isAccountType(initialTab) ? initialTab : "guardian");

  return (
    <div className="mx-auto flex max-w-[460px] flex-col gap-5 p-8">
      <div
        role="tablist"
        aria-label="I am a"
        className="grid grid-cols-2 gap-1 rounded-full bg-surface-subtle p-1"
      >
        {TABS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={tabClassName(tab === value)}
          >
            {label}
          </button>
        ))}
      </div>
      <AuthForm key={tab} accountType={tab} mode="sign-in" />
      <p className="text-center text-[15px] text-muted">
        Just looking?{" "}
        <Link href="/demo" className="font-extrabold text-link">
          Try the demo
        </Link>
      </p>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={<div className="p-8" />}>
      <SignInTabs />
    </Suspense>
  );
}

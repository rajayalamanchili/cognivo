"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getWhoAmI, logout, type SessionAccountType } from "@/services/api";
import { exitDemoLearnerMode, isDemoLearnerMode, onSessionChanged } from "@/lib/visitor-state";

// The nav's menu depends on who's actually visiting -- a server-verified
// session type (`getWhoAmI`) for guardian/instructor/demo_instructor, or
// a client-only "demo learner mode" flag for the seeded demo learner's
// entirely unauthenticated placement/practice/mastery/dashboard flow
// (visitor-state.ts). Logged out and not in demo mode: only "Try Demo"
// and "Sign In" show, per the product decision that drove this component
// -- everything else is gated on one of those two signals.

type Bucket = "anonymous" | "demo-learner" | "guardian" | "instructor";

interface NavLink {
  href: string;
  label: string;
}

const DEMO_LEARNER_LINKS: NavLink[] = [
  { href: "/placement?subject=algebra-1", label: "Placement" },
  { href: "/practice", label: "Practice" },
  { href: "/mastery", label: "Mastery" },
  { href: "/dashboard", label: "Dashboard" },
];

// SC-005 (spec 003/007): always reachable, no login/demo mode required
// -- a public evidence/trust page, not a role-gated menu item, so it
// stays outside the bucket logic below entirely.
const PERSONALIZATION_EVIDENCE_LINK: NavLink = {
  href: "/personalization-eval",
  label: "Personalization Evidence",
};

const GUARDIAN_LINKS: NavLink[] = [{ href: "/guardian/learners", label: "My Learners" }];

const INSTRUCTOR_LINKS: NavLink[] = [
  { href: "/instructor/rosters", label: "Rosters" },
  { href: "/instructor/dashboard", label: "Dashboard" },
  { href: "/instructor/review", label: "Review" },
];

function bucketFor(accountType: SessionAccountType | null, demoLearnerMode: boolean): Bucket {
  if (accountType === "guardian") return "guardian";
  if (accountType === "instructor" || accountType === "demo_instructor") return "instructor";
  if (demoLearnerMode) return "demo-learner";
  return "anonymous";
}

const ACCOUNT_TYPE_LABEL: Record<"guardian" | "instructor", string> = {
  guardian: "Guardian",
  instructor: "Instructor",
};

function useVisitorState() {
  const [accountType, setAccountType] = useState<SessionAccountType | null | "loading">(
    "loading",
  );
  const [identifier, setIdentifier] = useState<string | null>(null);
  const [demoLearnerMode, setDemoLearnerMode] = useState(() => isDemoLearnerMode());

  function refresh() {
    setDemoLearnerMode(isDemoLearnerMode());
    getWhoAmI()
      .then((result) => {
        setAccountType(result.account_type);
        setIdentifier(result.identifier);
      })
      .catch(() => {
        setAccountType(null);
        setIdentifier(null);
      });
  }

  return { accountType, identifier, demoLearnerMode, refresh, setAccountType, setIdentifier };
}

export default function Nav() {
  const router = useRouter();
  const { accountType, identifier, demoLearnerMode, refresh, setAccountType, setIdentifier } =
    useVisitorState();

  useEffect(() => {
    refresh();
    return onSessionChanged(refresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSignOut() {
    await logout();
    setAccountType(null);
    setIdentifier(null);
    router.push("/");
  }

  function handleExitDemo() {
    exitDemoLearnerMode();
    router.push("/");
  }

  // Treated as "anonymous" while `accountType` is still resolving --
  // avoids a flash of an empty nav, and the bucket updates the instant
  // the fetch settles (SC-005's link below renders regardless either way).
  const bucket = bucketFor(accountType === "loading" ? null : accountType, demoLearnerMode);

  const links: NavLink[] =
    bucket === "guardian"
      ? GUARDIAN_LINKS
      : bucket === "instructor"
        ? INSTRUCTOR_LINKS
        : bucket === "demo-learner"
          ? DEMO_LEARNER_LINKS
          : [];

  return (
    <nav className="flex flex-wrap items-center gap-4 border-b border-zinc-200 px-8 py-3 text-sm dark:border-zinc-800">
      {bucket === "anonymous" && (
        <Link href="/demo" className="text-zinc-600 dark:text-zinc-400">
          Try Demo
        </Link>
      )}
      <Link href={PERSONALIZATION_EVIDENCE_LINK.href} className="text-zinc-600 dark:text-zinc-400">
        {PERSONALIZATION_EVIDENCE_LINK.label}
      </Link>
      {links.map((link) => (
        <Link key={link.href} href={link.href} className="text-zinc-600 dark:text-zinc-400">
          {link.label}
        </Link>
      ))}
      {bucket === "demo-learner" && (
        <button
          type="button"
          onClick={handleExitDemo}
          className="text-zinc-600 underline dark:text-zinc-400"
        >
          Exit Demo
        </button>
      )}
      {(bucket === "guardian" || bucket === "instructor") && (
        <span className="ml-auto flex items-center gap-4">
          {(accountType === "guardian" || accountType === "instructor") && identifier && (
            <span className="text-zinc-500 dark:text-zinc-400" data-testid="nav-identity">
              {identifier} &middot; {ACCOUNT_TYPE_LABEL[accountType]}
            </span>
          )}
          <button
            type="button"
            onClick={handleSignOut}
            className="text-zinc-600 underline dark:text-zinc-400"
          >
            Sign Out
          </button>
        </span>
      )}
      {(bucket === "anonymous" || bucket === "demo-learner") && (
        <Link href="/sign-in" className="ml-auto text-zinc-600 dark:text-zinc-400">
          Sign In
        </Link>
      )}
    </nav>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import CognivoMark from "@/components/CognivoMark";
import {
  getDemoLearner,
  getWhoAmI,
  logout,
  type PendingDeletionWarning,
  type SessionAccountType,
} from "@/services/api";
import {
  exitDemoLearnerMode,
  isDemoLearnerMode,
  notifySessionChanged,
  onSessionChanged,
} from "@/lib/visitor-state";

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
  { href: "/tutor", label: "Tutor" },
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

// The logo is a role-aware home link, not a bucket-derived one --
// a demo_instructor is still a demo account (Constitution Principle
// VIII), so it goes to the marketing homepage like every other
// non-real-account visitor, while a real guardian/instructor lands on
// their own role's home page.
function logoHref(accountType: SessionAccountType | null | "loading"): string {
  if (accountType === "guardian") return "/guardian/learners";
  if (accountType === "instructor") return "/instructor/dashboard";
  return "/";
}

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
  const [accountType, setAccountType] = useState<SessionAccountType | null | "loading">("loading");
  const [identifier, setIdentifier] = useState<string | null>(null);
  // Starts `false` unconditionally -- matching SSR, which has no
  // `localStorage` to read (same reasoning as `accountType` starting
  // "loading" above) -- then `refresh()`'s effect below corrects it
  // right after mount. Reading the real value synchronously here
  // instead caused a hydration mismatch: the client's first render
  // (post-hydration) already saw the real flag while the server-
  // rendered HTML it's diffed against never could.
  const [demoLearnerMode, setDemoLearnerMode] = useState(false);
  const [pendingDeletionWarnings, setPendingDeletionWarnings] = useState<PendingDeletionWarning[]>(
    [],
  );

  function refresh() {
    setDemoLearnerMode(isDemoLearnerMode());
    getWhoAmI()
      .then((result) => {
        setAccountType(result.account_type);
        setIdentifier(result.identifier);
        setPendingDeletionWarnings(result.pending_deletion_warnings ?? []);
      })
      .catch(() => {
        setAccountType(null);
        setIdentifier(null);
        setPendingDeletionWarnings([]);
      });
  }

  return {
    accountType,
    identifier,
    demoLearnerMode,
    pendingDeletionWarnings,
    refresh,
    setAccountType,
    setIdentifier,
  };
}

// 027-learner-ui-redesign: pill-shaped nav-link treatment, scoped to the
// demo-learner bucket only (per spec.md's Edge Cases) -- guardian/instructor
// links keep their existing plain-text styling.
function demoLearnerLinkClassName(active: boolean): string {
  return `rounded-full px-4 py-2 font-bold ${active ? "bg-primary-subtle text-heading" : "text-muted"}`;
}

export default function Nav() {
  const router = useRouter();
  const pathname = usePathname();
  const {
    accountType,
    identifier,
    demoLearnerMode,
    pendingDeletionWarnings,
    refresh,
    setAccountType,
    setIdentifier,
  } = useVisitorState();

  useEffect(() => {
    refresh();
    return onSessionChanged(refresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 027-learner-ui-redesign, gap-closing pass: the mockup's header
  // shows an avatar bubble + "{name} (demo)" where this nav currently
  // has nothing -- only fetched for the demo-learner bucket, and only
  // for display (there's exactly one seeded demo learner, so this is
  // the same profile `getDemoLearner()` already resolves elsewhere).
  const [demoLearnerName, setDemoLearnerName] = useState<string | null>(null);
  useEffect(() => {
    if (!demoLearnerMode) {
      setDemoLearnerName(null);
      return;
    }
    let cancelled = false;
    getDemoLearner()
      .then((learner) => {
        if (!cancelled) setDemoLearnerName(learner.display_name);
      })
      .catch(() => {
        if (!cancelled) setDemoLearnerName(null);
      });
    return () => {
      cancelled = true;
    };
  }, [demoLearnerMode]);

  // User feedback: Personalization Evidence/Exit Demo/Sign In don't
  // need to sit inline in the nav row -- tucked behind a click on the
  // avatar/name instead (closer to the mockup, which shows no such
  // links at all), closing on an outside click.
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function handleOutsideClick(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [menuOpen]);

  async function handleSignOut() {
    await logout();
    setAccountType(null);
    setIdentifier(null);
    // Every other session-changing action (login/register, entering or
    // exiting demo learner mode) notifies other mounted components --
    // sign-out was the one gap, leaving DemoBadge's own independent
    // `accountType` state (a demo_instructor's OR condition, unrelated
    // to pathname) stuck showing the badge everywhere after sign-out.
    notifySessionChanged();
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

  // 027-learner-ui-redesign, gap-closing pass: the mockup's header is a
  // centered 1180px/68px-tall bar -- scoped to the demo-learner bucket
  // only (spec.md's Edge Cases: new layout/shape treatment stays
  // scoped to that bucket, same as `demoLearnerLinkClassName` below).
  // Other buckets keep their pre-existing unconstrained row untouched.
  const isDemoLearnerBucket = bucket === "demo-learner";

  return (
    <>
      <nav
        className={
          isDemoLearnerBucket
            ? "border-b border-border bg-surface px-6"
            : "flex flex-wrap items-center gap-4 border-b border-border bg-surface px-8 py-3 text-sm"
        }
      >
        <div
          className={
            isDemoLearnerBucket
              ? "mx-auto flex h-[68px] max-w-[1180px] items-center gap-8"
              : "contents"
          }
        >
          <Link
            href={logoHref(accountType)}
            data-testid="nav-logo"
            className="flex items-center gap-2 font-heading text-lg font-bold text-heading"
          >
            <CognivoMark size={28} />
            Cognivo
          </Link>
          {bucket === "anonymous" && (
            <Link href="/demo" className="text-muted">
              Try Demo
            </Link>
          )}
          {!isDemoLearnerBucket && (
            <Link href={PERSONALIZATION_EVIDENCE_LINK.href} className="text-muted">
              {PERSONALIZATION_EVIDENCE_LINK.label}
            </Link>
          )}
          <div className={isDemoLearnerBucket ? "flex flex-grow items-center gap-1" : "contents"}>
            {links.map((link) => {
              if (bucket !== "demo-learner") {
                return (
                  <Link key={link.href} href={link.href} className="text-muted">
                    {link.label}
                  </Link>
                );
              }
              const active = pathname === link.href.split("?")[0];
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={demoLearnerLinkClassName(active)}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
          {isDemoLearnerBucket && (
            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                aria-expanded={menuOpen}
                aria-haspopup="menu"
                className="flex items-center gap-3"
              >
                <span
                  aria-hidden="true"
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-subtle font-extrabold text-heading"
                >
                  {(demoLearnerName ?? "D").charAt(0).toUpperCase()}
                </span>
                <span className="font-bold text-heading">
                  {demoLearnerName ?? "Demo Learner"} (demo)
                </span>
              </button>
              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 top-full z-10 mt-2 flex w-56 flex-col gap-1 rounded-[16px] border border-border bg-surface p-2 text-sm shadow-lg"
                >
                  <Link
                    role="menuitem"
                    href={PERSONALIZATION_EVIDENCE_LINK.href}
                    onClick={() => setMenuOpen(false)}
                    className="rounded-[10px] px-3 py-2 text-muted"
                  >
                    {PERSONALIZATION_EVIDENCE_LINK.label}
                  </Link>
                  <button
                    role="menuitem"
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      handleExitDemo();
                    }}
                    className="rounded-[10px] px-3 py-2 text-left text-muted"
                  >
                    Exit Demo
                  </button>
                  <Link
                    role="menuitem"
                    href="/sign-in"
                    onClick={() => setMenuOpen(false)}
                    className="rounded-[10px] px-3 py-2 text-muted"
                  >
                    Sign In
                  </Link>
                </div>
              )}
            </div>
          )}
          {(bucket === "guardian" || bucket === "instructor") && (
            <span className="ml-auto flex items-center gap-4">
              {(accountType === "guardian" || accountType === "instructor") && identifier && (
                <span className="text-muted" data-testid="nav-identity">
                  {identifier} &middot; {ACCOUNT_TYPE_LABEL[accountType]}
                </span>
              )}
              <button type="button" onClick={handleSignOut} className="text-muted underline">
                Sign Out
              </button>
            </span>
          )}
          {bucket === "anonymous" && (
            <Link href="/sign-in" className="ml-auto text-muted">
              Sign In
            </Link>
          )}
        </div>
      </nav>
      {pendingDeletionWarnings.length > 0 && (
        <div
          data-testid="deletion-warning-banner"
          className="border-b border-warning/30 bg-warning/15 px-8 py-2 text-sm text-warning"
        >
          {pendingDeletionWarnings.map((warning) => (
            <p key={`${warning.target_type}-${warning.target_id}`}>
              {warning.target_type === "learner" ? "This learner's" : "Your instructor"} account
              will be deleted on {warning.scheduled_deletion_date} due to inactivity, unless it
              becomes active again first.
            </p>
          ))}
        </div>
      )}
    </>
  );
}

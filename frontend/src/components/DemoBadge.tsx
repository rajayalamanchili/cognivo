"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getWhoAmI, type SessionAccountType } from "@/services/api";
import { onSessionChanged } from "@/lib/visitor-state";

// Persistent, unmissable demo-account marker (Constitution Principle
// VIII, tech-stack.md's Demo account strategy) -- shown only while the
// visitor is actually in demo territory: a demo_instructor session, or
// one of the seeded demo learner's own pages, structurally tied to the
// single global DemoLearnerProfile regardless of how the page was
// reached (so a direct deep link still shows it, unlike the nav's own
// click-through-tracked "demo learner mode" flag). Not shown for a
// real guardian/instructor session, and not on the bare landing page
// before a demo/login choice has been made.

const DEMO_LEARNER_PATHNAMES = new Set([
  "/demo",
  "/placement",
  "/practice",
  "/mastery",
  "/dashboard",
  "/quiz",
]);

export default function DemoBadge() {
  const pathname = usePathname();
  const [accountType, setAccountType] = useState<SessionAccountType | null>(null);

  useEffect(() => {
    let cancelled = false;
    function refresh() {
      getWhoAmI()
        .then((result) => {
          if (!cancelled) setAccountType(result.account_type);
        })
        .catch(() => {
          if (!cancelled) setAccountType(null);
        });
    }
    refresh();
    const unsubscribe = onSessionChanged(refresh);
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  const visible = accountType === "demo_instructor" || DEMO_LEARNER_PATHNAMES.has(pathname);
  if (!visible) return null;

  return (
    <div
      role="status"
      data-testid="demo-badge"
      className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-demo px-4 py-1.5 text-sm font-semibold text-demo-foreground"
    >
      DEMO ACCOUNT -- synthetic data, not a real learner
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import {
  getPendingNavigation,
  onPendingNavigationChange,
  resolvePendingNavigation,
} from "@/lib/leave-guard";

// spec 044 FR-028-FR-030 (US6): mounted once near the app root
// (`app/layout.tsx`) -- every guarded navigation site shares this one
// dialog via `leave-guard.ts`'s pending-request state instead of each
// rendering its own.
export default function LeaveGuardDialog() {
  const [pending, setPending] = useState(getPendingNavigation());

  useEffect(() => onPendingNavigationChange(() => setPending(getPendingNavigation())), []);

  if (!pending) return null;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      data-testid="leave-guard-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="flex max-w-sm flex-col gap-4 rounded-card border border-border bg-surface p-6">
        <p className="text-[15px] font-bold text-heading">{pending.message}</p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => resolvePendingNavigation(false)}
            className="min-h-11 rounded-full border-2 border-border px-4.5 font-extrabold text-heading"
          >
            Stay here
          </button>
          <button
            type="button"
            onClick={() => resolvePendingNavigation(true)}
            className="min-h-11 rounded-full bg-primary px-4.5 font-extrabold text-primary-foreground"
          >
            Leave
          </button>
        </div>
      </div>
    </div>
  );
}

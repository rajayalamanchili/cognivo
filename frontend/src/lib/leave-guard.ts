// spec 044 FR-028-FR-033 (US6): warns before an in-app navigation away
// from Practice/Placement while a question is unsubmitted. In-memory
// only (not `localStorage`, unlike `visitor-state.ts`) -- a guard is
// only ever meaningful within the current page's lifetime, never worth
// surviving a reload (research.md §5).
//
// `setGuard`/`clearGuard` are called by the guarded page itself
// (practice-flow.tsx/placement-flow.tsx) as its unsubmitted state
// changes. Every navigation site (Nav.tsx's links/exit actions,
// Practice's own "End session" link) calls `confirmNavigation` instead
// of navigating directly -- it runs `proceed` immediately when no guard
// is active, or hands off to `LeaveGuardDialog` (mounted once near the
// app root, the only component that renders a confirmation) via the
// shared pending-request below when one is.

// FR-029's exact required framing -- shared so Practice/Placement don't
// each word it slightly differently.
export const LEAVE_GUARD_MESSAGE =
  "Leaving now starts over with a new set of questions, not the ones on screen.";

let guardMessage: string | null = null;
const guardListeners = new Set<() => void>();

export function setGuard(message: string): void {
  guardMessage = message;
  guardListeners.forEach((callback) => callback());
}

export function clearGuard(): void {
  if (guardMessage === null) return;
  guardMessage = null;
  guardListeners.forEach((callback) => callback());
}

export function isGuardActive(): boolean {
  return guardMessage !== null;
}

export function onGuardChange(callback: () => void): () => void {
  guardListeners.add(callback);
  return () => guardListeners.delete(callback);
}

export interface PendingNavigation {
  message: string;
  proceed: () => void;
}

let pending: PendingNavigation | null = null;
const pendingListeners = new Set<() => void>();

/** Called by every guarded navigation site instead of navigating
 * directly -- transparent (runs `proceed` immediately) when no guard is
 * active. */
export function confirmNavigation(proceed: () => void): void {
  if (guardMessage === null) {
    proceed();
    return;
  }
  pending = { message: guardMessage, proceed };
  pendingListeners.forEach((callback) => callback());
}

export function getPendingNavigation(): PendingNavigation | null {
  return pending;
}

export function resolvePendingNavigation(confirmed: boolean): void {
  const request = pending;
  pending = null;
  pendingListeners.forEach((callback) => callback());
  if (confirmed && request) {
    clearGuard();
    request.proceed();
  }
}

export function onPendingNavigationChange(callback: () => void): () => void {
  pendingListeners.add(callback);
  return () => pendingListeners.delete(callback);
}

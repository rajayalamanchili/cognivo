// Client-only signals the nav (`components/Nav.tsx`) uses to pick
// which menu bucket to render, alongside `getWhoAmI()`'s server-verified
// session type:
//
// - "demo learner mode" -- there is no real session for the seeded
//   demo learner (placement/practice/mastery/dashboard are all
//   unauthenticated, tied to the single global demo learner). A visitor
//   entering that flow via `/demo`'s "Try as a demo learner" link is
//   tracked with a plain localStorage flag, the only signal available
//   for something that has no session cookie to check.
// - a same-tab "session changed" event -- the nav is one persistent
//   component instance in the root layout that does not remount on
//   client-side navigation, so anything that changes the visitor's
//   identity (login, register, logout, entering/exiting demo learner
//   mode) must explicitly notify it to refetch rather than relying on
//   a route change.

const DEMO_LEARNER_MODE_KEY = "cognivo:demo-learner-mode";
const SESSION_CHANGED_EVENT = "cognivo:session-changed";
// spec 041 FR-016/FR-022 (research.md §1): same kind of signal as
// demo-learner-mode above -- which real learner a guardian is
// currently acting for, with no session cookie of its own (the
// guardian's own cookie still authenticates every request).
const REAL_LEARNER_SESSION_KEY = "cognivo:real-learner-session";

export function isDemoLearnerMode(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(DEMO_LEARNER_MODE_KEY) === "true";
}

export function notifySessionChanged(): void {
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
}

export function enterDemoLearnerMode(): void {
  window.localStorage.setItem(DEMO_LEARNER_MODE_KEY, "true");
  notifySessionChanged();
}

export function exitDemoLearnerMode(): void {
  window.localStorage.removeItem(DEMO_LEARNER_MODE_KEY);
  notifySessionChanged();
}

export function onSessionChanged(handler: () => void): () => void {
  window.addEventListener(SESSION_CHANGED_EVENT, handler);
  return () => window.removeEventListener(SESSION_CHANGED_EVENT, handler);
}

export interface RealLearnerSession {
  learnerId: string;
  displayName: string;
}

export function getRealLearnerSession(): RealLearnerSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(REAL_LEARNER_SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as RealLearnerSession;
  } catch {
    return null;
  }
}

export function enterRealLearnerSession(learnerId: string, displayName: string): void {
  window.localStorage.setItem(
    REAL_LEARNER_SESSION_KEY,
    JSON.stringify({ learnerId, displayName }),
  );
  notifySessionChanged();
}

export function exitRealLearnerSession(): void {
  window.localStorage.removeItem(REAL_LEARNER_SESSION_KEY);
  notifySessionChanged();
}

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

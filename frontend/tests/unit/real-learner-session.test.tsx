// Unit test: visitor-state.ts's real-learner-session helpers (T027,
// spec 041 FR-016/FR-022) -- the localStorage round-trip and the
// same-tab "session changed" notification, mirroring the existing
// demo-learner-mode helpers' contract.

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  enterRealLearnerSession,
  exitRealLearnerSession,
  getRealLearnerSession,
  onSessionChanged,
} from "@/lib/visitor-state";

const REAL_LEARNER_SESSION_KEY = "cognivo:real-learner-session";

describe("real-learner session", () => {
  beforeEach(() => {
    window.localStorage.removeItem(REAL_LEARNER_SESSION_KEY);
  });

  it("returns null when no session is active", () => {
    expect(getRealLearnerSession()).toBeNull();
  });

  it("entering a session round-trips through localStorage and notifies listeners", () => {
    const listener = vi.fn();
    const unsubscribe = onSessionChanged(listener);

    enterRealLearnerSession("learner-1", "Eli");

    expect(getRealLearnerSession()).toEqual({ learnerId: "learner-1", displayName: "Eli" });
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("exiting a session clears it and notifies listeners", () => {
    enterRealLearnerSession("learner-1", "Eli");

    const listener = vi.fn();
    const unsubscribe = onSessionChanged(listener);
    exitRealLearnerSession();

    expect(getRealLearnerSession()).toBeNull();
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("tolerates corrupt stored JSON by treating it as no session", () => {
    window.localStorage.setItem(REAL_LEARNER_SESSION_KEY, "{not json");
    expect(getRealLearnerSession()).toBeNull();
  });
});

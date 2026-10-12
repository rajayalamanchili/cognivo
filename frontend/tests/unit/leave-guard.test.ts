// Unit test: leave-guard.ts's own set/clear/subscribe + pending-
// navigation confirmation flow (spec 044 FR-028-FR-033, US6).

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearGuard,
  confirmNavigation,
  getPendingNavigation,
  isGuardActive,
  onGuardChange,
  onPendingNavigationChange,
  resolvePendingNavigation,
  setGuard,
} from "@/lib/leave-guard";

describe("leave-guard", () => {
  beforeEach(() => {
    clearGuard();
    resolvePendingNavigation(false);
  });

  it("isGuardActive reflects setGuard/clearGuard", () => {
    expect(isGuardActive()).toBe(false);
    setGuard("careful");
    expect(isGuardActive()).toBe(true);
    clearGuard();
    expect(isGuardActive()).toBe(false);
  });

  it("notifies guard-change subscribers on set and clear", () => {
    const callback = vi.fn();
    const unsubscribe = onGuardChange(callback);

    setGuard("careful");
    expect(callback).toHaveBeenCalledTimes(1);
    clearGuard();
    expect(callback).toHaveBeenCalledTimes(2);

    unsubscribe();
  });

  it("clearGuard is a no-op (no notification) when already inactive", () => {
    const callback = vi.fn();
    const unsubscribe = onGuardChange(callback);

    clearGuard();
    expect(callback).not.toHaveBeenCalled();

    unsubscribe();
  });

  it("confirmNavigation runs proceed immediately when no guard is active", () => {
    const proceed = vi.fn();
    confirmNavigation(proceed);
    expect(proceed).toHaveBeenCalledTimes(1);
    expect(getPendingNavigation()).toBeNull();
  });

  it("confirmNavigation defers to a pending request when a guard is active, resolved by resolvePendingNavigation(true)", () => {
    const proceed = vi.fn();
    const callback = vi.fn();
    const unsubscribe = onPendingNavigationChange(callback);

    setGuard("careful");
    confirmNavigation(proceed);
    expect(proceed).not.toHaveBeenCalled();
    expect(getPendingNavigation()).toEqual({ message: "careful", proceed });
    expect(callback).toHaveBeenCalledTimes(1);

    resolvePendingNavigation(true);
    expect(proceed).toHaveBeenCalledTimes(1);
    expect(getPendingNavigation()).toBeNull();
    expect(isGuardActive()).toBe(false);

    unsubscribe();
  });

  it("resolvePendingNavigation(false) cancels without running proceed, guard stays active", () => {
    const proceed = vi.fn();
    setGuard("careful");
    confirmNavigation(proceed);

    resolvePendingNavigation(false);
    expect(proceed).not.toHaveBeenCalled();
    expect(getPendingNavigation()).toBeNull();
    expect(isGuardActive()).toBe(true);
  });
});

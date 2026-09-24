"use client";

// A live countdown for a timed practice/quiz session (spec 022
// FR-002), built from a server-provided `expiresAt` timestamp -- never
// a client-guessed duration (research.md §1). This is a *display*
// only: the server is the sole authority on when a session actually
// ends (the lazy, per-request expiry check other endpoints already
// perform), so a little clock drift between this countdown reaching
// zero and the server's own cutoff is a cosmetic detail, not a
// correctness issue.

import { useEffect, useRef, useState } from "react";

export interface SessionCountdownProps {
  expiresAt: string;
  // Called once, the first time the countdown reaches zero -- callers
  // typically use this to trigger their next request, which the
  // server will then reject/auto-submit for real.
  onExpire?: () => void;
}

function remainingSeconds(expiresAt: string): number {
  return Math.max(0, Math.round((new Date(expiresAt).getTime() - Date.now()) / 1000));
}

function formatRemaining(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default function SessionCountdown({ expiresAt, onExpire }: SessionCountdownProps) {
  const [remaining, setRemaining] = useState(() => remainingSeconds(expiresAt));

  // A ref, not a dependency: `onExpire` is typically a fresh closure on
  // every parent render (both callers pass a plain function), and this
  // effect must not tear down/recreate its interval -- with a fresh
  // `expired` flag -- just because the parent re-rendered while the
  // countdown sits at/past zero, which would re-fire onExpire and
  // double-submit the same expired-session request.
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    let expired = false;
    const intervalId = setInterval(() => {
      const next = remainingSeconds(expiresAt);
      setRemaining(next);
      if (next <= 0 && !expired) {
        expired = true;
        clearInterval(intervalId);
        onExpireRef.current?.();
      }
    }, 1000);
    return () => clearInterval(intervalId);
  }, [expiresAt]);

  const low = remaining <= 60;

  return (
    <p
      data-testid="session-countdown"
      aria-live="polite"
      className={low ? "font-heading text-error" : "font-heading text-primary"}
    >
      Time remaining: {formatRemaining(remaining)}
    </p>
  );
}

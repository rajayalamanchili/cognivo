"use client";

import { useEffect, useState } from "react";
import {
  getCareerConnectionsPreference,
  setCareerConnectionsPreference,
} from "@/services/api";

// Spec 039 FR-004. Reused unmodified by the demo-learner settings page
// and the guardian's per-learner "My Learners" control -- both gate
// through the same backend endpoint/auth rule (research.md Decision 4).

export interface CareerConnectionsToggleProps {
  learnerId: string;
  // Optional -- only the guardian My-learners card (spec 041) has a
  // display name on hand to personalize the subtext; the demo-learner
  // settings page's own usage omits it.
  displayName?: string;
}

export default function CareerConnectionsToggle({
  learnerId,
  displayName,
}: CareerConnectionsToggleProps) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCareerConnectionsPreference(learnerId)
      .then((result) => {
        if (!cancelled) setEnabled(result.enabled);
      })
      .catch(() => {
        // Secondary control -- a failed fetch just leaves the toggle
        // unrendered rather than surfacing its own error UI.
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId]);

  async function handleChange(next: boolean) {
    setSaving(true);
    try {
      // Reflects the server's actual response, not an optimistic local
      // flip -- what's persisted is what's shown, even if it differs.
      const result = await setCareerConnectionsPreference(learnerId, next);
      setEnabled(result.enabled);
    } finally {
      setSaving(false);
    }
  }

  if (enabled === null) return null;

  return (
    <label
      className="flex cursor-pointer items-center justify-between gap-4"
      data-testid="career-connections-toggle"
    >
      <span className="flex flex-col">
        <span className="font-extrabold text-heading">Show STEM-career connections</span>
        <span className="text-sm text-muted">
          Real jobs that use each topic{displayName ? `, shown to ${displayName} too` : ""}
        </span>
      </span>
      <input
        type="checkbox"
        role="switch"
        checked={enabled}
        disabled={saving}
        onChange={(event) => handleChange(event.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden="true"
        className="flex h-[30px] w-[52px] shrink-0 items-center rounded-full bg-border p-[3px] transition-colors peer-checked:bg-primary peer-checked:justify-end"
      >
        <span className="h-6 w-6 rounded-full bg-white shadow" />
      </span>
    </label>
  );
}

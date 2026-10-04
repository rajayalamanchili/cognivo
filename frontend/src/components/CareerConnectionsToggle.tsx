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
}

export default function CareerConnectionsToggle({ learnerId }: CareerConnectionsToggleProps) {
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
    <label className="flex items-center gap-2 text-sm" data-testid="career-connections-toggle">
      <input
        type="checkbox"
        checked={enabled}
        disabled={saving}
        onChange={(event) => handleChange(event.target.checked)}
      />
      Show STEM-career connections
    </label>
  );
}

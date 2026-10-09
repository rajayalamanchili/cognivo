"use client";

import { useEffect, useState } from "react";
import { getWhoAmI } from "@/services/api";
import { onSessionChanged } from "@/lib/visitor-state";

// spec 041 FR-011, extended by spec 043: applies a guardian's or real
// instructor's Display & accessibility preferences (theme/larger
// text/reduce motion) to the document root via data attributes
// (globals.css), so Settings' toggles actually do something instead
// of only persisting to the backend. These columns exist on
// RealGuardianAccount and RealInstructorAccount only, so this is a
// no-op for every other session type -- same `onSessionChanged`
// refresh pattern Nav/DemoBadge already use.
export default function AccountDisplayPreferences() {
  const [prefs, setPrefs] = useState<{
    theme: string;
    largerText: boolean;
    reduceMotion: boolean;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    function refresh() {
      getWhoAmI()
        .then((result) => {
          if (cancelled) return;
          setPrefs(
            result.account_type === "guardian" || result.account_type === "instructor"
              ? {
                  theme: result.theme ?? "system",
                  largerText: result.larger_text ?? false,
                  reduceMotion: result.reduce_motion ?? false,
                }
              : null,
          );
        })
        .catch(() => {
          if (!cancelled) setPrefs(null);
        });
    }
    refresh();
    const unsubscribe = onSessionChanged(refresh);
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (prefs && prefs.theme !== "system") {
      root.dataset.theme = prefs.theme;
    } else {
      delete root.dataset.theme;
    }
    root.dataset.largerText = prefs?.largerText ? "true" : "false";
    root.dataset.reduceMotion = prefs?.reduceMotion ? "true" : "false";
  }, [prefs]);

  return null;
}

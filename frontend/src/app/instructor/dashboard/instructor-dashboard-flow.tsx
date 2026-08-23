"use client";

import { useEffect, useState } from "react";
import {
  getRosterDashboard,
  listRosters,
  type DashboardResponse,
  type RosterSummary,
} from "@/services/api";
import WeakAreaSection from "@/components/WeakAreaSection";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function InstructorDashboardFlow() {
  const [rosters, setRosters] = useState<RosterSummary[]>([]);
  const [selectedRosterId, setSelectedRosterId] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listRosters()
      .then((response) => {
        if (cancelled) return;
        setRosters(response.rosters);
        if (response.rosters.length > 0) {
          setSelectedRosterId(response.rosters[0].roster_id);
        }
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setErrorMessage(errorText(error));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedRosterId) return;
    let cancelled = false;
    getRosterDashboard(selectedRosterId)
      .then((response) => {
        if (cancelled) return;
        setDashboard(response);
        setDashboardError(null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setDashboardError(errorText(error));
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRosterId]);

  // Derived, not a separate state flag flipped synchronously in the
  // effect above: still fetching this roster's data whenever what's
  // loaded doesn't match what's selected (also true on first load,
  // when `dashboard` is still null).
  const dashboardLoading =
    selectedRosterId !== null && dashboard?.roster_id !== selectedRosterId && !dashboardError;

  if (loading) {
    return <p className="p-8">Loading dashboard&hellip;</p>;
  }

  if (rosters.length === 0) {
    return (
      <div className="p-8">
        <p className="text-sm">You have no rosters yet.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Class dashboard</h1>

      <label className="flex flex-col gap-1 text-sm">
        Roster
        <select
          value={selectedRosterId ?? ""}
          onChange={(event) => setSelectedRosterId(event.target.value)}
          className="rounded border border-black/20 px-3 py-2 dark:border-white/20"
        >
          {rosters.map((roster) => (
            <option key={roster.roster_id} value={roster.roster_id}>
              {roster.subject_id} ({roster.enrollment_mode})
            </option>
          ))}
        </select>
      </label>

      {errorMessage && <p className="text-sm text-red-600">Something went wrong: {errorMessage}</p>}
      {dashboardError && (
        <p className="text-sm text-red-600">Couldn&rsquo;t load this roster: {dashboardError}</p>
      )}

      {dashboardLoading && <p className="text-sm">Loading roster data&hellip;</p>}

      {!dashboardLoading && dashboard && dashboard.learners.length === 0 && (
        <p className="text-sm">No learners enrolled in this roster yet.</p>
      )}

      {!dashboardLoading && dashboard && dashboard.learners.length > 0 && (
        <div className="flex flex-col gap-6" data-testid="dashboard-learners">
          {dashboard.learners.map((entry) => (
            <div
              key={entry.learner_id}
              className="flex flex-col gap-3 rounded border border-black/20 p-4 dark:border-white/20"
            >
              <h2 className="font-medium">{entry.display_name}</h2>
              <WeakAreaSection recommendations={entry.recommendations} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

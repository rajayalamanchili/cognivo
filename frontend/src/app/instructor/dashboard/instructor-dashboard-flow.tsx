"use client";

import { useEffect, useState } from "react";
import {
  getRosterDashboard,
  listRosters,
  type DashboardResponse,
  type RosterSummary,
} from "@/services/api";
import WeakAreaSection from "@/components/WeakAreaSection";
import StandardsCoverage from "@/components/StandardsCoverage";
import LoadingIndicator from "@/components/LoadingIndicator";
import { avatarClassName } from "@/lib/avatar-color";

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
    return <LoadingIndicator message="Loading dashboard…" variant="professional" />;
  }

  if (rosters.length === 0) {
    return (
      <div className="p-8">
        <p className="text-sm">You have no rosters yet.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[1180px] flex-col gap-6 p-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="font-heading text-[40px] font-bold leading-tight text-heading">
            Class dashboard
          </h1>
          <p className="mt-1 text-[17px] text-muted">
            Where each learner needs help, from their own weak-area reports.
          </p>
        </div>
        <label className="flex flex-col gap-1 text-sm font-extrabold">
          Roster
          <select
            value={selectedRosterId ?? ""}
            onChange={(event) => setSelectedRosterId(event.target.value)}
            className="min-h-12 min-w-[260px] rounded-2xl border-2 border-primary/25 px-3.5 text-base font-bold"
          >
            {rosters.map((roster) => (
              <option key={roster.roster_id} value={roster.roster_id}>
                {roster.subject_id} ({roster.enrollment_mode})
              </option>
            ))}
          </select>
        </label>
      </div>

      {errorMessage && <p className="text-sm text-error">Something went wrong: {errorMessage}</p>}
      {dashboardError && (
        <p className="text-sm text-error">Couldn&rsquo;t load this roster: {dashboardError}</p>
      )}

      {dashboardLoading && (
        <LoadingIndicator message="Loading roster data…" variant="professional" compact />
      )}

      {!dashboardLoading && dashboard && (
        <div className="rounded-card border border-border bg-surface p-5">
          <span className="font-bold text-muted">Enrolled learners</span>
          <div className="font-heading text-[34px] font-bold leading-tight">
            {dashboard.learners.length}
          </div>
        </div>
      )}

      {!dashboardLoading && dashboard && dashboard.learners.length === 0 && (
        <p className="text-sm text-muted">No learners enrolled in this roster yet.</p>
      )}

      {!dashboardLoading && dashboard && (dashboard.standards_summary?.length ?? 0) > 0 && (
        <div
          className="flex flex-col gap-1.5 rounded-card border border-border bg-surface p-5"
          data-testid="roster-standards-summary"
        >
          <h2 className="font-heading text-xl font-bold text-heading">
            Class standards coverage
          </h2>
          {dashboard.standards_summary!.map((summary) => (
            <div
              key={`${summary.framework}:${summary.code}`}
              className="flex items-center justify-between gap-3 border-t border-border px-1 py-2 text-sm first:border-t-0"
            >
              <span>
                <span className="font-extrabold">{summary.code}</span> &mdash; {summary.title}
              </span>
              <span className="shrink-0 font-bold text-muted">
                {summary.met_count}/{summary.total_count} learners
              </span>
            </div>
          ))}
        </div>
      )}

      {!dashboardLoading && dashboard && dashboard.learners.length > 0 && (
        <div
          className="flex flex-col gap-4 rounded-card border border-border bg-surface p-3"
          data-testid="dashboard-learners"
        >
          <h2 className="font-heading px-3 pt-2 text-2xl font-bold text-heading">Learners</h2>
          {dashboard.learners.map((entry) => (
            <div
              key={entry.learner_id}
              className="flex flex-col gap-3 rounded-2xl border border-border p-5"
            >
              <div className="flex items-center gap-3">
                <span
                  aria-hidden="true"
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-extrabold ${avatarClassName(entry.learner_id)}`}
                >
                  {entry.display_name.charAt(0).toUpperCase()}
                </span>
                <h3 className="font-extrabold text-heading">{entry.display_name}</h3>
              </div>
              <StandardsCoverage standards={entry.standards ?? []} />
              <WeakAreaSection recommendations={entry.recommendations} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

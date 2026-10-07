"use client";

import { useEffect, useState } from "react";
import { getRosterDirectory, joinRoster, type RosterDirectoryEntry } from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";

// spec 041 FR-019/FR-020 (T050): browse real instructors' publicly
// listed, open-enrollment classes and join one without a code --
// alongside JoinRosterForm's existing code-entry field, not replacing
// it. Joining reuses the *existing* `POST /api/rosters/join` with the
// directory entry's own join_code (no new join request shape).

export interface ClassDirectoryBrowseProps {
  learnerId: string;
}

type JoinPhase = "idle" | "enrolled" | "pending";

export default function ClassDirectoryBrowse({ learnerId }: ClassDirectoryBrowseProps) {
  const [entries, setEntries] = useState<RosterDirectoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [joiningRosterId, setJoiningRosterId] = useState<string | null>(null);
  const [joinPhase, setJoinPhase] = useState<Record<string, JoinPhase>>({});
  const [joinError, setJoinError] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    getRosterDirectory()
      .then((result) => {
        if (!cancelled) setEntries(result.rosters);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleJoin(entry: RosterDirectoryEntry) {
    setJoiningRosterId(entry.roster_id);
    setJoinError((previous) => ({ ...previous, [entry.roster_id]: "" }));
    try {
      const result = await joinRoster(learnerId, entry.join_code);
      setJoinPhase((previous) => ({ ...previous, [entry.roster_id]: result.status }));
    } catch (error) {
      setJoinError((previous) => ({
        ...previous,
        [entry.roster_id]: error instanceof Error ? error.message : String(error),
      }));
    } finally {
      setJoiningRosterId(null);
    }
  }

  if (loading) return null;

  return (
    <div className="flex flex-col gap-2" data-testid="class-directory">
      <span className="text-sm font-extrabold text-heading">Or join a listed class</span>
      {entries.length === 0 ? (
        <p className="text-sm text-muted" data-testid="class-directory-empty">
          No listed classes yet -- ask the instructor for a join code instead.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((entry) => {
            const phase = joinPhase[entry.roster_id] ?? "idle";
            return (
              <li
                key={entry.roster_id}
                className="flex items-center justify-between gap-3 rounded-2xl bg-surface-subtle px-4 py-3 text-sm"
              >
                <span>
                  {formatTopicId(entry.subject_id)}
                  {entry.grade != null && ` · Grade ${entry.grade}`} &middot;{" "}
                  {entry.instructor_display_name}
                </span>
                {phase === "idle" ? (
                  <button
                    type="button"
                    disabled={joiningRosterId === entry.roster_id}
                    onClick={() => handleJoin(entry)}
                    className="rounded-full bg-primary px-3 py-1 font-extrabold text-primary-foreground disabled:opacity-40"
                  >
                    {joiningRosterId === entry.roster_id ? "Joining…" : "Join"}
                  </button>
                ) : (
                  <span className="text-muted">
                    {phase === "enrolled" ? "Joined" : "Request sent"}
                  </span>
                )}
                {joinError[entry.roster_id] && (
                  <span className="text-error" data-testid="class-directory-join-error">
                    {joinError[entry.roster_id]}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

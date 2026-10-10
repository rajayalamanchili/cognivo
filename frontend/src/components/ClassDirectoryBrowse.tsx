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
  // spec 041 v041 mockup: the empty state's "I have a class code" link
  // switches the surrounding tab switcher to the code-entry tab.
  onNeedCode?: () => void;
  // spec 044 FR-004: lets the parent card learn a join actually
  // enrolled the learner (not a pending request), so it can select the
  // new tab -- fired only for "enrolled", never "pending".
  onJoined?: () => void;
}

type JoinPhase = "idle" | "enrolled" | "pending";

export default function ClassDirectoryBrowse({
  learnerId,
  onNeedCode,
  onJoined,
}: ClassDirectoryBrowseProps) {
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
      if (result.status === "enrolled") onJoined?.();
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
      {entries.length === 0 ? (
        <div
          className="flex flex-col items-center gap-1 rounded-2xl bg-surface-subtle p-5.5 text-center"
          data-testid="class-directory-empty"
        >
          <strong className="font-extrabold text-heading">No listed classes yet</strong>
          <span className="text-[15px] text-muted">
            Instructors choose whether to list their classes here. If you have a class code, use
            that instead.
          </span>
          {onNeedCode && (
            <button
              type="button"
              onClick={onNeedCode}
              className="mt-1.5 min-h-11 font-extrabold text-primary underline"
            >
              I have a class code
            </button>
          )}
        </div>
      ) : (
        <>
          <ul className="flex flex-col gap-2.5">
            {entries.map((entry) => {
              const phase = joinPhase[entry.roster_id] ?? "idle";
              return (
                <li
                  key={entry.roster_id}
                  className="flex flex-wrap items-center justify-between gap-3.5 rounded-2xl border border-border px-4 py-3.5 text-[15px]"
                >
                  <span className="flex flex-col" data-testid={`class-directory-entry-${entry.roster_id}`}>
                    <span>
                      <strong className="font-extrabold">{formatTopicId(entry.subject_id)}</strong>
                      <span className="text-muted">
                        {" "}
                        · {entry.grade != null ? `Grade ${entry.grade}` : "Ungraded"}
                      </span>
                    </span>
                    <span className="text-sm text-muted">{entry.instructor_display_name}</span>
                  </span>
                  {phase === "idle" ? (
                    <button
                      type="button"
                      disabled={joiningRosterId === entry.roster_id}
                      onClick={() => handleJoin(entry)}
                      className="min-h-11 rounded-full border-2 border-primary/25 bg-surface px-4.5 font-extrabold text-heading disabled:opacity-40"
                    >
                      {joiningRosterId === entry.roster_id ? "Joining…" : "Join"}
                    </button>
                  ) : (
                    <span className="rounded-full bg-success/15 px-3 py-0.5 text-[13px] font-extrabold text-success">
                      {phase === "enrolled" ? "Joined" : "Request sent"}
                    </span>
                  )}
                  {joinError[entry.roster_id] && (
                    <span
                      className="basis-full text-sm text-error"
                      data-testid="class-directory-join-error"
                    >
                      {joinError[entry.roster_id]}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="text-sm text-muted">
            Only open classes whose instructor chose to list them appear here. Joining enrolls
            this learner in that class&apos;s subject.
          </p>
        </>
      )}
    </div>
  );
}

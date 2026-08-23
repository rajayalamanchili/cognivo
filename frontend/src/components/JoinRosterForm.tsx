"use client";

import { useState, type FormEvent } from "react";
import { joinRoster } from "@/services/api";

export interface JoinRosterFormProps {
  learnerId: string;
}

type Phase = "idle" | "submitting" | "enrolled" | "pending" | "error";

export default function JoinRosterForm({ learnerId }: JoinRosterFormProps) {
  const [joinCode, setJoinCode] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setPhase("submitting");
    setErrorText(null);
    try {
      const result = await joinRoster(learnerId, joinCode.trim());
      setPhase(result.status);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : String(error));
      setPhase("error");
    }
  }

  if (phase === "enrolled") {
    return <p className="text-sm">Joined the roster.</p>;
  }
  if (phase === "pending") {
    return <p className="text-sm">Join request sent -- waiting on instructor approval.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        type="text"
        required
        placeholder="Join code"
        value={joinCode}
        onChange={(event) => setJoinCode(event.target.value)}
        className="rounded border border-black/20 px-2 py-1 text-sm dark:border-white/20"
      />
      <button
        type="submit"
        disabled={phase === "submitting" || joinCode.trim() === ""}
        className="rounded bg-foreground px-3 py-1 text-sm text-background disabled:opacity-40"
      >
        {phase === "submitting" ? "Joining…" : "Join roster"}
      </button>
      {phase === "error" && errorText && (
        <span className="text-sm text-red-600" data-testid="join-roster-error">
          {errorText}
        </span>
      )}
    </form>
  );
}

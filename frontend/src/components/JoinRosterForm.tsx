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
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-2.5">
      <label className="flex flex-col gap-1.5 text-[15px] font-extrabold">
        Class code
        {/* Placeholder text kept as "Join code" (not the mockup's
            literal "e.g. K7Q-4MX") -- existing Playwright e2e specs
            (instructor-classroom-round-trip,
            instructor-assigned-quiz-round-trip) locate this field by
            that exact placeholder. */}
        <input
          type="text"
          required
          placeholder="Join code"
          value={joinCode}
          onChange={(event) => setJoinCode(event.target.value)}
          className="min-h-12 w-[220px] rounded-xl border-2 border-primary/25 px-3.5 font-mono text-[15px] font-normal"
        />
      </label>
      <button
        type="submit"
        disabled={phase === "submitting" || joinCode.trim() === ""}
        className="min-h-12 rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
      >
        {phase === "submitting" ? "Joining…" : "Join roster"}
      </button>
      <span className="basis-full text-sm text-muted">
        Got a code from an instructor? Some classes need their approval first. We&apos;ll show
        &quot;waiting on approval&quot; until they approve.
      </span>
      {phase === "error" && errorText && (
        <span className="basis-full text-sm text-error" data-testid="join-roster-error">
          {errorText}
        </span>
      )}
    </form>
  );
}

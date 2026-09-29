import { getExplanationCopyTier } from "@/lib/explainabilityCopy";
import type { NextQuestion } from "@/services/api";

// Spec 025 FR-001/FR-002/FR-003/FR-004: "why this question" chip for a
// question served by the Sequencing Agent's own next-question picker
// (ordinary practice, both timed-practice routes). Never rendered for
// quiz -- quiz's round-robin topic selection has no is_fallback/decay
// concept at all (research.md §1 correction), so there is no selection
// reason to report there, not merely one this component declines to show.

const DEFAULT_EXPLAIN_EVERY_PICK = process.env.NEXT_PUBLIC_EXPLAIN_EVERY_PICK !== "false";

const RELATIVE_TIME = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

// Native Intl.RelativeTimeFormat, not a new date-library dependency --
// this project has none installed, and this is the only place elapsed
// time needs human wording (FR-002: "you last practiced it about 6
// months ago", not just a raw duration).
function formatElapsed(lastPracticedAt: string): string {
  const elapsedDays = Math.floor((Date.now() - new Date(lastPracticedAt).getTime()) / 86_400_000);
  if (elapsedDays < 1) return "today";
  if (elapsedDays < 7) return RELATIVE_TIME.format(-elapsedDays, "day");
  if (elapsedDays < 30) return RELATIVE_TIME.format(-Math.floor(elapsedDays / 7), "week");
  if (elapsedDays < 365) return RELATIVE_TIME.format(-Math.floor(elapsedDays / 30), "month");
  return RELATIVE_TIME.format(-Math.floor(elapsedDays / 365), "year");
}

export interface SelectionReasonChipProps {
  question: NextQuestion;
  // Defaults to `NEXT_PUBLIC_EXPLAIN_EVERY_PICK` (FR-003) -- exposed as a
  // prop so tests don't need to fight Next.js's build-time env inlining.
  explainEveryPick?: boolean;
}

export default function SelectionReasonChip({
  question,
  explainEveryPick = DEFAULT_EXPLAIN_EVERY_PICK,
}: SelectionReasonChipProps) {
  const { is_fallback, p_mastery, effective_p_mastery, last_practiced_at, unlocked_grade } =
    question;

  // FR-004: no selection-reason data at all (e.g. this component used
  // against a quiz/placement question, which structurally never has it)
  // -- omit rather than guess.
  if (is_fallback === undefined) return null;

  let text: string;
  if (is_fallback) {
    // FR-004: never fabricate a reason -- a fallback pick with no real
    // mastery/timestamp data behind it (shouldn't happen by construction,
    // but asserted defensively) gets no chip rather than a broken message.
    if (p_mastery == null || effective_p_mastery == null || last_practiced_at == null) {
      return null;
    }
    const tier = getExplanationCopyTier(unlocked_grade);
    text = `${tier.decayFraming} (last practiced ${formatElapsed(last_practiced_at)})`;
  } else {
    if (!explainEveryPick) return null;
    text = "Next step in your practice path.";
  }

  return (
    <p
      data-testid="selection-reason-chip"
      className="rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary"
    >
      {text}
    </p>
  );
}

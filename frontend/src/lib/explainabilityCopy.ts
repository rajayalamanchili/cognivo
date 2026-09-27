// Grade-band-keyed explanation copy tiers (spec 025 FR-016, research.md
// §8) -- a pure, client-side lookup. Mirrors `pacing.ts`'s
// `getPacingProfile` pattern and grade-band boundaries independently: no
// shared code, since (per that same precedent) each of these small
// lookups is meant to be easy to product-tune on its own without
// touching the others.

export interface ExplanationCopyTier {
  // "Why this question" chip wording for a decayed/fallback review pick.
  decayFraming: string;
  // Dashboard copy for a topic whose effective mastery has decayed below its peak.
  recoveryFraming: string;
  // "Refreshed" acknowledgment wording (User Story 4).
  refreshedFraming: string;
}

const DEFAULT_TIER: ExplanationCopyTier = {
  decayFraming: "Reviewing this -- it's been a while since you last practiced it.",
  recoveryFraming: "This one's faded a little. A bit more practice will bring it right back.",
  refreshedFraming: "Nice -- you've brought this one back up.",
};

const YOUNGEST_TIER: ExplanationCopyTier = {
  decayFraming: "Let's practice this again -- it's been a while!",
  recoveryFraming: "You knew this before! A little practice will help you remember.",
  refreshedFraming: "You did it! You remembered this again!",
};

const MIDDLE_TIER: ExplanationCopyTier = {
  decayFraming: "Time for a quick review -- you haven't practiced this in a while.",
  recoveryFraming: "This one's a bit rusty. Practicing it again will help it stick.",
  refreshedFraming: "You've got it back -- nice work refreshing this one.",
};

const TEEN_TIER: ExplanationCopyTier = {
  decayFraming: "Reviewing this -- your mastery here has faded since you last practiced it.",
  recoveryFraming: "This topic has decayed since you last practiced it -- practice to restore it.",
  refreshedFraming: "You've refreshed this topic back to mastered.",
};

const OLDER_TIER: ExplanationCopyTier = {
  decayFraming: "Review: mastery on this topic has decayed since your last practice session.",
  recoveryFraming: "This topic's effective mastery has decayed -- practice restores it to your peak.",
  refreshedFraming: "Mastery restored -- this topic is back above the mastered threshold.",
};

export function getExplanationCopyTier(unlockedGrade: number | null): ExplanationCopyTier {
  // No grade-band data (ungraded subject, or not yet placed) -- the
  // same "entirely unaffected" default this feature uses elsewhere
  // when grade-band data doesn't exist.
  if (unlockedGrade === null) return DEFAULT_TIER;
  // Same 1-2/3-5/6-8/9-12 boundaries as pacing.ts's getPacingProfile,
  // kept as an independent lookup rather than shared code (research.md §8).
  if (unlockedGrade <= 2) return YOUNGEST_TIER;
  if (unlockedGrade <= 5) return MIDDLE_TIER;
  if (unlockedGrade <= 8) return TEEN_TIER;
  return OLDER_TIER;
}

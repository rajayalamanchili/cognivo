// Session pacing by grade band (spec 019 FR-009, research.md Decision
// 6) -- a pure, client-side lookup. Uses the same 1-2/3-5/6-8/9-12
// boundaries as the backend's MediationTier, independently: no shared
// code, since the three user stories share no backend surface area on
// purpose, and this feature's whole point (unlike MediationTier) is
// that these numbers are easy to product-tune without a backend
// deploy.

export interface PacingProfile {
  // Reaching this many answered questions in one quiz session surfaces
  // the stopping-point prompt (FR-009, Acceptance Scenario 1).
  // `Infinity` means no checkpoint is ever shown (Acceptance Scenario 2).
  recommendedQuestionCount: number;
  reinforcementEveryN: number;
}

const NO_CHECKPOINT: PacingProfile = {
  recommendedQuestionCount: Infinity,
  reinforcementEveryN: Infinity,
};

export function getPacingProfile(unlockedGrade: number | null): PacingProfile {
  // No grade-band data (ungraded subject, or not yet placed) -- treated
  // as unbounded/no-checkpoint, the same "entirely unaffected" default
  // this feature uses elsewhere when grade-band data doesn't exist.
  if (unlockedGrade === null) return NO_CHECKPOINT;
  if (unlockedGrade <= 2) return { recommendedQuestionCount: 3, reinforcementEveryN: 1 };
  if (unlockedGrade <= 5) return { recommendedQuestionCount: 5, reinforcementEveryN: 2 };
  if (unlockedGrade <= 8) return { recommendedQuestionCount: 8, reinforcementEveryN: 3 };
  return NO_CHECKPOINT;
}

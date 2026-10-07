// A learner's avatar square gets its own background color (v041
// mockups) -- not a persisted setting, just a stable visual distinction
// between cards. Built from existing design tokens (FR-013), not new
// hex literals. Deterministic by id so a given learner's color doesn't
// change across reloads/re-renders. Shared by GuardianLearnerCard and
// the guardian Settings "Learners" list so the same learner shows the
// same color on both.
const AVATAR_PALETTE = [
  "bg-primary-subtle text-heading",
  "bg-warning/20 text-warning",
  "bg-success/20 text-success",
  "bg-link/15 text-link",
] as const;

export function avatarClassName(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length];
}

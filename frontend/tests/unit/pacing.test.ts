// Unit tests: getPacingProfile (spec 019 FR-009, research.md Decision 6).

import { describe, expect, it } from "vitest";
import { getPacingProfile } from "@/lib/pacing";

describe("getPacingProfile", () => {
  it("returns a short, frequent-reinforcement profile for an early grade band", () => {
    const profile = getPacingProfile(1);
    expect(profile.recommendedQuestionCount).toBeLessThan(10);
    expect(Number.isFinite(profile.recommendedQuestionCount)).toBe(true);
    expect(profile.reinforcementEveryN).toBeLessThanOrEqual(2);
  });

  it("returns progressively longer profiles as grade increases within the checkpointed range", () => {
    const early = getPacingProfile(2);
    const mid = getPacingProfile(4);
    const late = getPacingProfile(7);
    expect(mid.recommendedQuestionCount).toBeGreaterThan(early.recommendedQuestionCount);
    expect(late.recommendedQuestionCount).toBeGreaterThan(mid.recommendedQuestionCount);
  });

  it("returns an effectively-unbounded profile for a late grade band", () => {
    const profile = getPacingProfile(11);
    expect(profile.recommendedQuestionCount).toBe(Infinity);
  });

  it("returns an effectively-unbounded profile when there is no grade-band data", () => {
    const profile = getPacingProfile(null);
    expect(profile.recommendedQuestionCount).toBe(Infinity);
  });
});

// Unit tests: getExplanationCopyTier (spec 025 FR-016, Foundational T003).

import { describe, expect, it } from "vitest";
import { getExplanationCopyTier } from "@/lib/explainabilityCopy";

describe("getExplanationCopyTier", () => {
  it("returns a tier for the youngest grade band", () => {
    const tier = getExplanationCopyTier(1);
    expect(tier.refreshedFraming).toBeTruthy();
    expect(tier.decayFraming).toBeTruthy();
  });

  it("returns a tier for each of the other three grade bands", () => {
    expect(getExplanationCopyTier(4).decayFraming).toBeTruthy();
    expect(getExplanationCopyTier(7).decayFraming).toBeTruthy();
    expect(getExplanationCopyTier(11).decayFraming).toBeTruthy();
  });

  it("returns distinct copy across bands, not one fixed string reused everywhere", () => {
    const bands = [1, 4, 7, 11].map((grade) => getExplanationCopyTier(grade));
    const uniqueRefreshed = new Set(bands.map((tier) => tier.refreshedFraming));
    expect(uniqueRefreshed.size).toBeGreaterThan(1);
  });

  it("falls back to a sensible default tier when there is no grade-band data", () => {
    const tier = getExplanationCopyTier(null);
    expect(tier.refreshedFraming).toBeTruthy();
    expect(tier.decayFraming).toBeTruthy();
  });
});

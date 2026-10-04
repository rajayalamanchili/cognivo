import { describe, expect, it } from "vitest";
import { getFirstMissedCriterion, getMasteryNote, getNextNote } from "@/lib/answerResultCopy";

describe("answerResultCopy", () => {
  it("returns null mastery note when there's no prior mastery", () => {
    expect(
      getMasteryNote({
        correct: true,
        priorPMastery: null,
        posteriorPMastery: 0.6,
        firstMissedCriterion: null,
      }),
    ).toBeNull();
  });

  it("frames a mastery gain", () => {
    const note = getMasteryNote({
      correct: true,
      priorPMastery: 0.48,
      posteriorPMastery: 0.61,
      firstMissedCriterion: null,
    });
    expect(note).toContain("Up 13 points");
  });

  it("frames a mastery dip with the missed criterion", () => {
    const note = getMasteryNote({
      correct: false,
      priorPMastery: 0.48,
      posteriorPMastery: 0.46,
      firstMissedCriterion: "Distributes 4 to both terms",
    });
    expect(note).toContain("Down 2 points");
    expect(note).toContain("Distributes 4 to both terms");
  });

  it("frames the refreshed case distinctly from a plain gain", () => {
    const note = getMasteryNote({
      correct: true,
      priorPMastery: 0.79,
      posteriorPMastery: 0.87,
      refreshed: true,
      firstMissedCriterion: null,
    });
    expect(note).toContain("mastery line");
  });

  it("suggests the next question when correct", () => {
    expect(
      getNextNote({ correct: true, priorPMastery: 0.5, posteriorPMastery: 0.6, firstMissedCriterion: null }),
    ).toMatch(/next question/i);
  });

  it("names the missed criterion as the next focus when incorrect", () => {
    expect(
      getNextNote({
        correct: false,
        priorPMastery: 0.5,
        posteriorPMastery: 0.4,
        firstMissedCriterion: "Final value of x is correct",
      }),
    ).toBe("Focus on: Final value of x is correct");
  });

  it("falls back to generic review copy when there's no criterion to name", () => {
    expect(
      getNextNote({ correct: false, priorPMastery: 0.5, posteriorPMastery: 0.4, firstMissedCriterion: null }),
    ).toMatch(/review this topic/i);
  });

  it("finds the first missed criterion from flat criteria before step results", () => {
    expect(getFirstMissedCriterion(["a missed point"], null)).toBe("a missed point");
  });

  it("finds the first missed criterion from step results when flat criteria are absent", () => {
    expect(
      getFirstMissedCriterion(null, [
        { correct: true, criteria_missed: [] },
        { correct: false, criteria_missed: ["step 2 slip"] },
      ]),
    ).toBe("step 2 slip");
  });

  it("returns null when nothing was missed anywhere", () => {
    expect(getFirstMissedCriterion([], [{ correct: true, criteria_missed: [] }])).toBeNull();
  });
});

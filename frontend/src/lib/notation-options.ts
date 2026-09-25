// Spec 023 research.md §1: notation is plain Unicode text, not markup --
// a precomposed fraction/superscript/subscript character is just a
// string, so it needs no renderer and no backend change. Any fraction
// without a precomposed glyph is built from a superscript numerator +
// U+2044 FRACTION SLASH + subscript denominator (composeFraction below).

export interface NotationOption {
  label: string;
  insert: string;
  // Screen-reader-friendly name for the aria-label -- the raw glyph alone
  // (e.g. "⁻", "₂") doesn't announce as anything meaningful out of context.
  description: string;
}

// The full set of Unicode "vulgar fraction" precomposed characters.
export const FRACTION_OPTIONS: NotationOption[] = [
  { label: "¼", insert: "¼", description: "one quarter" },
  { label: "½", insert: "½", description: "one half" },
  { label: "¾", insert: "¾", description: "three quarters" },
  { label: "⅓", insert: "⅓", description: "one third" },
  { label: "⅔", insert: "⅔", description: "two thirds" },
  { label: "⅕", insert: "⅕", description: "one fifth" },
  { label: "⅖", insert: "⅖", description: "two fifths" },
  { label: "⅗", insert: "⅗", description: "three fifths" },
  { label: "⅘", insert: "⅘", description: "four fifths" },
  { label: "⅙", insert: "⅙", description: "one sixth" },
  { label: "⅚", insert: "⅚", description: "five sixths" },
  { label: "⅐", insert: "⅐", description: "one seventh" },
  { label: "⅛", insert: "⅛", description: "one eighth" },
  { label: "⅜", insert: "⅜", description: "three eighths" },
  { label: "⅝", insert: "⅝", description: "five eighths" },
  { label: "⅞", insert: "⅞", description: "seven eighths" },
  { label: "⅑", insert: "⅑", description: "one ninth" },
  { label: "⅒", insert: "⅒", description: "one tenth" },
];

const SUPERSCRIPT_DIGITS: Record<string, string> = {
  "0": "⁰",
  "1": "¹",
  "2": "²",
  "3": "³",
  "4": "⁴",
  "5": "⁵",
  "6": "⁶",
  "7": "⁷",
  "8": "⁸",
  "9": "⁹",
};

const SUBSCRIPT_DIGITS: Record<string, string> = {
  "0": "₀",
  "1": "₁",
  "2": "₂",
  "3": "₃",
  "4": "₄",
  "5": "₅",
  "6": "₆",
  "7": "₇",
  "8": "₈",
  "9": "₉",
};

// Exponent buttons: superscript digits 0-9 plus a superscript minus for
// negative exponents (e.g. 10⁻²).
export const EXPONENT_OPTIONS: NotationOption[] = [
  ...Object.entries(SUPERSCRIPT_DIGITS).map(([digit, glyph]) => ({
    label: glyph,
    insert: glyph,
    description: `exponent ${digit}`,
  })),
  { label: "⁻", insert: "⁻", description: "exponent minus sign" },
];

// Subscript buttons: digits only, sufficient for chemical formulas
// (H₂O, CO₂, C₆H₁₂O₆) -- research.md §1.
export const SUBSCRIPT_OPTIONS: NotationOption[] = Object.entries(SUBSCRIPT_DIGITS).map(
  ([digit, glyph]) => ({ label: glyph, insert: glyph, description: `subscript ${digit}` })
);

const FRACTION_SLASH = "⁄";

function toSuperscriptDigits(digits: string): string {
  return Array.from(digits)
    .map((d) => SUPERSCRIPT_DIGITS[d] ?? d)
    .join("");
}

function toSubscriptDigits(digits: string): string {
  return Array.from(digits)
    .map((d) => SUBSCRIPT_DIGITS[d] ?? d)
    .join("");
}

const DIGITS_ONLY = /^[0-9]+$/;

/** Composes an arbitrary numerator/denominator pair into a single
 * Unicode fraction string (e.g. "5", "12" -> "⁵⁄₁₂"). Returns null if
 * either side isn't plain digits, or the denominator is zero
 * (mathematically undefined), so a caller can disable its own insert
 * action rather than ever producing a half-built or nonsensical
 * fraction. */
export function composeFraction(numerator: string, denominator: string): string | null {
  if (!DIGITS_ONLY.test(numerator) || !DIGITS_ONLY.test(denominator)) return null;
  if (Number(denominator) === 0) return null;
  return `${toSuperscriptDigits(numerator)}${FRACTION_SLASH}${toSubscriptDigits(denominator)}`;
}

"use client";

import { useState } from "react";
import {
  FRACTION_OPTIONS,
  EXPONENT_OPTIONS,
  SUBSCRIPT_OPTIONS,
  composeFraction,
} from "@/lib/notation-options";

// Spec 023: every button here inserts one complete, already-valid
// notation unit -- the custom-fraction builder's own Insert button
// (disabled until both fields are digits) is the only place an
// incomplete construct could occur, and it never leaves that builder,
// so nothing incomplete can ever reach the answer field itself
// (FR-007 is satisfied by construction, not by a submit-time check).

export interface NotationToolbarProps {
  onInsert: (text: string) => void;
  disabled?: boolean;
}

export default function NotationToolbar({ onInsert, disabled }: NotationToolbarProps) {
  const [numerator, setNumerator] = useState("");
  const [denominator, setDenominator] = useState("");
  const customFraction = composeFraction(numerator, denominator);

  function insertCustomFraction() {
    if (!customFraction) return;
    onInsert(customFraction);
    setNumerator("");
    setDenominator("");
  }

  return (
    <div className="flex flex-wrap items-center gap-1" data-testid="notation-toolbar">
      {FRACTION_OPTIONS.map((option) => (
        <button
          key={option.label}
          type="button"
          disabled={disabled}
          onClick={() => onInsert(option.insert)}
          className="rounded border border-border px-2 py-1 text-sm disabled:opacity-40"
          data-testid={`notation-fraction-${option.label}`}
        >
          {option.label}
        </button>
      ))}
      <span className="mx-1 text-sm text-muted">exp</span>
      {EXPONENT_OPTIONS.map((option) => (
        <button
          key={`exp-${option.label}`}
          type="button"
          disabled={disabled}
          onClick={() => onInsert(option.insert)}
          className="rounded border border-border px-2 py-1 text-sm disabled:opacity-40"
          data-testid={`notation-exponent-${option.label}`}
        >
          {option.label}
        </button>
      ))}
      <span className="mx-1 text-sm text-muted">sub</span>
      {SUBSCRIPT_OPTIONS.map((option) => (
        <button
          key={`sub-${option.label}`}
          type="button"
          disabled={disabled}
          onClick={() => onInsert(option.insert)}
          className="rounded border border-border px-2 py-1 text-sm disabled:opacity-40"
          data-testid={`notation-subscript-${option.label}`}
        >
          {option.label}
        </button>
      ))}
      <span className="mx-1 text-sm text-muted">other fraction</span>
      <input
        type="number"
        placeholder="num"
        value={numerator}
        disabled={disabled}
        onChange={(event) => setNumerator(event.target.value)}
        className="w-12 rounded border border-border px-1 py-1 text-sm"
        data-testid="notation-fraction-numerator"
      />
      <span className="text-sm">/</span>
      <input
        type="number"
        placeholder="den"
        value={denominator}
        disabled={disabled}
        onChange={(event) => setDenominator(event.target.value)}
        className="w-12 rounded border border-border px-1 py-1 text-sm"
        data-testid="notation-fraction-denominator"
      />
      <button
        type="button"
        disabled={disabled || !customFraction}
        onClick={insertCustomFraction}
        className="rounded border border-border px-2 py-1 text-sm disabled:opacity-40"
        data-testid="notation-fraction-insert"
      >
        Insert
      </button>
    </div>
  );
}

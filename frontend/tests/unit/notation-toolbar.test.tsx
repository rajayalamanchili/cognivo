// Unit test: NotationToolbar's insertion buttons and its custom-fraction
// composer (spec 023 FR-001/FR-002/FR-007). The composer's Insert button
// stays disabled until both numerator and denominator are digits, so an
// incomplete fraction can never reach the caller's onInsert.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import NotationToolbar from "@/components/NotationToolbar";

describe("NotationToolbar", () => {
  it("inserts a precomposed fraction glyph on click", async () => {
    const onInsert = vi.fn();
    render(<NotationToolbar onInsert={onInsert} />);
    await userEvent.click(screen.getByTestId("notation-fraction-½"));
    expect(onInsert).toHaveBeenCalledWith("½");
  });

  it("inserts an exponent digit on click", async () => {
    const onInsert = vi.fn();
    render(<NotationToolbar onInsert={onInsert} />);
    await userEvent.click(screen.getByTestId("notation-exponent-²"));
    expect(onInsert).toHaveBeenCalledWith("²");
  });

  it("inserts a subscript digit on click", async () => {
    const onInsert = vi.fn();
    render(<NotationToolbar onInsert={onInsert} />);
    await userEvent.click(screen.getByTestId("notation-subscript-₂"));
    expect(onInsert).toHaveBeenCalledWith("₂");
  });

  it("disables the custom-fraction Insert button until both fields are digits", async () => {
    const onInsert = vi.fn();
    render(<NotationToolbar onInsert={onInsert} />);
    const insertButton = screen.getByTestId("notation-fraction-insert");
    expect(insertButton).toBeDisabled();

    await userEvent.type(screen.getByTestId("notation-fraction-numerator"), "5");
    expect(insertButton).toBeDisabled();

    await userEvent.type(screen.getByTestId("notation-fraction-denominator"), "12");
    expect(insertButton).not.toBeDisabled();
  });

  it("composes and inserts a custom fraction, then clears the fields", async () => {
    const onInsert = vi.fn();
    render(<NotationToolbar onInsert={onInsert} />);
    await userEvent.type(screen.getByTestId("notation-fraction-numerator"), "5");
    await userEvent.type(screen.getByTestId("notation-fraction-denominator"), "12");
    await userEvent.click(screen.getByTestId("notation-fraction-insert"));

    expect(onInsert).toHaveBeenCalledWith("⁵⁄₁₂");
    expect(screen.getByTestId("notation-fraction-numerator")).toHaveValue(null);
    expect(screen.getByTestId("notation-fraction-denominator")).toHaveValue(null);
  });

  it("disables every control when disabled is true", () => {
    render(<NotationToolbar onInsert={vi.fn()} disabled />);
    expect(screen.getByTestId("notation-fraction-½")).toBeDisabled();
    expect(screen.getByTestId("notation-exponent-²")).toBeDisabled();
    expect(screen.getByTestId("notation-subscript-₂")).toBeDisabled();
    expect(screen.getByTestId("notation-fraction-numerator")).toBeDisabled();
    expect(screen.getByTestId("notation-fraction-insert")).toBeDisabled();
  });
});

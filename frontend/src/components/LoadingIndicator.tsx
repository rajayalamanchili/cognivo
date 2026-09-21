// A progress indicator shown whenever the app is loading a page or
// waiting on an LLM call, instead of bare "Loading…" text. Two visual
// variants sharing one component/testid so every call site stays a
// one-line swap: "kid" (bouncing rocket, playful heading font, teal) for
// learner-facing pages, "professional" (a plain spinning ring, neutral
// muted text) for instructor-facing and other non-learner views.

export interface LoadingIndicatorProps {
  message?: string;
  // `compact`: inline, next to a button's own label (e.g. "Grading…").
  // Default: a full block for an empty page waiting to fill in.
  compact?: boolean;
  variant?: "kid" | "professional";
}

export default function LoadingIndicator({
  message = "Loading…",
  compact = false,
  variant = "kid",
}: LoadingIndicatorProps) {
  const icon =
    variant === "kid" ? (
      <span
        className={compact ? "animate-spin text-base" : "animate-bounce text-6xl"}
        aria-hidden="true"
      >
        {compact ? "⭐" : "🚀"}
      </span>
    ) : (
      <span
        className={
          "inline-block animate-spin rounded-full border-border border-t-primary " +
          (compact ? "h-4 w-4 border-2" : "h-10 w-10 border-4")
        }
        aria-hidden="true"
      />
    );

  const textClassName =
    variant === "kid"
      ? compact
        ? undefined
        : "font-heading text-lg text-primary"
      : compact
        ? "text-sm text-muted"
        : "text-sm text-muted";

  if (compact) {
    return (
      <span className="inline-flex items-center gap-2" data-testid="loading-indicator">
        {icon}
        <span className={textClassName}>{message}</span>
      </span>
    );
  }

  return (
    <div
      className="flex flex-col items-center gap-3 p-8 text-center"
      data-testid="loading-indicator"
    >
      {icon}
      <p className={textClassName}>{message}</p>
    </div>
  );
}

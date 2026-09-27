// Spec 025 FR-011, User Story 4: a one-shot celebration for the
// specific answer that crossed a topic back above the mastered band --
// renders nothing otherwise. Purely prop-driven, no fetch/state of its
// own, so it can never re-fire from anything but the value it's given.

export interface RefreshedBannerProps {
  refreshed: boolean;
}

export default function RefreshedBanner({ refreshed }: RefreshedBannerProps) {
  if (!refreshed) return null;

  return (
    <p
      data-testid="refreshed-banner"
      className="rounded-lg bg-success/15 px-4 py-3 text-sm font-medium text-success"
    >
      Nice -- you&apos;ve brought this one back up.
    </p>
  );
}

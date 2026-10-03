// Spec 025 FR-011, User Story 4: a one-shot celebration for the
// specific answer that crossed a topic back above the mastered band --
// renders nothing otherwise. Purely prop-driven, no fetch/state of its
// own, so it can never re-fire from anything but the value it's given.

import { getExplanationCopyTier } from "@/lib/explainabilityCopy";

export interface RefreshedBannerProps {
  refreshed: boolean;
  unlockedGrade?: number | null;
}

export default function RefreshedBanner({
  refreshed,
  unlockedGrade = null,
}: RefreshedBannerProps) {
  if (!refreshed) return null;

  const tier = getExplanationCopyTier(unlockedGrade);

  return (
    <p
      data-testid="refreshed-banner"
      className="rounded-[18px] bg-success/15 px-5 py-4 text-[15px] font-bold text-success"
    >
      {tier.refreshedFraming}
    </p>
  );
}

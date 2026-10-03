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
    <div
      role="status"
      data-testid="refreshed-banner"
      className="flex items-center gap-3.5 rounded-[18px] bg-success/15 px-5 py-4 text-[15px] font-bold text-success"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="flex-shrink-0">
        <path d="M21 12a9 9 0 1 1-3-6.7" />
        <path d="M21 4v5h-5" />
      </svg>
      <span>{tier.refreshedFraming}</span>
    </div>
  );
}

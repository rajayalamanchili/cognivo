"use client";

// One dashboard section per subject. Each of the three sub-sections
// (mastery, weak-area, path) is fetched and rendered independently
// with its own loading/loaded/error phase, so a failure in one never
// blocks the others (FR-007, FR-008) -- US2/US3 add the weak-area and
// path slots' own fetches in later phases.

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getActivitySummary,
  getMasteryState,
  getRecommendations,
  getTopicPriorityPreview,
  type CareerConnectionEntry,
  type MasteryTopicEntry,
  type RecommendationsResponse,
  type TopicPriorityPreview,
} from "@/services/api";
import MasteryView from "@/components/MasteryView";
import CareerConnectionsList from "@/components/CareerConnectionsList";
import WeakAreaSummary from "@/components/WeakAreaSummary";
import LoadingIndicator from "@/components/LoadingIndicator";
import { formatTopicId } from "@/lib/format-topic-id";
import { getExplanationCopyTier } from "@/lib/explainabilityCopy";

type SectionPhase = "loading" | "loaded" | "error";

// Shared failure-state presentation (FR-010): every sub-section's
// "couldn't load" state uses this same pattern rather than an
// independently-styled variant, and none auto-retries within a page load.
function CouldntLoad({ what }: { what: string }) {
  return <p className="text-error">Couldn&rsquo;t load {what}.</p>;
}

// 027-learner-ui-redesign, second pass: same small, independent
// elapsed-time helper SelectionReasonChip.tsx already has -- not
// extracted into shared code, matching explainabilityCopy.ts's own
// stated precedent (each of these stays easy to product-tune alone).
const RELATIVE_TIME = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

function formatElapsed(lastUpdatedAt: string): string {
  const elapsedDays = Math.floor((Date.now() - new Date(lastUpdatedAt).getTime()) / 86_400_000);
  if (elapsedDays < 1) return "today";
  if (elapsedDays < 7) return RELATIVE_TIME.format(-elapsedDays, "day");
  if (elapsedDays < 30) return RELATIVE_TIME.format(-Math.floor(elapsedDays / 7), "week");
  if (elapsedDays < 365) return RELATIVE_TIME.format(-Math.floor(elapsedDays / 30), "month");
  return RELATIVE_TIME.format(-Math.floor(elapsedDays / 365), "year");
}

export interface DashboardSubjectSectionProps {
  subjectId: string;
  displayName: string;
  learnerId: string;
}

export default function DashboardSubjectSection({
  subjectId,
  displayName,
  learnerId,
}: DashboardSubjectSectionProps) {
  const [masteryPhase, setMasteryPhase] = useState<SectionPhase>("loading");
  const [masteryTopics, setMasteryTopics] = useState<MasteryTopicEntry[]>([]);
  const [unlockedGrade, setUnlockedGrade] = useState<number | null>(null);
  // 027-learner-ui-redesign, gap-closing pass: the "Refreshed!" banner
  // -- part of the same mastery-state response already fetched below,
  // no new fetch.
  const [recentlyRefreshedTopicId, setRecentlyRefreshedTopicId] = useState<string | null>(null);
  // Spec 039 FR-003 -- off its already-fetched getMasteryState call
  // below, no new fetch.
  const [careerConnections, setCareerConnections] = useState<CareerConnectionEntry[]>([]);

  const [weakAreaPhase, setWeakAreaPhase] = useState<SectionPhase>("loading");
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);

  const [pathPhase, setPathPhase] = useState<SectionPhase>("loading");
  const [pathPreview, setPathPreview] = useState<TopicPriorityPreview | null>(null);

  // 027-learner-ui-redesign FR-009: the one new fetch this feature adds,
  // independent of the three above for the same reason they're
  // independent of each other -- a failure here must not affect them.
  const [activityPhase, setActivityPhase] = useState<SectionPhase>("loading");
  const [questionsThisWeek, setQuestionsThisWeek] = useState<number | null>(null);
  const [questionsCorrectThisWeek, setQuestionsCorrectThisWeek] = useState<number | null>(null);

  // 027-learner-ui-redesign, gap-closing pass: the "Why this question?"
  // expand/collapse disclosure -- purely local UI state, same pattern
  // as `whyOpen` in the mockup's own script. Collapsed by default,
  // unlike the mockup's static sample (which shows it open) -- a real
  // disclosure should start closed.
  const [whyOpen, setWhyOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // Fetched fresh on every mount, never cached (FR-006).
    getMasteryState(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setMasteryTopics(result.topics);
        setUnlockedGrade(result.unlocked_grade);
        setRecentlyRefreshedTopicId(result.recently_refreshed_topic_id);
        setCareerConnections(result.career_connections ?? []);
        setMasteryPhase("loaded");
      })
      .catch(() => {
        if (cancelled) return;
        setMasteryPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  useEffect(() => {
    let cancelled = false;
    // Independent of the mastery fetch above: a failure here must not
    // affect the mastery view (FR-007), and vice versa.
    getRecommendations(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setRecommendations(result);
        setWeakAreaPhase("loaded");
      })
      .catch(() => {
        if (cancelled) return;
        setWeakAreaPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  useEffect(() => {
    let cancelled = false;
    // Independent of the mastery/weak-area fetches above: a failure
    // here must not affect either of them (FR-008).
    getTopicPriorityPreview(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setPathPreview(result);
        setPathPhase("loaded");
      })
      .catch(() => {
        if (cancelled) return;
        setPathPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  useEffect(() => {
    let cancelled = false;
    getActivitySummary(learnerId, subjectId)
      .then((result) => {
        if (cancelled) return;
        setQuestionsThisWeek(result.questions_this_week);
        setQuestionsCorrectThisWeek(result.questions_correct_this_week);
        setActivityPhase("loaded");
      })
      .catch(() => {
        if (cancelled) return;
        setActivityPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  // Derived entirely from masteryTopics (already fetched above) -- no
  // new data, matching FR-002's "prefer a client-side derivation over a
  // new network call" ordering.
  const scoredTopics = masteryTopics.filter((topic) => topic.status === "scored");
  const masteredCount = scoredTopics.filter((topic) => topic.band === "mastered").length;
  const refreshCandidates = scoredTopics.filter(
    (topic) =>
      topic.band === "mastered" &&
      topic.effective_p_mastery != null &&
      Math.round(topic.effective_p_mastery * 100) < Math.round((topic.p_mastery ?? 0) * 100),
  );
  // Most-decayed first -- the single most worth surfacing in the card.
  const refreshTopic = [...refreshCandidates].sort(
    (a, b) => (a.effective_p_mastery ?? 0) - (b.effective_p_mastery ?? 0),
  )[0];

  const nextTopicState =
    pathPreview &&
    masteryTopics.find((topic) => topic.topic_id === pathPreview.next_topic.topic_id);
  const tier = getExplanationCopyTier(unlockedGrade);

  function upNextWhyText(): string {
    if (!pathPreview) return "";
    if (!pathPreview.is_fallback) return "Next step in your practice path.";
    const peak = nextTopicState?.p_mastery;
    const effective = nextTopicState?.effective_p_mastery;
    const lastUpdated = nextTopicState?.last_updated_at;
    const hasDecayed =
      peak != null && effective != null && Math.round(effective * 100) < Math.round(peak * 100);
    if (hasDecayed && lastUpdated) {
      return `${tier.decayFraming} (last practiced ${formatElapsed(lastUpdated)})`;
    }
    return "Reviewing one of your mastered topics to help it stick.";
  }

  // 027-learner-ui-redesign, gap-closing pass: the "Why this question?"
  // disclosure's three rows -- reuses the exact same fields
  // `upNextWhyText` above already derives from already-fetched data,
  // just split into the mockup's three-line layout instead of one
  // sentence. `null` only when `pathPreview` hasn't loaded yet.
  function whyDisclosureRows(): { pickedBecause: string; currentEstimate: string } | null {
    if (!pathPreview) return null;
    if (!pathPreview.is_fallback) {
      const prereq = pathPreview.next_topic_prerequisite_display_name;
      const pickedBecause = prereq
        ? `You've mastered ${prereq}, its prerequisite — this is the next step on your path.`
        : "This is the next topic in your practice path.";
      const currentEstimate =
        nextTopicState?.p_mastery != null
          ? `${Math.round(nextTopicState.p_mastery * 100)}% — not yet at the mastered line.`
          : "Not yet attempted.";
      return { pickedBecause, currentEstimate };
    }

    const peak = nextTopicState?.p_mastery;
    const effective = nextTopicState?.effective_p_mastery;
    const hasDecayed =
      peak != null && effective != null && Math.round(effective * 100) < Math.round(peak * 100);
    const pickedBecause = hasDecayed
      ? tier.recoveryFraming
      : "Reviewing one of your mastered topics to help it stick.";
    const currentEstimate = hasDecayed
      ? `${Math.round((effective ?? 0) * 100)}% retained — your peak was ${Math.round((peak ?? 0) * 100)}%.`
      : peak != null
        ? `${Math.round(peak * 100)}% mastered.`
        : "Not yet attempted.";
    return { pickedBecause, currentEstimate };
  }

  return (
    <section
      data-testid={`dashboard-subject-section-${subjectId}`}
      className="flex flex-col gap-5 rounded-card border border-border bg-surface p-7"
    >
      {/* 027-learner-ui-redesign, gap-closing pass: the mockup has no
          visible per-card subject heading (the subject-pill toggle
          above already names it) -- kept as a screen-reader-only
          heading rather than removed, so the section still has an
          accessible name when there's only one subject and no pills
          render at all. */}
      <h2 className="sr-only">{displayName}</h2>

      <div data-testid="dashboard-path-slot">
        {pathPhase === "loading" && <LoadingIndicator message="Mapping your path…" compact />}
        {pathPhase === "error" && <CouldntLoad what="your up-next pick" />}
        {pathPhase === "loaded" && pathPreview && (
          <div className="grid grid-cols-1 gap-5 rounded-[20px] bg-surface-subtle p-6 md:grid-cols-[1.4fr_1fr]">
            <div className="flex flex-col gap-3">
              <span className="text-[13px] font-extrabold tracking-[0.08em] text-primary">
                UP NEXT
              </span>
              <h3 className="font-heading text-[32px] font-bold leading-tight text-heading">
                {pathPreview.next_topic.display_name}
              </h3>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="w-fit rounded-full bg-primary-subtle px-4 py-1.5 text-[15px] font-bold text-heading">
                  {upNextWhyText()}
                </span>
                <button
                  type="button"
                  aria-expanded={whyOpen}
                  onClick={() => setWhyOpen((open) => !open)}
                  className="font-extrabold text-primary underline"
                >
                  Why this question?
                </button>
              </div>
              {whyOpen &&
                (() => {
                  const rows = whyDisclosureRows();
                  if (!rows) return null;
                  return (
                    <div className="flex flex-col gap-2 rounded-[16px] bg-surface-subtle p-5 text-[15px]">
                      <div className="flex gap-2">
                        <span className="min-w-[150px] font-extrabold">Picked because</span>
                        <span>{rows.pickedBecause}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="min-w-[150px] font-extrabold">Your current estimate</span>
                        <span>{rows.currentEstimate}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="min-w-[150px] font-extrabold">Recorded by</span>
                        <span>The Sequencing Agent&rsquo;s selection log for this pick.</span>
                      </div>
                    </div>
                  );
                })()}
              <div className="mt-2 flex flex-wrap gap-3">
                <Link
                  href={`/practice?subject=${subjectId}`}
                  className="rounded-full bg-primary px-6 py-3 text-[17px] font-extrabold text-primary-foreground"
                >
                  Start practicing
                </Link>
                <Link
                  href="/tutor"
                  className="rounded-full border-2 border-primary/30 px-6 py-3 text-[17px] font-extrabold text-primary"
                >
                  Ask the AI Tutor first
                </Link>
              </div>
              {pathPreview.upcoming_topics.length > 0 && (
                // 027-learner-ui-redesign, gap-closing pass: the one piece of
                // PathVisualization.tsx that wasn't already shown elsewhere on
                // this screen (the rest -- "assessed so far," the single
                // "up next" topic -- fully duplicated "Your topics" and this
                // same hero), folded into the hero it's actually about rather
                // than kept as its own unstyled, mostly-redundant block.
                <p className="text-sm text-muted">
                  Likely coming up:{" "}
                  {pathPreview.upcoming_topics
                    .slice(0, 3)
                    .map((topic) => topic.display_name)
                    .join(", ")}
                  .{" "}
                  <span className="italic">
                    Illustrative only -- subject to change as your mastery updates.
                  </span>
                </p>
              )}
            </div>

            {refreshTopic ? (
              <div className="flex flex-col gap-3 rounded-[16px] bg-warning/10 p-5">
                <span className="font-extrabold text-warning">Ready for a refresh</span>
                <span className="font-heading text-[22px] font-bold text-heading">
                  {formatTopicId(refreshTopic.topic_id)}
                </span>
                <p className="text-[15px] text-muted">
                  {refreshTopic.last_updated_at
                    ? `Last practiced ${formatElapsed(refreshTopic.last_updated_at)}. `
                    : ""}
                  {tier.recoveryFraming}
                </p>
                {refreshTopic.effective_p_mastery != null && refreshTopic.p_mastery != null && (
                  <div className="flex flex-col gap-1.5">
                    <div className="relative h-3 rounded-full bg-warning/15">
                      <div
                        className="absolute inset-y-0 left-0 box-border rounded-full border-2 border-dashed border-warning/60"
                        style={{ width: `${Math.round(refreshTopic.p_mastery * 100)}%` }}
                      />
                      <div
                        className="absolute inset-y-0 left-0 rounded-full bg-warning"
                        style={{ width: `${Math.round(refreshTopic.effective_p_mastery * 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-sm font-bold text-muted">
                      <span>Retained {Math.round(refreshTopic.effective_p_mastery * 100)}%</span>
                      <span>Your best {Math.round(refreshTopic.p_mastery * 100)}%</span>
                    </div>
                  </div>
                )}
                <Link
                  href={`/practice?subject=${subjectId}`}
                  className="w-fit font-extrabold text-warning underline"
                >
                  Practice now
                </Link>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1 rounded-[16px] border border-border p-5">
          <span className="text-[15px] font-bold text-muted">Topics mastered</span>
          <span className="font-heading text-[36px] font-bold text-heading">
            {masteredCount} of {scoredTopics.length || masteryTopics.length}
          </span>
          <span className="text-sm text-muted">{displayName}</span>
        </div>
        <div className="flex flex-col gap-1 rounded-[16px] border border-border p-5">
          <span className="text-[15px] font-bold text-muted">Questions this week</span>
          <span className="font-heading text-[36px] font-bold text-heading">
            {activityPhase === "loaded" ? questionsThisWeek : activityPhase === "error" ? "—" : "…"}
          </span>
          <span className="text-sm text-muted">
            {activityPhase === "loaded" ? `${questionsCorrectThisWeek} answered correctly` : ""}
          </span>
        </div>
        <div className="flex flex-col gap-1 rounded-[16px] border border-border p-5">
          <span className="text-[15px] font-bold text-muted">Ready to refresh</span>
          <span className="font-heading text-[36px] font-bold text-heading">
            {refreshCandidates.length}
          </span>
          <span className="text-sm text-muted">Practice restores it</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <div data-testid="dashboard-weak-area-slot" className="flex flex-col gap-2">
          <h3 className="font-heading text-[26px] font-bold text-heading">Where to focus next</h3>
          {weakAreaPhase === "loading" && (
            <LoadingIndicator message="Spotting areas to practice…" compact />
          )}
          {weakAreaPhase === "error" && <CouldntLoad what="weak-area report" />}
          {weakAreaPhase === "loaded" && recommendations && (
            // Spec 025 User Story 6: the learner's own dashboard gets the
            // softened, encouraging rendering -- WeakAreaSection (raw
            // percentages/reason codes/misconception detail) remains the
            // instructor dashboard's own view of the same report.
            <WeakAreaSummary recommendations={recommendations} unlockedGrade={unlockedGrade} />
          )}
        </div>
        <div data-testid="dashboard-mastery-slot" className="flex flex-col gap-2">
          <h3 className="font-heading text-[26px] font-bold text-heading">Your topics</h3>
          {recentlyRefreshedTopicId && (
            <p
              data-testid="dashboard-refreshed-banner"
              className="rounded-[14px] bg-success/15 px-4 py-3 text-[15px] font-bold text-success"
            >
              Refreshed! {formatTopicId(recentlyRefreshedTopicId)} — {tier.refreshedFraming}
            </p>
          )}
          {masteryPhase === "loading" && (
            <LoadingIndicator message="Gathering your progress…" compact />
          )}
          {masteryPhase === "error" && <CouldntLoad what="mastery state" />}
          {masteryPhase === "loaded" && (
            <>
              <MasteryView topics={masteryTopics} unlockedGrade={unlockedGrade} />
              <CareerConnectionsList careerConnections={careerConnections} />
            </>
          )}
        </div>
      </div>
    </section>
  );
}

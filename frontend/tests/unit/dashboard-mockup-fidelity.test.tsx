// Unit tests for the Dashboard gap-closing pass (027-learner-ui-
// redesign, user-directed: "fix all deferred items and gaps"): the
// "Why this question?" expand/collapse disclosure, the refresh card's
// retained/best progress bar, the stat tiles' sub-lines, the
// "Refreshed!" banner, and (second round, "remove it, and add
// genuinely new information to existing tiles") the "Likely coming up"
// line folded into the UP NEXT hero in place of the removed, mostly-
// redundant standalone PathVisualization block. All derived from data
// the three existing fetches (mastery-state, topic-priority-preview,
// activity-summary) already carry -- no new fetch introduced by this
// test file's expectations.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardSubjectSection from "@/components/DashboardSubjectSection";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getMasteryState: vi.fn(),
    getRecommendations: vi.fn(),
    getTopicPriorityPreview: vi.fn(),
    getActivitySummary: vi.fn(),
  };
});

const confidentRecommendations = {
  subject_id: "algebra-1",
  data_sufficiency: "confident" as const,
  broad_review_needed: false,
  weak_areas: [],
  in_progress_topic_ids: [],
  not_yet_assessed_topic_ids: [],
  insufficient_data_topic_ids: [],
};

function masteryState({
  recentlyRefreshedTopicId = null,
}: { recentlyRefreshedTopicId?: string | null } = {}) {
  return {
    unlocked_grade: null,
    recently_refreshed_topic_id: recentlyRefreshedTopicId,
    topics: [
      {
        topic_id: "solving-one-step-equations",
        status: "scored" as const,
        p_mastery: 0.48,
        band: "developing" as const,
        last_updated_at: "2026-01-01T00:00:00Z",
        effective_p_mastery: 0.48,
      },
      {
        topic_id: "integers-and-operations",
        status: "scored" as const,
        p_mastery: 0.92,
        band: "mastered" as const,
        last_updated_at: "2026-06-01T00:00:00Z",
        effective_p_mastery: 0.68,
      },
    ],
  };
}

function topicPriorityPreview({
  prereq = null,
  upcoming = [],
}: {
  prereq?: string | null;
  upcoming?: {
    topic_id: string;
    display_name: string;
    band: "unknown";
    p_mastery: number | null;
  }[];
} = {}) {
  return {
    subject_id: "algebra-1",
    next_topic: {
      topic_id: "solving-one-step-equations",
      display_name: "Solving One-Step Equations",
      band: "developing" as const,
      p_mastery: 0.48,
    },
    upcoming_topics: upcoming,
    is_fallback: false,
    next_topic_prerequisite_display_name: prereq,
  };
}

function activitySummary() {
  return { questions_this_week: 27, questions_correct_this_week: 19 };
}

beforeEach(() => {
  vi.mocked(api.getMasteryState).mockReset();
  vi.mocked(api.getRecommendations).mockReset();
  vi.mocked(api.getTopicPriorityPreview).mockReset();
  vi.mocked(api.getActivitySummary).mockReset();
  vi.mocked(api.getRecommendations).mockResolvedValue(confidentRecommendations);
});

describe("DashboardSubjectSection mockup-fidelity gaps", () => {
  it("why-this-question disclosure starts collapsed and expands to show the prerequisite, estimate, and recorded-by rows", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(masteryState());
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(
      topicPriorityPreview({ prereq: "Variables and Expressions" }),
    );
    vi.mocked(api.getActivitySummary).mockResolvedValue(activitySummary());

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    const toggle = await screen.findByRole("button", { name: /why this question/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/picked because/i)).not.toBeInTheDocument();

    await userEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/picked because/i)).toBeInTheDocument();
    expect(screen.getByText(/you've mastered variables and expressions/i)).toBeInTheDocument();
    expect(screen.getByText(/48% — not yet at the mastered line/i)).toBeInTheDocument();
    expect(screen.getByText(/sequencing agent/i)).toBeInTheDocument();

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/picked because/i)).not.toBeInTheDocument();
  });

  it("names the next topic itself (no prerequisite line) when it has none", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(masteryState());
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(topicPriorityPreview({ prereq: null }));
    vi.mocked(api.getActivitySummary).mockResolvedValue(activitySummary());

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    await userEvent.click(await screen.findByRole("button", { name: /why this question/i }));
    expect(screen.getByText(/this is the next topic in your practice path/i)).toBeInTheDocument();
  });

  it("renders the refresh card's retained/best progress bar from already-fetched mastery values", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(masteryState());
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(topicPriorityPreview());
    vi.mocked(api.getActivitySummary).mockResolvedValue(activitySummary());

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    await screen.findByText(/ready for a refresh/i);
    expect(screen.getByText("Retained 68%")).toBeInTheDocument();
    expect(screen.getByText("Your best 92%")).toBeInTheDocument();
  });

  it("renders each stat tile's sub-line", async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(masteryState());
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(topicPriorityPreview());
    vi.mocked(api.getActivitySummary).mockResolvedValue(activitySummary());

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    expect(await screen.findByText("19 answered correctly")).toBeInTheDocument();
    expect(screen.getByText("Practice restores it")).toBeInTheDocument();
    // "Algebra I" also appears as the sr-only section heading -- scope
    // the assertion to the stat tile itself.
    const topicsMasteredTile = screen.getByText("Topics mastered").closest("div");
    expect(topicsMasteredTile).toHaveTextContent("Algebra I");
  });

  it('shows the "Refreshed!" banner naming the topic when mastery-state reports one', async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(
      masteryState({ recentlyRefreshedTopicId: "order-of-operations" }),
    );
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(topicPriorityPreview());
    vi.mocked(api.getActivitySummary).mockResolvedValue(activitySummary());

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    const banner = await screen.findByTestId("dashboard-refreshed-banner");
    expect(within(banner).getByText(/order of operations/i)).toBeInTheDocument();
  });

  it('omits the "Refreshed!" banner when mastery-state reports none', async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(masteryState());
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(topicPriorityPreview());
    vi.mocked(api.getActivitySummary).mockResolvedValue(activitySummary());

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    await waitFor(() => expect(api.getMasteryState).toHaveBeenCalled());
    expect(screen.queryByTestId("dashboard-refreshed-banner")).not.toBeInTheDocument();
  });

  it('shows "Likely coming up" (capped at 3) with the illustrative disclosure, folded into the UP NEXT hero in place of the removed PathVisualization block', async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(masteryState());
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(
      topicPriorityPreview({
        upcoming: [
          { topic_id: "a", display_name: "Topic A", band: "unknown", p_mastery: null },
          { topic_id: "b", display_name: "Topic B", band: "unknown", p_mastery: null },
          { topic_id: "c", display_name: "Topic C", band: "unknown", p_mastery: null },
          { topic_id: "d", display_name: "Topic D", band: "unknown", p_mastery: null },
        ],
      }),
    );
    vi.mocked(api.getActivitySummary).mockResolvedValue(activitySummary());

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    const line = await screen.findByText(/likely coming up/i);
    expect(line).toHaveTextContent("Topic A, Topic B, Topic C");
    expect(line).not.toHaveTextContent("Topic D");
    expect(line).toHaveTextContent(/illustrative only/i);
  });

  it('omits "Likely coming up" when there are no upcoming topics', async () => {
    vi.mocked(api.getMasteryState).mockResolvedValue(masteryState());
    vi.mocked(api.getTopicPriorityPreview).mockResolvedValue(topicPriorityPreview({ upcoming: [] }));
    vi.mocked(api.getActivitySummary).mockResolvedValue(activitySummary());

    render(
      <DashboardSubjectSection subjectId="algebra-1" displayName="Algebra I" learnerId="learner-1" />,
    );

    await screen.findByText("UP NEXT");
    expect(screen.queryByText(/likely coming up/i)).not.toBeInTheDocument();
  });
});

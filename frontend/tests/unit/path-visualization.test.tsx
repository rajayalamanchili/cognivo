// Unit test: PathVisualization renders assessed topics (derived from
// the existing mastery-state response), the top-priority next topic,
// and up to 3 upcoming topics -- and every render that includes an
// upcoming-topics list carries the visible illustrative/subject-to-
// change disclosure (FR-003, FR-004, SC-004, SC-006). T022.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PathVisualization from "@/components/PathVisualization";
import type { MasteryTopicEntry, TopicPriorityPreview } from "@/services/api";

const assessedTopics: MasteryTopicEntry[] = [
  {
    topic_id: "integers-and-operations",
    status: "scored",
    p_mastery: 0.8,
    band: "mastered",
    last_updated_at: "2026-01-01T00:00:00Z",
  },
];

const preview: TopicPriorityPreview = {
  subject_id: "algebra-1",
  next_topic: { topic_id: "linear-equations", display_name: "Linear Equations", band: "struggling", p_mastery: 0.2 },
  upcoming_topics: [
    { topic_id: "fractions", display_name: "Fractions", band: "unknown", p_mastery: null },
    { topic_id: "order-of-operations", display_name: "Order of Operations", band: "developing", p_mastery: 0.5 },
  ],
  is_fallback: false,
};

describe("PathVisualization", () => {
  it("renders assessed topics, the next topic, and up to 3 upcoming topics with the illustrative disclosure", () => {
    render(<PathVisualization assessedTopics={assessedTopics} preview={preview} />);

    expect(screen.getByText("Integers And Operations")).toBeInTheDocument();
    expect(screen.getByTestId("next-topic")).toHaveTextContent("Linear Equations");

    const upcoming = screen.getByTestId("upcoming-topics");
    expect(upcoming).toHaveTextContent("Fractions");
    expect(upcoming).toHaveTextContent("Order of Operations");

    expect(screen.getByTestId("illustrative-disclosure")).toBeInTheDocument();
  });

  it("caps the upcoming-topics list at 3 entries", () => {
    const manyUpcoming: TopicPriorityPreview = {
      ...preview,
      upcoming_topics: [
        { topic_id: "a", display_name: "A", band: "unknown", p_mastery: null },
        { topic_id: "b", display_name: "B", band: "unknown", p_mastery: null },
        { topic_id: "c", display_name: "C", band: "unknown", p_mastery: null },
        { topic_id: "d", display_name: "D", band: "unknown", p_mastery: null },
      ],
    };
    render(<PathVisualization assessedTopics={assessedTopics} preview={manyUpcoming} />);
    const items = screen.getByTestId("upcoming-topics").querySelectorAll("li");
    expect(items.length).toBeLessThanOrEqual(3);
  });

  it("does not show the illustrative disclosure when there are no upcoming topics", () => {
    render(
      <PathVisualization
        assessedTopics={assessedTopics}
        preview={{ ...preview, upcoming_topics: [] }}
      />,
    );
    expect(screen.queryByTestId("illustrative-disclosure")).not.toBeInTheDocument();
  });

  it("still shows the next topic when the learner has no assessed topics yet", () => {
    render(<PathVisualization assessedTopics={[]} preview={preview} />);
    expect(screen.getByTestId("next-topic")).toHaveTextContent("Linear Equations");
  });
});

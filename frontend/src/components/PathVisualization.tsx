import type { MasteryTopicEntry, TopicPriorityPreview } from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";

// Presentational only -- FR-003's three pieces (already-assessed
// topics, the Sequencing Agent's current top-priority next topic, and
// up to 3 likely-upcoming topics from that same ranking) plus FR-004's
// illustrative/subject-to-change disclosure, shown with the same
// wording and placement in every subject section (only rendered when
// there is an upcoming-topics list to disclose).

export interface PathVisualizationProps {
  assessedTopics: MasteryTopicEntry[];
  preview: TopicPriorityPreview;
}

export default function PathVisualization({ assessedTopics, preview }: PathVisualizationProps) {
  // SC-006: capped at 3 regardless of what the API returns.
  const upcomingTopics = preview.upcoming_topics.slice(0, 3);

  return (
    <div data-testid="path-visualization" className="flex flex-col gap-3">
      {assessedTopics.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted">Assessed so far</h3>
          <ul className="flex flex-col gap-1">
            {assessedTopics.map((topic) => (
              <li key={topic.topic_id} className="text-sm">
                {formatTopicId(topic.topic_id)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 className="text-sm font-medium text-muted">Up next</h3>
        <p data-testid="next-topic" className="font-medium">
          {preview.next_topic.display_name}
        </p>
      </div>

      {upcomingTopics.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted">Likely coming up</h3>
          <ol data-testid="upcoming-topics" className="flex flex-col gap-1">
            {upcomingTopics.map((topic) => (
              <li key={topic.topic_id} className="text-sm">
                {topic.display_name}
              </li>
            ))}
          </ol>
          <p data-testid="illustrative-disclosure" className="mt-1 text-xs text-muted">
            Illustrative only &mdash; subject to change as your mastery updates.
          </p>
        </div>
      )}
    </div>
  );
}

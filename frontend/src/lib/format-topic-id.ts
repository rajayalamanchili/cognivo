export function formatTopicId(topicId: string): string {
  return topicId
    .split("-")
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

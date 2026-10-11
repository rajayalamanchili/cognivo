"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  assignQuizToOwnLearner,
  getMasteryState,
  listLearnerEnrollments,
  type MasteryTopicEntry,
} from "@/services/api";
import { formatTopicId } from "@/lib/format-topic-id";

// spec 043 FR-017: shown only on a default-instructor-owned enrollment
// card -- resolved the same fail-silent way `GuardianLearnerStandards`
// resolves a learner's enrolled subject(s), via
// `GET /api/learners/{learner_id}/enrollments`'s `is_default_instructor_
// roster` field (contracts §5), so no second round-trip is needed.

export interface GuardianAssignQuizProps {
  learnerId: string;
  rosterId: string;
  onAssigned?: () => void;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function GuardianAssignQuiz({
  learnerId,
  rosterId,
  onAssigned,
}: GuardianAssignQuizProps) {
  const [eligible, setEligible] = useState(false);
  const [topics, setTopics] = useState<MasteryTopicEntry[]>([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([]);
  const [questionCount, setQuestionCount] = useState(5);
  const [dueAt, setDueAt] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assignedAt, setAssignedAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    listLearnerEnrollments(learnerId)
      .then((result) => {
        if (cancelled) return;
        const entry = result.enrollments.find((e) => e.roster_id === rosterId);
        setEligible(entry?.is_default_instructor_roster ?? false);
        if (!entry) return;
        return getMasteryState(learnerId, entry.subject_id).then((masteryResult) => {
          if (!cancelled) setTopics(masteryResult.topics);
        });
      })
      .catch(() => {
        // Secondary enrichment -- same precedent as GuardianLearnerStandards.
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, rosterId]);

  function toggleTopic(topicId: string) {
    setSelectedTopicIds((current) =>
      current.includes(topicId) ? current.filter((id) => id !== topicId) : [...current, topicId],
    );
  }

  if (!eligible) return null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setAssigning(true);
    setError(null);
    try {
      await assignQuizToOwnLearner(learnerId, rosterId, {
        topicIds: selectedTopicIds,
        questionCount,
        dueAt: dueAt ? new Date(dueAt).toISOString() : null,
      });
      setSelectedTopicIds([]);
      setQuestionCount(5);
      setDueAt("");
      setAssignedAt(Date.now());
      onAssigned?.();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setAssigning(false);
    }
  }

  return (
    <details className="border-t border-border pt-3.5">
      <summary className="flex min-h-11 cursor-pointer items-center font-extrabold text-primary">
        Assign a quiz
      </summary>
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-3 pt-2"
        data-testid="guardian-assign-quiz-form"
      >
        <fieldset className="flex flex-col gap-1.5" data-testid="guardian-assign-topic-ids">
          <legend className="text-sm font-extrabold">Topics</legend>
          <div className="flex flex-wrap gap-2">
            {topics.map((topic) => {
              const selected = selectedTopicIds.includes(topic.topic_id);
              return (
                <button
                  key={topic.topic_id}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => toggleTopic(topic.topic_id)}
                  className={`min-h-9 rounded-full px-3.5 text-sm font-bold ${
                    selected
                      ? "bg-primary text-primary-foreground"
                      : "border-2 border-border bg-surface text-heading"
                  }`}
                >
                  {formatTopicId(topic.topic_id)}
                </button>
              );
            })}
          </div>
        </fieldset>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-sm font-extrabold">
            Question count
            <input
              type="number"
              min={1}
              max={50}
              value={questionCount}
              onChange={(event) => setQuestionCount(Number(event.target.value))}
              data-testid="guardian-assign-question-count"
              className="min-h-11 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-extrabold">
            Due date (optional)
            <input
              type="datetime-local"
              value={dueAt}
              onChange={(event) => setDueAt(event.target.value)}
              data-testid="guardian-assign-due-at"
              className="min-h-11 rounded-xl border-2 border-primary/25 px-3.5 font-normal"
            />
          </label>
        </div>
        {error && (
          <p className="text-sm text-error" data-testid="guardian-assign-quiz-error">
            {error}
          </p>
        )}
        {assignedAt !== null && !error && (
          <p className="text-sm text-muted" data-testid="guardian-assign-quiz-success">
            Quiz assigned.
          </p>
        )}
        <button
          type="submit"
          disabled={assigning || selectedTopicIds.length === 0}
          className="self-start min-h-11 rounded-full bg-primary px-5 font-extrabold text-primary-foreground disabled:opacity-40"
        >
          {assigning ? "Assigning…" : "Assign quiz"}
        </button>
      </form>
    </details>
  );
}

"use client";

import { useEffect, useRef, useState, type ComponentPropsWithoutRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import {
  ApiError,
  getTutorExchange,
  streamTutorMessage,
  type TutorMessageErrorBody,
  type TutorRetrievedPassage,
} from "@/services/api";
import LoadingIndicator from "@/components/LoadingIndicator";
import { formatTopicId } from "@/lib/format-topic-id";

// Owns its own message list and streaming lifecycle (mirrors
// FreeTextAnswerInput's self-contained submission pattern) so the
// parent flow page only needs to hand it a `sessionId` once a
// Tutoring Session exists (FR-005's token-by-token delivery, FR-015's
// in-flight guardrail reflected in the UI as a disabled input while
// `streaming` is true).

export interface TutorChatProps {
  sessionId: string;
  // 027-learner-ui-redesign, gap-closing pass: reports the session's
  // accumulated, deduped grounding sources upward so tutor-flow.tsx's
  // sidebar can render "Sources used in this chat" -- this component
  // still owns the fetch (it already owns exchangeId/streaming state).
  onSourcesChange?: (sources: TutorRetrievedPassage[]) => void;
  // spec 044 FR-021 (US4): substituted into the suggested-prompt pills'
  // wording when available; falls back to today's generic wording when
  // absent (FR-022).
  currentTopicDisplayName?: string;
  // spec 044 FR-015 (US3): sent automatically, once per distinct value,
  // through the same submit path a learner's own typed message uses --
  // the mechanism Practice's inline panel relies on to show a hint with
  // no typing required. Re-fires on a new value (e.g. advancing to a
  // new practice question) so a fresh hint goes into this same session
  // (FR-017), but never resends the same value twice (e.g. re-opening
  // the panel for the same question).
  initialMessage?: string;
}

interface ChatMessage {
  role: "learner" | "tutor";
  text: string;
  exchangeId?: string;
  sources?: TutorRetrievedPassage[];
}

function sourceKey(source: TutorRetrievedPassage): string {
  return `${source.topic_id}:${source.field}`;
}

export function fieldLabel(field: string): string {
  return field === "skill_summary" ? "skill summary" : "difficulty notes";
}

type ErrorState =
  | "none"
  | "still-answering"
  | "rate-limited"
  | "question-too-long"
  | "moderation-rejected"
  | "tutor-unavailable";

const MAX_LENGTH = 2000;

// Tutor.dc.html's suggested-prompt pills, kept subject-agnostic (Constitution
// Principle III) rather than the mockup's algebra-specific wording -- these
// only ever pre-fill the input, so they're a restyle affordance, not new
// behavior (the existing submit path still owns what happens next).
// spec 044 FR-021/FR-022 (US4): worded around the active topic when one is
// available, falling back to this exact generic wording otherwise.
function suggestedPrompts(topicDisplayName?: string): string[] {
  if (!topicDisplayName) {
    return [
      "Give me a hint, not the answer",
      "Can you explain that differently?",
      "Show me a similar example",
    ];
  }
  return [
    `Give me a hint about ${topicDisplayName}, not the answer`,
    `Can you explain ${topicDisplayName} differently?`,
    `Show me a similar ${topicDisplayName} example`,
  ];
}

// No @tailwindcss/typography plugin is installed, and Tailwind's
// preflight reset strips default heading/list margins -- so markdown
// elements need their own minimal spacing here rather than relying on
// browser or "prose" defaults.
const MARKDOWN_COMPONENTS = {
  p: (props: ComponentPropsWithoutRef<"p">) => <p className="mb-2 last:mb-0" {...props} />,
  ul: (props: ComponentPropsWithoutRef<"ul">) => (
    <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0" {...props} />
  ),
  ol: (props: ComponentPropsWithoutRef<"ol">) => (
    <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0" {...props} />
  ),
  strong: (props: ComponentPropsWithoutRef<"strong">) => (
    <strong className="font-semibold" {...props} />
  ),
  code: (props: ComponentPropsWithoutRef<"code">) => (
    <code className="rounded bg-border/40 px-1 py-0.5 text-xs" {...props} />
  ),
  a: (props: ComponentPropsWithoutRef<"a">) => (
    <a className="underline" target="_blank" rel="noopener noreferrer" {...props} />
  ),
  // Tutor answers mix in untrusted retrieved-passage content (Milestone
  // 9 RAG) -- rendering markdown images would let `![](url)` silently
  // fetch an attacker-controlled URL as a side effect of displaying a
  // chat bubble (a known RAG-chat exfiltration pattern).
  img: () => null,
};

function RoleAvatar({ role }: { role: ChatMessage["role"] }) {
  return (
    <span
      title={role === "learner" ? "You" : "Tutor"}
      className={
        "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-base " +
        (role === "learner"
          ? "bg-primary text-primary-foreground"
          : "bg-primary-subtle text-heading")
      }
    >
      {role === "learner" ? "🙂" : "🦉"}
    </span>
  );
}

function stateFromError(error: unknown): ErrorState {
  if (error instanceof ApiError && error.body && typeof error.body === "object") {
    const body = error.body as TutorMessageErrorBody;
    if (body.error === "still_answering") return "still-answering";
    if (body.error === "rate_limited") return "rate-limited";
    if (body.error === "question_too_long") return "question-too-long";
    if (body.error === "moderation_rejected") return "moderation-rejected";
    if (body.error === "tutor_unavailable") return "tutor-unavailable";
  }
  return "none";
}

export default function TutorChat({
  sessionId,
  onSourcesChange,
  currentTopicDisplayName,
  initialMessage,
}: TutorChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [errorState, setErrorState] = useState<ErrorState>("none");
  const [sessionSources, setSessionSources] = useState<TutorRetrievedPassage[]>([]);

  const onSourcesChangeRef = useRef(onSourcesChange);
  useEffect(() => {
    onSourcesChangeRef.current = onSourcesChange;
  });
  useEffect(() => {
    onSourcesChangeRef.current?.(sessionSources);
  }, [sessionSources]);

  // Citations are enrichment on top of an answer that already rendered
  // successfully -- a failed fetch here shouldn't surface as a chat
  // error, so this swallows and just leaves that message without a
  // "Grounded in" row (spec 012's `grounded`/`retrieved_passage_ids`,
  // now readable by the demo learner per backend/src/api/routes/tutor.py).
  async function loadSources(exchangeId: string) {
    try {
      const detail = await getTutorExchange(exchangeId);
      if (!detail.grounded || detail.retrieved_passages.length === 0) return;
      setMessages((current) =>
        current.map((message) =>
          message.exchangeId === exchangeId
            ? { ...message, sources: detail.retrieved_passages }
            : message,
        ),
      );
      setSessionSources((current) => {
        const merged = [...current];
        for (const source of detail.retrieved_passages) {
          if (!merged.some((existing) => sourceKey(existing) === sourceKey(source))) {
            merged.push(source);
          }
        }
        return merged;
      });
    } catch {
      // Best-effort -- see function comment above.
    }
  }

  const sendMessage = useCallback(
    async (text: string) => {
      setErrorState("none");
      setMessages((current) => [
        ...current,
        { role: "learner", text },
        { role: "tutor", text: "" },
      ]);
      setStreaming(true);
      try {
        await streamTutorMessage(sessionId, text, (event) => {
          setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            next[next.length - 1] =
              "delta" in event
                ? { ...last, text: last.text + event.delta }
                : { ...last, exchangeId: event.exchange_id };
            return next;
          });
          if (!("delta" in event)) void loadSources(event.exchange_id);
        });
      } catch (error) {
        setErrorState(stateFromError(error));
        // The rejected question never got a real answer -- drop the
        // empty tutor placeholder bubble rather than leaving it blank.
        setMessages((current) => current.slice(0, -1));
      } finally {
        setStreaming(false);
      }
    },
    [sessionId],
  );

  // spec 044 FR-015/FR-017 (US3): Practice's inline panel passes a hint
  // request here instead of waiting for the learner to type -- re-fires
  // on each distinct value (a new question while the panel stays open)
  // but never resends the same one twice.
  const sentInitialMessageRef = useRef<string | null>(null);
  useEffect(() => {
    if (!initialMessage || streaming || sentInitialMessageRef.current === initialMessage) return;
    sentInitialMessageRef.current = initialMessage;
    void sendMessage(initialMessage);
  }, [initialMessage, streaming, sendMessage]);

  async function handleSubmit() {
    const text = question.trim();
    if (!text || streaming) return;
    setQuestion("");
    await sendMessage(text);
  }

  return (
    <div className="flex flex-col gap-4" data-testid="tutor-chat">
      <div className="flex flex-col gap-3" data-testid="tutor-chat-messages">
        {messages.map((message, index) => (
          <div
            key={index}
            className={
              "flex max-w-[85%] items-start gap-2 " +
              (message.role === "learner" ? "self-end flex-row-reverse" : "self-start")
            }
          >
            <RoleAvatar role={message.role} />
            <div className="flex flex-col gap-1.5">
              <div
                data-testid={
                  message.role === "learner"
                    ? "tutor-chat-learner-message"
                    : "tutor-chat-tutor-message"
                }
                data-exchange-id={message.exchangeId}
                className={
                  message.role === "learner"
                    ? "rounded-[22px] rounded-br-[6px] bg-primary px-[18px] py-3.5 text-primary-foreground"
                    : "rounded-[22px] rounded-bl-[6px] bg-surface-subtle px-5 py-4"
                }
              >
                {message.role === "tutor" && message.text ? (
                  <ReactMarkdown components={MARKDOWN_COMPONENTS}>{message.text}</ReactMarkdown>
                ) : (
                  message.text || (streaming && index === messages.length - 1 ? "…" : "")
                )}
              </div>
              {message.role === "tutor" && message.sources && message.sources.length > 0 && (
                <div
                  className="flex flex-wrap items-center gap-2 text-[13px]"
                  data-testid="tutor-grounded-in"
                >
                  <span className="font-bold text-heading">Grounded in</span>
                  {message.sources.map((source) => (
                    <span
                      key={sourceKey(source)}
                      className="rounded-full border border-border bg-surface px-3 py-1 font-bold text-heading"
                    >
                      {formatTopicId(source.topic_id)} · {fieldLabel(source.field)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {errorState === "still-answering" && (
        <p className="text-sm text-error" data-testid="tutor-error-still-answering">
          The tutor is still answering your last question.
        </p>
      )}
      {errorState === "rate-limited" && (
        <p className="text-sm text-error" data-testid="tutor-error-rate-limited">
          You&apos;ve asked a lot of questions recently. Please wait a bit and try again.
        </p>
      )}
      {errorState === "question-too-long" && (
        <p className="text-sm text-error" data-testid="tutor-error-too-long">
          Your question is too long (max {MAX_LENGTH} characters). Please shorten it.
        </p>
      )}
      {errorState === "moderation-rejected" && (
        <p className="text-sm text-error" data-testid="tutor-error-moderation">
          This question couldn&apos;t be accepted. Please revise and resubmit.
        </p>
      )}
      {errorState === "tutor-unavailable" && (
        <p className="text-sm text-error" data-testid="tutor-error-unavailable">
          The tutor is temporarily unavailable. Please try again shortly.
        </p>
      )}

      <div className="flex flex-wrap gap-2" data-testid="tutor-suggested-prompts">
        {suggestedPrompts(currentTopicDisplayName).map((prompt) => (
          <button
            key={prompt}
            type="button"
            disabled={streaming}
            onClick={() => setQuestion(prompt)}
            className="min-h-11 rounded-full border-2 border-primary/30 px-4 py-2 text-[15px] font-bold text-heading disabled:opacity-40"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2.5">
        <label htmlFor="tutor-question" className="sr-only">
          Ask the AI Tutor
        </label>
        <input
          id="tutor-question"
          type="text"
          className="min-h-[52px] flex-1 rounded-full border-2 border-primary/30 px-[22px] text-base"
          maxLength={MAX_LENGTH}
          value={question}
          disabled={streaming}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void handleSubmit();
            }
          }}
          placeholder="Ask about this topic…"
        />
        <button
          type="button"
          aria-label={streaming ? undefined : "Send"}
          onClick={() => void handleSubmit()}
          disabled={streaming || question.trim() === ""}
          className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-40"
        >
          {streaming ? (
            <LoadingIndicator message="Thinking…" compact />
          ) : (
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M5 12h14" />
              <path d="m13 6 6 6-6 6" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}

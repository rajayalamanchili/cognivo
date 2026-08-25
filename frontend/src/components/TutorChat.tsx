"use client";

import { useState } from "react";
import { ApiError, streamTutorMessage, type TutorMessageErrorBody } from "@/services/api";

// Owns its own message list and streaming lifecycle (mirrors
// FreeTextAnswerInput's self-contained submission pattern) so the
// parent flow page only needs to hand it a `sessionId` once a
// Tutoring Session exists (FR-005's token-by-token delivery, FR-015's
// in-flight guardrail reflected in the UI as a disabled input while
// `streaming` is true).

export interface TutorChatProps {
  sessionId: string;
}

interface ChatMessage {
  role: "learner" | "tutor";
  text: string;
  exchangeId?: string;
}

type ErrorState =
  | "none"
  | "still-answering"
  | "rate-limited"
  | "question-too-long"
  | "moderation-rejected"
  | "tutor-unavailable";

const MAX_LENGTH = 2000;

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

export default function TutorChat({ sessionId }: TutorChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [errorState, setErrorState] = useState<ErrorState>("none");

  async function handleSubmit() {
    const text = question.trim();
    if (!text || streaming) return;

    setErrorState("none");
    setQuestion("");
    setMessages((current) => [...current, { role: "learner", text }, { role: "tutor", text: "" }]);
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
      });
    } catch (error) {
      setErrorState(stateFromError(error));
      // The rejected question never got a real answer -- drop the
      // empty tutor placeholder bubble rather than leaving it blank.
      setMessages((current) => current.slice(0, -1));
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="flex flex-col gap-4" data-testid="tutor-chat">
      <div className="flex flex-col gap-3" data-testid="tutor-chat-messages">
        {messages.map((message, index) => (
          <div
            key={index}
            data-testid={
              message.role === "learner" ? "tutor-chat-learner-message" : "tutor-chat-tutor-message"
            }
            data-exchange-id={message.exchangeId}
            className={
              message.role === "learner"
                ? "self-end rounded-lg bg-primary px-4 py-2 text-primary-foreground"
                : "self-start rounded-lg border border-border px-4 py-2"
            }
          >
            {message.text || (streaming && index === messages.length - 1 ? "…" : "")}
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

      <div className="flex gap-2">
        <input
          type="text"
          className="flex-1 rounded-lg border border-border px-3 py-2"
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
          placeholder="Ask the tutor a question…"
        />
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={streaming || question.trim() === ""}
          className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-40"
        >
          {streaming ? "Answering…" : "Ask"}
        </button>
      </div>
    </div>
  );
}

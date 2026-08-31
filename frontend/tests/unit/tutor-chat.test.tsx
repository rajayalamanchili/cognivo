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
  };
});

describe("TutorChat", () => {
  beforeEach(() => {
    vi.mocked(api.streamTutorMessage).mockReset();
  });

  it("renders the learner's question and streams deltas into the tutor bubble", async () => {
    vi.mocked(api.streamTutorMessage).mockImplementation(async (_sessionId, _question, onEvent) => {
      onEvent({ delta: "Light " });
      onEvent({ delta: "provides the energy." });
      onEvent({ done: true, exchange_id: "ex-1" });
    });

    render(<TutorChat sessionId="session-1" />);
    await userEvent.type(screen.getByPlaceholderText(/ask the tutor/i), "why does it need light?");
    await userEvent.click(screen.getByRole("button", { name: /ask/i }));

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

  it("renders markdown in the tutor's answer instead of literal syntax", async () => {
    vi.mocked(api.streamTutorMessage).mockImplementation(async (_sessionId, _question, onEvent) => {
      onEvent({ delta: "Key points:\n\n- **Photosynthesis** needs light\n- It produces oxygen" });
      onEvent({ done: true, exchange_id: "ex-2" });
    });

    render(<TutorChat sessionId="session-1" />);
    await userEvent.type(screen.getByPlaceholderText(/ask the tutor/i), "how does it work?");
    await userEvent.click(screen.getByRole("button", { name: /ask/i }));

    const tutorMessage = await screen.findByTestId("tutor-chat-tutor-message");
    await waitFor(() => expect(tutorMessage.querySelector("ul")).not.toBeNull());
    expect(tutorMessage.querySelector("strong")).toHaveTextContent("Photosynthesis");
    expect(tutorMessage.querySelectorAll("li")).toHaveLength(2);
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
    const input = screen.getByPlaceholderText(/ask the tutor/i);
    await userEvent.type(input, "a question");
    await userEvent.click(screen.getByRole("button", { name: /ask/i }));

    expect(input).toBeDisabled();
    expect(screen.getByRole("button", { name: /answering/i })).toBeDisabled();

    resolveStream();
    await waitFor(() => expect(input).not.toBeDisabled());
  });

  it("shows a distinct message per rejection response and drops the empty tutor bubble", async () => {
    vi.mocked(api.streamTutorMessage).mockRejectedValue(
      new ApiError(429, "rate limited", { error: "rate_limited", retry_after_seconds: 42 }),
    );

    render(<TutorChat sessionId="session-1" />);
    await userEvent.type(screen.getByPlaceholderText(/ask the tutor/i), "a question");
    await userEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => expect(screen.getByTestId("tutor-error-rate-limited")).toBeInTheDocument());
    expect(screen.queryByTestId("tutor-chat-tutor-message")).not.toBeInTheDocument();
    expect(screen.getByTestId("tutor-chat-learner-message")).toBeInTheDocument();
  });

  it("clears a still-answering error once a later question succeeds", async () => {
    vi.mocked(api.streamTutorMessage).mockRejectedValueOnce(
      new ApiError(409, "still answering", { error: "still_answering", exchange_id: "ex-1" }),
    );

    render(<TutorChat sessionId="session-1" />);
    const input = screen.getByPlaceholderText(/ask the tutor/i);
    await userEvent.type(input, "first question");
    await userEvent.click(screen.getByRole("button", { name: /ask/i }));
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
    await userEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() =>
      expect(screen.queryByTestId("tutor-error-still-answering")).not.toBeInTheDocument(),
    );
  });
});

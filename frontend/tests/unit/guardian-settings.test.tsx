// Unit tests: guardian Settings page (spec 041 FR-009/FR-010/FR-011/FR-012).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GuardianSettingsPage from "@/app/(auth)/guardian/settings/page";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getWhoAmI: vi.fn(),
    listMyLearners: vi.fn(),
    updateGuardianMe: vi.fn(),
    changeGuardianPassword: vi.fn(),
    submitDeletionRequest: vi.fn(),
    getDeletionRequestStatus: vi.fn(),
  };
});

const BASE_WHOAMI = {
  account_type: "guardian" as const,
  identifier: "parent@example.com",
  pending_deletion_warnings: [],
  guardian_id: "guardian-1",
  name: null,
  read_aloud_default: false,
  larger_text: false,
  reduce_motion: false,
  theme: "system" as const,
  quiz_finished_email_enabled: true,
  weekly_summary_enabled: false,
};

const ONE_LEARNER = {
  learners: [
    {
      learner_id: "learner-1",
      display_name: "Eli",
      enrollment: { roster_id: "roster-1", subject_id: "algebra-1", grade: 7 },
    },
  ],
};

describe("GuardianSettingsPage", () => {
  beforeEach(() => {
    vi.mocked(api.getWhoAmI).mockReset().mockResolvedValue(BASE_WHOAMI);
    vi.mocked(api.listMyLearners).mockReset().mockResolvedValue(ONE_LEARNER);
    vi.mocked(api.updateGuardianMe).mockReset();
    vi.mocked(api.changeGuardianPassword).mockReset();
    vi.mocked(api.submitDeletionRequest).mockReset();
    vi.mocked(api.getDeletionRequestStatus).mockReset();
  });

  it("loads and displays the guardian's account and learners", async () => {
    render(<GuardianSettingsPage />);

    expect(await screen.findByDisplayValue("parent@example.com")).toBeInTheDocument();
    expect(await screen.findByText("Grade 7 · algebra-1")).toBeInTheDocument();
    expect((await screen.findAllByText("Eli")).length).toBeGreaterThan(0);
  });

  it("saves account name/email edits and reflects the persisted response", async () => {
    vi.mocked(api.updateGuardianMe).mockResolvedValue({
      name: "Dana",
      email: "dana@example.com",
      read_aloud_default: false,
      larger_text: false,
      reduce_motion: false,
      theme: "system",
      quiz_finished_email_enabled: true,
      weekly_summary_enabled: false,
    });
    const user = userEvent.setup();
    render(<GuardianSettingsPage />);

    const nameInput = await screen.findByLabelText("Name");
    await user.clear(nameInput);
    await user.type(nameInput, "Dana");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(api.updateGuardianMe).toHaveBeenCalledWith({
      name: "Dana",
      email: "parent@example.com",
    });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("changes the password and shows a confirmation", async () => {
    vi.mocked(api.changeGuardianPassword).mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<GuardianSettingsPage />);

    await screen.findByDisplayValue("parent@example.com");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    await user.type(screen.getByLabelText("Current password"), "old password here");
    await user.type(screen.getByLabelText("New password"), "a new password here");
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(api.changeGuardianPassword).toHaveBeenCalledWith(
      "old password here",
      "a new password here",
    );
    expect(await screen.findByText("Password changed.")).toBeInTheDocument();
  });

  it("shows an error when the current password is wrong", async () => {
    const { ApiError } = api;
    vi.mocked(api.changeGuardianPassword).mockRejectedValue(
      new ApiError(401, "invalid_credentials"),
    );
    const user = userEvent.setup();
    render(<GuardianSettingsPage />);

    await screen.findByDisplayValue("parent@example.com");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    await user.type(screen.getByLabelText("Current password"), "wrong password here");
    await user.type(screen.getByLabelText("New password"), "a new password here");
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(await screen.findByText("Current password is incorrect.")).toBeInTheDocument();
  });

  it("persists each Display/Notification preference toggle via its own PATCH call", async () => {
    vi.mocked(api.updateGuardianMe).mockResolvedValue({
      name: null,
      email: "parent@example.com",
      read_aloud_default: false,
      larger_text: true,
      reduce_motion: false,
      theme: "system",
      quiz_finished_email_enabled: true,
      weekly_summary_enabled: false,
    });
    const user = userEvent.setup();
    render(<GuardianSettingsPage />);

    const toggle = await screen.findByText("Larger text");
    const checkbox = toggle.closest("label")!.querySelector("input")!;
    await user.click(checkbox);

    expect(api.updateGuardianMe).toHaveBeenCalledWith({ larger_text: true });
    await waitFor(() => expect(checkbox).toBeChecked());
  });

  it("submits a learner-deletion request and shows its real pending status", async () => {
    vi.mocked(api.submitDeletionRequest).mockResolvedValue({
      deletion_request_id: "del-1",
      target_type: "learner",
      target_id: "learner-1",
      status: "pending",
      requested_at: "2026-10-06T00:00:00Z",
    });
    const user = userEvent.setup();
    render(<GuardianSettingsPage />);

    await screen.findByText("Grade 7 · algebra-1");
    await user.selectOptions(screen.getByDisplayValue("Choose a learner"), "learner-1");
    await user.click(screen.getByRole("button", { name: "Request deletion" }));

    expect(api.submitDeletionRequest).toHaveBeenCalledWith("learner", "learner-1");
    expect(await screen.findByText(/Status: pending/)).toBeInTheDocument();
  });

  it("submits a guardian account-deletion request targeting the guardian's own id", async () => {
    vi.mocked(api.submitDeletionRequest).mockResolvedValue({
      deletion_request_id: "del-2",
      target_type: "guardian",
      target_id: "guardian-1",
      status: "pending",
      requested_at: "2026-10-06T00:00:00Z",
    });
    const user = userEvent.setup();
    render(<GuardianSettingsPage />);

    await screen.findByText("Grade 7 · algebra-1");
    await user.click(screen.getByRole("button", { name: "Request account deletion" }));

    expect(api.submitDeletionRequest).toHaveBeenCalledWith("guardian", "guardian-1");
    expect(await screen.findByText(/Status: pending/)).toBeInTheDocument();
  });
});

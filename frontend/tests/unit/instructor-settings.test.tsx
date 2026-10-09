// Unit tests: instructor Settings page (spec 043 FR-007/FR-008/FR-009/
// FR-010/FR-011/FR-012), mirroring guardian-settings.test.tsx's own
// coverage of the guardian equivalent.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InstructorSettingsFlow from "@/app/instructor/settings/instructor-settings-flow";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getWhoAmI: vi.fn(),
    listRosters: vi.fn(),
    listRosterEnrollments: vi.fn(),
    updateInstructorMe: vi.fn(),
    changeInstructorPassword: vi.fn(),
    submitDeletionRequest: vi.fn(),
    getDeletionRequestStatus: vi.fn(),
  };
});

const BASE_WHOAMI = {
  account_type: "instructor" as const,
  identifier: "teacher@example.com",
  pending_deletion_warnings: [],
  instructor_id: "instructor-1",
  name: null,
  theme: "system" as const,
  larger_text: false,
  reduce_motion: false,
  notifications_enabled: true,
  default_enrollment_mode: "open" as const,
  default_due_date_offset_days: null,
};

const DEMO_WHOAMI = {
  account_type: "demo_instructor" as const,
  identifier: "Ms. Rivera (demo)",
  pending_deletion_warnings: [],
};

const ONE_ROSTER = { rosters: [{ roster_id: "roster-1", subject_id: "algebra-1", enrollment_mode: "open" as const, is_listed: true }] };
const ONE_ENROLLMENT = { enrollments: [{ learner_id: "learner-1", display_name: "Leo" }] };

const FULL_ME_RESPONSE = {
  display_name: null,
  theme: "system" as const,
  larger_text: false,
  reduce_motion: false,
  notifications_enabled: true,
  default_enrollment_mode: "open" as const,
  default_due_date_offset_days: null,
};

describe("InstructorSettingsFlow", () => {
  beforeEach(() => {
    vi.mocked(api.getWhoAmI).mockReset().mockResolvedValue(BASE_WHOAMI);
    vi.mocked(api.listRosters).mockReset().mockResolvedValue(ONE_ROSTER);
    vi.mocked(api.listRosterEnrollments).mockReset().mockResolvedValue(ONE_ENROLLMENT);
    vi.mocked(api.updateInstructorMe).mockReset();
    vi.mocked(api.changeInstructorPassword).mockReset();
    vi.mocked(api.submitDeletionRequest).mockReset();
    vi.mocked(api.getDeletionRequestStatus).mockReset();
  });

  it("loads and displays the instructor's account and learners", async () => {
    render(<InstructorSettingsFlow />);

    expect(await screen.findByDisplayValue("teacher@example.com")).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Leo · algebra-1" })).toBeInTheDocument();
  });

  it("saves the display name and reflects the persisted response", async () => {
    vi.mocked(api.updateInstructorMe).mockResolvedValue({
      ...FULL_ME_RESPONSE,
      display_name: "Ms. Rivera",
    });
    const user = userEvent.setup();
    render(<InstructorSettingsFlow />);

    const nameInput = await screen.findByLabelText(/Display name/);
    await user.clear(nameInput);
    await user.type(nameInput, "Ms. Rivera");
    const accountSection = screen.getByRole("heading", { name: "Account" }).closest("section")!;
    await user.click(within(accountSection).getByRole("button", { name: "Save changes" }));

    expect(api.updateInstructorMe).toHaveBeenCalledWith({ display_name: "Ms. Rivera" });
    expect(await within(accountSection).findByText("Saved.")).toBeInTheDocument();
  });

  it("changes the password and shows a confirmation", async () => {
    vi.mocked(api.changeInstructorPassword).mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<InstructorSettingsFlow />);

    await screen.findByDisplayValue("teacher@example.com");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    await user.type(screen.getByLabelText("Current password"), "old password here");
    await user.type(screen.getByLabelText("New password"), "a new password here");
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(api.changeInstructorPassword).toHaveBeenCalledWith(
      "old password here",
      "a new password here",
    );
    expect(await screen.findByText("Password changed.")).toBeInTheDocument();
  });

  it("shows an error when the current password is wrong", async () => {
    const { ApiError } = api;
    vi.mocked(api.changeInstructorPassword).mockRejectedValue(
      new ApiError(401, "invalid_credentials"),
    );
    const user = userEvent.setup();
    render(<InstructorSettingsFlow />);

    await screen.findByDisplayValue("teacher@example.com");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    await user.type(screen.getByLabelText("Current password"), "wrong password here");
    await user.type(screen.getByLabelText("New password"), "a new password here");
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(await screen.findByText("Current password is incorrect.")).toBeInTheDocument();
  });

  it("persists each Display preference toggle via its own PATCH call", async () => {
    vi.mocked(api.updateInstructorMe).mockResolvedValue({
      ...FULL_ME_RESPONSE,
      larger_text: true,
    });
    const user = userEvent.setup();
    render(<InstructorSettingsFlow />);

    const toggle = await screen.findByText("Larger text");
    const checkbox = toggle.closest("label")!.querySelector("input")!;
    await user.click(checkbox);

    expect(api.updateInstructorMe).toHaveBeenCalledWith({ larger_text: true });
    await waitFor(() => expect(checkbox).toBeChecked());
  });

  it("saves classroom defaults (enrollment mode + due date offset)", async () => {
    vi.mocked(api.updateInstructorMe).mockResolvedValue({
      ...FULL_ME_RESPONSE,
      default_enrollment_mode: "closed",
      default_due_date_offset_days: 7,
    });
    const user = userEvent.setup();
    render(<InstructorSettingsFlow />);

    await screen.findByDisplayValue("teacher@example.com");
    const classroomSection = screen
      .getByRole("heading", { name: "Classroom defaults" })
      .closest("section")!;
    await user.click(within(classroomSection).getByRole("radio", { name: "Closed" }));
    await user.type(within(classroomSection).getByLabelText(/Due after/), "7");
    await user.click(within(classroomSection).getByRole("button", { name: "Save changes" }));

    expect(api.updateInstructorMe).toHaveBeenCalledWith({
      default_enrollment_mode: "closed",
      default_due_date_offset_days: 7,
    });
    expect(await within(classroomSection).findByText("Saved.")).toBeInTheDocument();
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
    render(<InstructorSettingsFlow />);

    await screen.findByRole("option", { name: "Leo · algebra-1" });
    await user.selectOptions(screen.getByDisplayValue("Choose a learner"), "learner-1");
    await user.click(screen.getByRole("button", { name: "Request deletion" }));

    expect(api.submitDeletionRequest).toHaveBeenCalledWith("learner", "learner-1");
    expect(await screen.findByText(/Status: pending/)).toBeInTheDocument();
  });

  it("submits an instructor account-deletion request targeting the instructor's own id", async () => {
    vi.mocked(api.submitDeletionRequest).mockResolvedValue({
      deletion_request_id: "del-2",
      target_type: "instructor",
      target_id: "instructor-1",
      status: "pending",
      requested_at: "2026-10-06T00:00:00Z",
    });
    const user = userEvent.setup();
    render(<InstructorSettingsFlow />);

    await screen.findByDisplayValue("teacher@example.com");
    await user.click(screen.getByRole("button", { name: "Request account deletion" }));

    expect(api.submitDeletionRequest).toHaveBeenCalledWith("instructor", "instructor-1");
    expect(await screen.findByText(/Status: pending/)).toBeInTheDocument();
  });

  it("shows the demo-account view with password-change/account-deletion disabled", async () => {
    vi.mocked(api.getWhoAmI).mockReset().mockResolvedValue(DEMO_WHOAMI);
    render(<InstructorSettingsFlow />);

    expect(await screen.findByTestId("settings-demo-notice")).toBeInTheDocument();
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Change password" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request account deletion" })).toBeDisabled();
    expect(screen.getByDisplayValue("Choose a learner")).toBeDisabled();
  });
});

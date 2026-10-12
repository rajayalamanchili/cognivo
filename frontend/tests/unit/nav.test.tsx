// Unit test: Nav's per-visitor-type menu (anonymous/demo-learner/
// guardian/instructor buckets) and the "signed in as" identity readout
// for real guardian/instructor sessions. The Personalization Evidence
// link (spec 006 SC-005) is temporarily hidden from nav everywhere, at
// the user's request -- see Nav.tsx's comment for how to re-add it.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Nav from "@/components/Nav";
import LeaveGuardDialog from "@/components/LeaveGuardDialog";
import * as api from "@/services/api";
import { enterRealLearnerSession, onSessionChanged } from "@/lib/visitor-state";
import { clearGuard, setGuard } from "@/lib/leave-guard";

// spec 044 FR-028 (US6): `LeaveGuardDialog` is mounted once near the app
// root (`app/layout.tsx`), not inside Nav itself -- rendered alongside
// it here to match that composition for the leave-guard tests below.
function renderNav() {
  return render(
    <>
      <Nav />
      <LeaveGuardDialog />
    </>,
  );
}

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/",
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    getWhoAmI: vi.fn(),
    logout: vi.fn(),
    getDemoLearner: vi.fn(),
  };
});

const DEMO_LEARNER_MODE_KEY = "cognivo:demo-learner-mode";
const REAL_LEARNER_SESSION_KEY = "cognivo:real-learner-session";

describe("Nav", () => {
  beforeEach(() => {
    push.mockReset();
    vi.mocked(api.getWhoAmI).mockReset();
    vi.mocked(api.logout).mockReset();
    vi.mocked(api.getDemoLearner).mockReset();
    vi.mocked(api.getDemoLearner).mockResolvedValue({
      learner_id: "learner-1",
      display_name: "Demo Learner",
    });
    window.localStorage.removeItem(DEMO_LEARNER_MODE_KEY);
    window.localStorage.removeItem(REAL_LEARNER_SESSION_KEY);
    clearGuard();
  });

  it.each([
    ["logged out", { account_type: null, identifier: null, pending_deletion_warnings: [] }, "/"],
    ["demo_instructor (still a demo account)", { account_type: "demo_instructor" as const, identifier: "Demo Instructor", pending_deletion_warnings: [] }, "/"],
    ["a real guardian", { account_type: "guardian" as const, identifier: "parent@example.com", pending_deletion_warnings: [] }, "/guardian/learners"],
    ["a real instructor", { account_type: "instructor" as const, identifier: "teacher@example.com", pending_deletion_warnings: [] }, "/instructor/dashboard"],
  ])("the Cognivo logo links home appropriately for %s", async (_label, whoAmI, expectedHref) => {
    vi.mocked(api.getWhoAmI).mockResolvedValue(whoAmI);
    render(<Nav />);

    const logo = await screen.findByTestId("nav-logo");
    await waitFor(() => expect(logo).toHaveAttribute("href", expectedHref));
  });

  it("shows only Try Demo and Sign In when logged out", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: null,
      identifier: null,
      pending_deletion_warnings: [],
    });
    render(<Nav />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(await screen.findByText("Try Demo")).toBeInTheDocument();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
    expect(screen.queryByText("Personalization Evidence")).not.toBeInTheDocument();

    expect(screen.queryByText("My Learners")).not.toBeInTheDocument();
    expect(screen.queryByText("Rosters")).not.toBeInTheDocument();
    expect(screen.queryByText("Placement")).not.toBeInTheDocument();
  });

  it("shows the demo-learner bucket when demo-learner mode is set, with no real session", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: null,
      identifier: null,
      pending_deletion_warnings: [],
    });
    window.localStorage.setItem(DEMO_LEARNER_MODE_KEY, "true");
    render(<Nav />);

    await waitFor(() => expect(api.getWhoAmI).toHaveBeenCalled());
    expect(await screen.findByText("Placement")).toBeInTheDocument();
    expect(screen.getByText("Practice")).toBeInTheDocument();
    expect(screen.getByText("Mastery")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Try Demo")).not.toBeInTheDocument();

    // Exit Demo/Sign In are tucked behind the avatar/name menu now, not
    // shown inline (user feedback). Personalization Evidence is hidden
    // from nav entirely for now (not just tucked away) -- see Nav.tsx.
    expect(screen.queryByText("Exit Demo")).not.toBeInTheDocument();
    expect(screen.queryByText("Personalization Evidence")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Demo Learner (demo)"));
    expect(screen.getByText("Exit Demo")).toBeInTheDocument();
    expect(screen.queryByText("Personalization Evidence")).not.toBeInTheDocument();
  });

  it("shows an avatar and the demo learner's real name in the demo-learner bucket, with Sign In behind that same menu (027-learner-ui-redesign gap-closing pass)", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: null,
      identifier: null,
      pending_deletion_warnings: [],
    });
    vi.mocked(api.getDemoLearner).mockResolvedValue({
      learner_id: "learner-1",
      display_name: "Sam",
    });
    window.localStorage.setItem(DEMO_LEARNER_MODE_KEY, "true");
    render(<Nav />);

    const trigger = await screen.findByText("Sam (demo)");
    expect(screen.queryByText("Sign In")).not.toBeInTheDocument();

    fireEvent.click(trigger);
    expect(screen.getByText("Sign In")).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    expect(screen.queryByText("Sign In")).not.toBeInTheDocument();
  });

  it("exiting demo mode clears the flag and navigates home", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: null,
      identifier: null,
      pending_deletion_warnings: [],
    });
    window.localStorage.setItem(DEMO_LEARNER_MODE_KEY, "true");
    render(<Nav />);

    fireEvent.click(await screen.findByText("Demo Learner (demo)"));
    fireEvent.click(screen.getByText("Exit Demo"));

    expect(window.localStorage.getItem(DEMO_LEARNER_MODE_KEY)).toBeNull();
    expect(push).toHaveBeenCalledWith("/");
  });

  it("shows the guardian bucket with an identity readout for a guardian session", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    render(<Nav />);

    expect(await screen.findByText("My Learners")).toBeInTheDocument();
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
    expect(screen.getByTestId("nav-identity")).toHaveTextContent("parent@example.com · Guardian");
    expect(screen.queryByText("Try Demo")).not.toBeInTheDocument();
    expect(screen.queryByText("Rosters")).not.toBeInTheDocument();
  });

  it("shows the instructor bucket with an identity readout for a real instructor session", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "instructor",
      identifier: "teacher@example.com",
      pending_deletion_warnings: [],
    });
    render(<Nav />);

    expect(await screen.findByText("Rosters")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
    expect(screen.getByTestId("nav-identity")).toHaveTextContent(
      "teacher@example.com · Instructor",
    );
  });

  it("shows the instructor bucket with no identity readout for a demo instructor session", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "demo_instructor",
      identifier: "Demo Instructor",
      pending_deletion_warnings: [],
    });
    render(<Nav />);

    expect(await screen.findByText("Rosters")).toBeInTheDocument();
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
    expect(screen.queryByTestId("nav-identity")).not.toBeInTheDocument();
  });

  it("signing out logs out, clears the identity readout, and navigates home", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    vi.mocked(api.logout).mockResolvedValue(undefined);
    render(<Nav />);

    await screen.findByTestId("nav-identity");
    fireEvent.click(screen.getByText("Sign Out"));

    await waitFor(() => expect(api.logout).toHaveBeenCalled());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });

  it("signing out notifies other mounted components the session changed (regression: DemoBadge stayed stuck showing a demo_instructor's badge after sign-out, since nothing told it to refetch)", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "demo_instructor",
      identifier: "Demo Instructor",
      pending_deletion_warnings: [],
    });
    vi.mocked(api.logout).mockResolvedValue(undefined);
    render(<Nav />);

    await screen.findByText("Sign Out");
    const sessionChanged = vi.fn();
    const unsubscribe = onSessionChanged(sessionChanged);

    fireEvent.click(screen.getByText("Sign Out"));

    await waitFor(() => expect(sessionChanged).toHaveBeenCalled());
    unsubscribe();
  });

  it("shows the real-learner bucket (Dashboard/Practice/Mastery/AI Tutor, no Placement) with the real learner's identity and an Exit learner view action, for a guardian with an active real-learner session (spec 041 FR-016/FR-022)", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    enterRealLearnerSession("learner-1", "Eli");
    render(<Nav />);

    expect(await screen.findByTestId("nav-real-learner-identity")).toHaveTextContent("Eli (learner)");
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Practice")).toBeInTheDocument();
    expect(screen.getByText("Mastery")).toBeInTheDocument();
    expect(screen.getByText("AI Tutor")).toBeInTheDocument();
    expect(screen.queryByText("Placement")).not.toBeInTheDocument();
    expect(screen.queryByText("My Learners")).not.toBeInTheDocument();
    expect(screen.getByText("Exit learner view")).toBeInTheDocument();
    expect(screen.getByTestId("real-learner-session-banner")).toHaveTextContent(
      "You’re viewing Eli’s learning on your guardian account.",
    );
    expect(screen.getByText("End session, back to my learners")).toBeInTheDocument();
  });

  it("the banner's End session action clears the real-learner session and navigates to Guardian · My learners", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    enterRealLearnerSession("learner-1", "Eli");
    render(<Nav />);

    fireEvent.click(await screen.findByText("End session, back to my learners"));

    expect(window.localStorage.getItem(REAL_LEARNER_SESSION_KEY)).toBeNull();
    expect(push).toHaveBeenCalledWith("/guardian/learners");
  });

  it("Exit learner view clears the real-learner session and navigates to Guardian · My learners", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    enterRealLearnerSession("learner-1", "Eli");
    render(<Nav />);

    fireEvent.click(await screen.findByText("Exit learner view"));

    expect(window.localStorage.getItem(REAL_LEARNER_SESSION_KEY)).toBeNull();
    expect(push).toHaveBeenCalledWith("/guardian/learners");
  });

  it("signing out while a real-learner session is active clears that session too, not just accountType/identifier (FR-022)", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    vi.mocked(api.logout).mockResolvedValue(undefined);
    enterRealLearnerSession("learner-1", "Eli");
    render(<Nav />);

    await screen.findByTestId("nav-real-learner-identity");
    fireEvent.click(screen.getByText("Sign Out"));

    await waitFor(() => expect(api.logout).toHaveBeenCalled());
    expect(window.localStorage.getItem(REAL_LEARNER_SESSION_KEY)).toBeNull();
  });

  it("spec 044 FR-028/FR-030 (US6): a nav link click shows the leave-guard confirmation when a guard is active, and proceeds only on confirm", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    enterRealLearnerSession("learner-1", "Eli");
    renderNav();
    await screen.findByText("Dashboard");

    setGuard("careful");
    fireEvent.click(screen.getByText("Dashboard"));
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByTestId("leave-guard-dialog")).toHaveTextContent("careful");

    fireEvent.click(screen.getByText("Stay here"));
    expect(push).not.toHaveBeenCalled();
    expect(screen.queryByTestId("leave-guard-dialog")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Dashboard"));
    fireEvent.click(screen.getByText("Leave"));
    expect(push).toHaveBeenCalledWith("/dashboard");
  });

  it("spec 044 FR-028/FR-030 (US6): a nav link click navigates immediately with no guard active", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    enterRealLearnerSession("learner-1", "Eli");
    renderNav();

    fireEvent.click(await screen.findByText("Dashboard"));
    expect(push).toHaveBeenCalledWith("/dashboard");
    expect(screen.queryByTestId("leave-guard-dialog")).not.toBeInTheDocument();
  });

  it("spec 044 FR-028 (US6): Exit learner view and End session both show the confirmation when a guard is active", async () => {
    vi.mocked(api.getWhoAmI).mockResolvedValue({
      account_type: "guardian",
      identifier: "parent@example.com",
      pending_deletion_warnings: [],
    });
    enterRealLearnerSession("learner-1", "Eli");
    renderNav();
    await screen.findByText("Exit learner view");

    setGuard("careful");
    fireEvent.click(screen.getByText("End session, back to my learners"));
    expect(push).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("Leave"));
    expect(push).toHaveBeenCalledWith("/guardian/learners");
  });
});

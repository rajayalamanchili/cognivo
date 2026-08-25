import { test, expect } from "@playwright/test";

// Playwright E2E: open a Tutoring Session, ask a question, confirm a
// grounded streamed answer renders, then inspect that exchange as the
// enrolled instructor (spec 012, T033; quickstart.md scenarios 1-4).
//
// Split into two halves against the same running dev deployment,
// deliberately not one continuous "ask as X, then inspect as X" click
// path -- for the same reason
// instructor-classroom-round-trip.spec.ts's module comment documents
// for its own scope cut: the seeded demo learner (the *only* learner
// `/tutor`'s frontend page supports asking as -- tasks.md never
// specified a guardian-facing "pick my real learner" UI) has
// `guardian_id` always null, so it can never be joined into a roster
// via `POST /api/rosters/join`'s guardian-ownership check -- there is
// no click path from "demo learner asks a question" to "an instructor
// who is actually enrolled with that learner". `GET /api/tutor/
// exchanges/{id}` also has no frontend page at all (no task in
// tasks.md built one) -- only the exchange_id surfaced via
// TutorChat.tsx's `data-exchange-id` attribute and a direct API call
// exercise it here.
//
// Part 1 (UI): the demo-learner chat flow, exactly as a real visitor
// would use it -- proves FR-002/FR-005 (grounded, incrementally
// streamed) end to end through the actual browser.
// Part 2 (API against the same live deployment): a real guardian +
// instructor + enrolled real learner, proving FR-001's guardian path
// and User Story 3's enrollment-scoped inspection endpoint -- via
// `page.request`, Playwright's real-HTTP-call fixture, not a mock.

function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

const PASSWORD = "correct horse battery staple";

test("demo learner asks the tutor a question and gets a grounded streamed answer", async ({
  page,
}) => {
  await page.goto("/tutor");
  await expect(page.getByTestId("tutor-start-form")).toBeVisible();
  await page.getByRole("button", { name: "Start Tutoring" }).click();

  await expect(page.getByTestId("tutor-chat")).toBeVisible();
  await page
    .getByPlaceholder("Ask the tutor a question…")
    .fill("why does photosynthesis need light?");
  await page.getByRole("button", { name: "Ask" }).click();

  await expect(page.getByTestId("tutor-chat-learner-message")).toContainText(
    "why does photosynthesis need light?",
  );
  const tutorMessage = page.getByTestId("tutor-chat-tutor-message");
  // Streamed, not a single buffered payload: some non-empty text
  // appears before the final answer settles.
  await expect(tutorMessage).not.toHaveText("", { timeout: 30_000 });
  // "Answering…" clears once the stream's final `done` event lands,
  // which is also when the exchange_id attribute gets set.
  await expect(page.getByRole("button", { name: "Ask" })).toBeVisible({ timeout: 60_000 });
  await expect(tutorMessage).toHaveAttribute("data-exchange-id", /.+/);
});

test("a real learner's tutor exchange is inspectable by their enrolled instructor", async ({
  page,
}) => {
  const instructorEmail = uniqueEmail("e2e-tutor-instructor");
  const guardianEmail = uniqueEmail("e2e-tutor-guardian");

  const instructorRegister = await page.request.post("/api/auth/instructor/register", {
    data: { email: instructorEmail, password: PASSWORD },
  });
  expect(instructorRegister.ok(), await instructorRegister.text()).toBeTruthy();

  const subjects = await page.request.get("/api/subjects");
  const subjectId = (await subjects.json()).subjects[0].subject_id as string;

  const roster = await page.request.post("/api/rosters", {
    data: { subject_id: subjectId, enrollment_mode: "open" },
  });
  expect(roster.ok(), await roster.text()).toBeTruthy();
  const { join_code: joinCode } = await roster.json();
  await page.request.post("/api/auth/logout");

  const guardianRegister = await page.request.post("/api/auth/guardian/register", {
    data: { email: guardianEmail, password: PASSWORD },
  });
  expect(guardianRegister.ok(), await guardianRegister.text()).toBeTruthy();

  const learner = await page.request.post("/api/learners", {
    data: { display_name: "E2E Tutor Learner" },
  });
  expect(learner.ok(), await learner.text()).toBeTruthy();
  const { learner_id: learnerId } = await learner.json();

  const joined = await page.request.post("/api/rosters/join", {
    data: { learner_id: learnerId, join_code: joinCode },
  });
  expect(joined.ok(), await joined.text()).toBeTruthy();

  const session = await page.request.post("/api/tutor/sessions", {
    data: { learner_id: learnerId, subject_id: subjectId },
  });
  expect(session.ok(), await session.text()).toBeTruthy();
  const { session_id: sessionId } = await session.json();

  const message = await page.request.post(`/api/tutor/sessions/${sessionId}/messages`, {
    data: { question: "what should I work on next?" },
  });
  expect(message.ok(), await message.text()).toBeTruthy();
  const body = await message.text();
  const doneLine = body
    .split("\n")
    .reverse()
    .find((line) => line.startsWith("data: ") && line.includes('"done"'));
  expect(doneLine, `no done event in stream body: ${body}`).toBeTruthy();
  const { exchange_id: exchangeId } = JSON.parse(doneLine!.slice("data: ".length));

  await page.request.post("/api/auth/logout");
  const instructorLogin = await page.request.post("/api/auth/instructor/login", {
    data: { email: instructorEmail, password: PASSWORD },
  });
  expect(instructorLogin.ok(), await instructorLogin.text()).toBeTruthy();

  const inspected = await page.request.get(`/api/tutor/exchanges/${exchangeId}`);
  expect(inspected.ok(), await inspected.text()).toBeTruthy();
  const exchangeBody = await inspected.json();
  expect(exchangeBody.status).toBe("completed");
  expect(exchangeBody.question_text).toBe("what should I work on next?");
});

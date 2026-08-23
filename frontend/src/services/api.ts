// API client for the FastAPI backend (contracts/api.md). Relative paths
// only -- `/api/*` requests are same-origin in production and proxied to
// the local backend in dev (see next.config.ts).

export type QuestionType = "multiple_choice" | "numeric" | "free_text";
export type Difficulty = "easy" | "medium" | "hard";
export type MasteryBand = "struggling" | "developing" | "mastered";
export type MasteryStatus = "unknown" | "scored";

export interface PlacementQuestion {
  question_id: string;
  topic_id: string;
  difficulty: Difficulty;
  question_type: QuestionType;
  stem: string;
  options: string[] | null;
}

export interface PlacementStartResponse {
  placement_session_id: string;
  questions: PlacementQuestion[];
}

export interface PlacementAnswer {
  question_id: string;
  response: string | number;
}

export interface MasteryStateEntry {
  topic_id: string;
  status: MasteryStatus;
  p_mastery: number | null;
  band: MasteryBand | null;
}

export interface PlacementSubmitResponse {
  mastery_state: MasteryStateEntry[];
}

export interface MasteryTopicEntry extends MasteryStateEntry {
  last_updated_at: string | null;
}

export interface MasteryStateResponse {
  topics: MasteryTopicEntry[];
}

export interface DemoLearner {
  learner_id: string;
  display_name: string;
}

export interface SubjectSummary {
  subject_id: string;
  display_name: string;
}

export interface SubjectsResponse {
  subjects: SubjectSummary[];
}

export type DataSufficiency = "confident" | "insufficient_data";

export interface EvidenceCitation {
  event_id: string;
  question_id: string;
  question_stem: string;
  answer_correct: boolean;
  prior_p_mastery: number | null;
  posterior_p_mastery: number;
  created_at: string;
}

export interface NextStepSuggestion {
  recommended_topic_id: string;
  recommended_display_name: string;
  reason: string;
  prerequisite_chain: string[];
}

export interface WeakAreaFlag {
  topic_id: string;
  display_name: string;
  p_mastery: number;
  evidence: EvidenceCitation[];
  next_step: NextStepSuggestion;
}

export interface RecommendationsResponse {
  subject_id: string;
  data_sufficiency: DataSufficiency;
  broad_review_needed: boolean;
  weak_areas: WeakAreaFlag[];
  in_progress_topic_ids: string[];
  not_yet_assessed_topic_ids: string[];
  insufficient_data_topic_ids: string[];
}

export interface TopicPreviewEntry {
  topic_id: string;
  display_name: string;
  band: MasteryBand | "unknown";
  p_mastery: number | null;
}

export interface TopicPriorityPreview {
  subject_id: string;
  next_topic: TopicPreviewEntry;
  upcoming_topics: TopicPreviewEntry[];
  is_fallback: boolean;
}

export interface NextQuestion {
  question_id: string;
  topic_id: string;
  difficulty: Difficulty;
  question_type: QuestionType;
  stem: string;
  options: string[] | null;
}

export interface AnswerResult {
  correct: boolean;
  topic_id: string;
  prior_p_mastery: number | null;
  posterior_p_mastery: number;
  band: MasteryBand;
  graduated_score: number | null;
  criteria_met: string[] | null;
  criteria_missed: string[] | null;
  grading_logic_version: string | null;
}

export interface FlagResult {
  question_id: string;
  validation_status: string;
}

export type QuizStatus = "in_progress" | "completed" | "ended_early";

export interface StartQuizResponse {
  quiz_session_id: string;
  status: QuizStatus;
  question: NextQuestion | null;
}

export interface QuizNextQuestionResponse {
  status: QuizStatus;
  question: NextQuestion | null;
}

export interface QuizScore {
  correct: number;
  total: number;
}

export interface QuizSummaryEntry {
  topic_id: string;
  difficulty: Difficulty;
  correct: number;
  total: number;
}

export interface QuizSummaryResponse {
  quiz_session_id: string;
  subject_id: string;
  topic_ids: string[];
  question_count: number;
  status: QuizStatus;
  started_at: string;
  completed_at: string | null;
  score: QuizScore;
  summary: QuizSummaryEntry[];
}

// Free-text's four distinct rejection responses (contracts/api.md) --
// `ApiError.body` carries the parsed shape so callers can distinguish
// them without re-parsing `message`.
export interface AnswerTooLongBody {
  error: "answer_too_long";
  max_length: number;
}

export interface RateLimitedBody {
  error: "rate_limited";
  retry_after_seconds: number;
}

export interface ModerationRejectedBody {
  error: "moderation_rejected";
}

export interface GradingUnavailableBody {
  error: "grading_unavailable";
}

export type FreeTextErrorBody =
  AnswerTooLongBody | RateLimitedBody | ModerationRejectedBody | GradingUnavailableBody;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchOrThrow(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const text = await response.text();
    let body: unknown;
    try {
      body = JSON.parse(text);
    } catch {
      body = undefined;
    }
    throw new ApiError(response.status, `${path} failed (${response.status}): ${text}`, body);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchOrThrow(path, init);
  return (await response.json()) as T;
}

// For endpoints with no response body (e.g. logout's 204) -- `request`
// always calls `response.json()`, which throws on an empty body.
async function requestVoid(path: string, init?: RequestInit): Promise<void> {
  await fetchOrThrow(path, init);
}

export function getDemoLearner(): Promise<DemoLearner> {
  return request<DemoLearner>("/api/demo-learner");
}

export function startPlacement(subjectId: string): Promise<PlacementStartResponse> {
  return request<PlacementStartResponse>(`/api/subjects/${subjectId}/placement/start`, {
    method: "POST",
  });
}

export function submitPlacement(
  placementSessionId: string,
  answers: PlacementAnswer[],
): Promise<PlacementSubmitResponse> {
  return request<PlacementSubmitResponse>(`/api/placement/${placementSessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export function getSubjects(): Promise<SubjectsResponse> {
  return request<SubjectsResponse>("/api/subjects");
}

export function getMasteryState(
  learnerId: string,
  subjectId: string,
): Promise<MasteryStateResponse> {
  return request<MasteryStateResponse>(
    `/api/learners/${learnerId}/mastery-state?subject_id=${encodeURIComponent(subjectId)}`,
  );
}

export function getRecommendations(
  learnerId: string,
  subjectId: string,
): Promise<RecommendationsResponse> {
  return request<RecommendationsResponse>(
    `/api/learners/${learnerId}/recommendations?subject_id=${encodeURIComponent(subjectId)}`,
  );
}

export function getTopicPriorityPreview(
  learnerId: string,
  subjectId: string,
): Promise<TopicPriorityPreview> {
  return request<TopicPriorityPreview>(
    `/api/learners/${learnerId}/topic-priority-preview?subject_id=${encodeURIComponent(subjectId)}`,
  );
}

export function getNextQuestion(learnerId: string, subjectId: string): Promise<NextQuestion> {
  return request<NextQuestion>(
    `/api/learners/${learnerId}/next-question?subject_id=${encodeURIComponent(subjectId)}`,
  );
}

export function answerQuestion(
  questionId: string,
  response: string | number,
): Promise<AnswerResult> {
  return request<AnswerResult>(`/api/questions/${questionId}/answer`, {
    method: "POST",
    body: JSON.stringify({ response }),
  });
}

export function startQuiz(topicIds: string[], questionCount: number): Promise<StartQuizResponse> {
  return request<StartQuizResponse>("/api/quizzes", {
    method: "POST",
    body: JSON.stringify({ topic_ids: topicIds, question_count: questionCount }),
  });
}

export function getQuizNextQuestion(quizSessionId: string): Promise<QuizNextQuestionResponse> {
  return request<QuizNextQuestionResponse>(`/api/quizzes/${quizSessionId}/next-question`);
}

export function getQuizSummary(quizSessionId: string): Promise<QuizSummaryResponse> {
  return request<QuizSummaryResponse>(`/api/quizzes/${quizSessionId}`);
}

export function flagQuestion(
  questionId: string,
  flaggedBy: string,
  reason: string,
): Promise<FlagResult> {
  return request<FlagResult>(`/api/questions/${questionId}/flag`, {
    method: "POST",
    body: JSON.stringify({ flagged_by: flaggedBy, reason }),
  });
}

export interface ConditionStats {
  // Omitted from the wire response (not `null`) when zero learners
  // converged for this condition -- never a fabricated 0.0.
  mean?: number;
  median?: number;
  non_converged_count: number;
  non_converged_rate: number;
  n: number;
}

export interface EvaluationBreakdown {
  profile: string;
  subject_id: string;
  conditions: Record<string, ConditionStats>;
}

export interface EvaluationReport {
  published: boolean;
  run_timestamp?: string;
  seed?: number;
  profiles?: string[];
  subjects?: string[];
  population_size_per_profile?: number;
  max_questions_per_topic_budget?: number;
  breakdowns?: EvaluationBreakdown[];
  aggregate?: Record<string, ConditionStats>;
}

export function getEvaluationReport(): Promise<EvaluationReport> {
  return request<EvaluationReport>("/api/evaluation/report");
}

// Auth (spec 010 contracts/api.md "Auth" section). Session is a
// stateless JWT in an httpOnly cookie set by the backend's Set-Cookie
// response header -- these calls never read/write the token directly.

export interface GuardianAuthResponse {
  guardian_id: string;
}

export interface InstructorAuthResponse {
  instructor_id: string;
}

// `AuthErrorBody.detail` distinguishes register/login failures (e.g.
// "email_taken", "invalid_credentials") without re-parsing `message`,
// same pattern as `FreeTextErrorBody` above.
export interface AuthErrorBody {
  detail: string;
}

export function registerGuardian(email: string, password: string): Promise<GuardianAuthResponse> {
  return request<GuardianAuthResponse>("/api/auth/guardian/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function loginGuardian(email: string, password: string): Promise<GuardianAuthResponse> {
  return request<GuardianAuthResponse>("/api/auth/guardian/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function registerInstructor(
  email: string,
  password: string,
): Promise<InstructorAuthResponse> {
  return request<InstructorAuthResponse>("/api/auth/instructor/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function loginInstructor(email: string, password: string): Promise<InstructorAuthResponse> {
  return request<InstructorAuthResponse>("/api/auth/instructor/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<void> {
  return requestVoid("/api/auth/logout", { method: "POST" });
}

export type SessionAccountType = "guardian" | "instructor" | "demo_instructor";

export interface WhoAmIResponse {
  account_type: SessionAccountType | null;
}

// Read-only session-identity check -- drives the nav's per-user-type
// menu. Never itself an authorization decision (every route still
// gates on its own current_guardian/current_instructor dependency).
export function getWhoAmI(): Promise<WhoAmIResponse> {
  return request<WhoAmIResponse>("/api/auth/whoami");
}

export interface CreateLearnerResponse {
  learner_id: string;
  guardian_id: string;
}

export function createLearner(displayName: string): Promise<CreateLearnerResponse> {
  return request<CreateLearnerResponse>("/api/learners", {
    method: "POST",
    body: JSON.stringify({ display_name: displayName }),
  });
}

// Rosters (spec 010 contracts/api.md "Rosters" section, User Story 2).

export type EnrollmentMode = "open" | "closed";

export interface Roster {
  roster_id: string;
  subject_id: string;
  enrollment_mode: EnrollmentMode;
  join_code: string | null;
}

export interface RosterSummary {
  roster_id: string;
  subject_id: string;
  enrollment_mode: EnrollmentMode;
}

export interface ListRostersResponse {
  rosters: RosterSummary[];
}

export function createRoster(subjectId: string, enrollmentMode: EnrollmentMode): Promise<Roster> {
  return request<Roster>("/api/rosters", {
    method: "POST",
    body: JSON.stringify({ subject_id: subjectId, enrollment_mode: enrollmentMode }),
  });
}

export function updateRosterEnrollmentMode(
  rosterId: string,
  enrollmentMode: EnrollmentMode,
): Promise<Roster> {
  return request<Roster>(`/api/rosters/${rosterId}`, {
    method: "PATCH",
    body: JSON.stringify({ enrollment_mode: enrollmentMode }),
  });
}

export function listRosters(): Promise<ListRostersResponse> {
  return request<ListRostersResponse>("/api/rosters");
}

export type JoinRosterResponse =
  | { status: "enrolled"; enrollment_id: string }
  | { status: "pending"; enrollment_request_id: string };

export function joinRoster(learnerId: string, joinCode: string): Promise<JoinRosterResponse> {
  return request<JoinRosterResponse>("/api/rosters/join", {
    method: "POST",
    body: JSON.stringify({ learner_id: learnerId, join_code: joinCode }),
  });
}

export interface EnrollmentRequestEntry {
  enrollment_request_id: string;
  learner_id: string;
  requested_at: string;
}

export interface ListRequestsResponse {
  requests: EnrollmentRequestEntry[];
}

export function listRosterRequests(rosterId: string): Promise<ListRequestsResponse> {
  return request<ListRequestsResponse>(`/api/rosters/${rosterId}/requests`);
}

export function approveRosterRequest(
  rosterId: string,
  enrollmentRequestId: string,
): Promise<{ status: "approved"; enrollment_id: string }> {
  return request(`/api/rosters/${rosterId}/requests/${enrollmentRequestId}/approve`, {
    method: "POST",
  });
}

export function declineRosterRequest(
  rosterId: string,
  enrollmentRequestId: string,
): Promise<{ status: "declined" }> {
  return request(`/api/rosters/${rosterId}/requests/${enrollmentRequestId}/decline`, {
    method: "POST",
  });
}

export interface EnrolledLearner {
  learner_id: string;
  display_name: string;
}

export interface ListEnrollmentsResponse {
  enrollments: EnrolledLearner[];
}

export function listRosterEnrollments(rosterId: string): Promise<ListEnrollmentsResponse> {
  return request<ListEnrollmentsResponse>(`/api/rosters/${rosterId}/enrollments`);
}

export function unenrollLearner(rosterId: string, learnerId: string): Promise<void> {
  return requestVoid(`/api/rosters/${rosterId}/enrollments/${learnerId}`, { method: "DELETE" });
}

// Dashboard (spec 010 contracts/api.md "Dashboard" section, User Story 3).
// Each `learners[].recommendations` entry is byte-for-byte what
// `getRecommendations` returns for that learner directly (SC-001) --
// reuses the same `RecommendationsResponse` type for that reason.

export interface DashboardLearnerEntry {
  learner_id: string;
  display_name: string;
  recommendations: RecommendationsResponse;
}

export interface DashboardResponse {
  roster_id: string;
  subject_id: string;
  learners: DashboardLearnerEntry[];
}

export function getRosterDashboard(rosterId: string): Promise<DashboardResponse> {
  return request<DashboardResponse>(`/api/rosters/${rosterId}/dashboard`);
}

// Content review (spec 010 contracts/api.md "Content review" section,
// User Story 4).

export interface FlaggedQuestion {
  question_id: string;
  learner_id: string;
  roster_id: string;
  stem: string;
  flagged_reason: string | null;
  flagged_at: string;
}

export interface ListFlaggedResponse {
  flagged: FlaggedQuestion[];
}

export function listFlaggedQuestions(): Promise<ListFlaggedResponse> {
  return request<ListFlaggedResponse>("/api/content-review/flagged");
}

export type ResolutionAction = "reactivate" | "reject";

export interface ResolveResponse {
  question_id: string;
  validation_status: string;
}

export function resolveFlaggedQuestion(
  questionId: string,
  action: ResolutionAction,
): Promise<ResolveResponse> {
  return request<ResolveResponse>(`/api/content-review/${questionId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
}

// Demo entry points (spec 010 contracts/api.md "Demo entry points"
// section). Unlike `getDemoLearner`, this also issues a session cookie
// (`/speckit-clarify` with the user) -- calling it signs the browser in
// as the seeded demo instructor, so the instructor pages become
// browsable immediately afterward.

export interface DemoInstructor {
  instructor_id: string;
  display_name: string;
}

export function getDemoInstructor(): Promise<DemoInstructor> {
  return request<DemoInstructor>("/api/demo-instructor");
}

// Instructor-assigned quizzes (spec 011 contracts/api.md "Assignments"
// section, User Story 1).

export interface QuizAssignment {
  assignment_id: string;
  roster_id: string;
  subject_id: string;
  topic_ids: string[];
  question_count: number;
  due_at: string | null;
  target_learner_ids: string[];
}

export interface QuizAssignmentSummary {
  assignment_id: string;
  topic_ids: string[];
  question_count: number;
  due_at: string | null;
  cancelled_at: string | null;
  created_at: string;
}

export interface ListAssignmentsResponse {
  assignments: QuizAssignmentSummary[];
}

export function createAssignment(
  rosterId: string,
  params: {
    topicIds: string[];
    questionCount: number;
    dueAt: string | null;
    learnerIds: string[] | "all";
  },
): Promise<QuizAssignment> {
  return request<QuizAssignment>(`/api/rosters/${rosterId}/assignments`, {
    method: "POST",
    body: JSON.stringify({
      topic_ids: params.topicIds,
      question_count: params.questionCount,
      due_at: params.dueAt,
      learner_ids: params.learnerIds,
    }),
  });
}

export function listRosterAssignments(rosterId: string): Promise<ListAssignmentsResponse> {
  return request<ListAssignmentsResponse>(`/api/rosters/${rosterId}/assignments`);
}

export function cancelAssignment(rosterId: string, assignmentId: string): Promise<void> {
  return requestVoid(`/api/rosters/${rosterId}/assignments/${assignmentId}`, {
    method: "DELETE",
  });
}

// Instructor-assigned quizzes (guardian-facing, User Story 2).

export type AssignmentStatus = "not_started" | "in_progress" | "completed" | "ended_early";

export interface LearnerAssignment {
  assignment_id: string;
  topic_ids: string[];
  question_count: number;
  due_at: string | null;
  cancelled_at: string | null;
  status: AssignmentStatus;
}

export interface ListLearnerAssignmentsResponse {
  assignments: LearnerAssignment[];
}

export function listLearnerAssignments(
  learnerId: string,
): Promise<ListLearnerAssignmentsResponse> {
  return request<ListLearnerAssignmentsResponse>(`/api/learners/${learnerId}/assignments`);
}

// Identical response shape to `startQuiz` (spec 005) -- reuses
// `StartQuizResponse` (contracts/api.md).
export function startAssignment(
  assignmentId: string,
  learnerId: string,
): Promise<StartQuizResponse> {
  return request<StartQuizResponse>(
    `/api/assignments/${assignmentId}/learners/${learnerId}/start`,
    { method: "POST" },
  );
}

// Instructor-facing per-assignment results report (User Story 3).

export interface AssignmentLearnerScore {
  correct: number;
  total: number;
}

export interface AssignmentLearnerReport {
  learner_id: string;
  display_name: string;
  status: AssignmentStatus;
  score: AssignmentLearnerScore | null;
}

export interface AssignmentDetail {
  assignment_id: string;
  topic_ids: string[];
  question_count: number;
  due_at: string | null;
  cancelled_at: string | null;
  learners: AssignmentLearnerReport[];
}

export function getAssignmentDetail(
  rosterId: string,
  assignmentId: string,
): Promise<AssignmentDetail> {
  return request<AssignmentDetail>(`/api/rosters/${rosterId}/assignments/${assignmentId}`);
}

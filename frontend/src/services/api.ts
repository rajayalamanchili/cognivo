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
  | AnswerTooLongBody
  | RateLimitedBody
  | ModerationRejectedBody
  | GradingUnavailableBody;

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
  return (await response.json()) as T;
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

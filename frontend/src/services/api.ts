// API client for the FastAPI backend (contracts/api.md). Relative paths
// only -- `/api/*` requests are same-origin in production and proxied to
// the local backend in dev (see next.config.ts).

export type QuestionType = "multiple_choice" | "numeric";
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

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
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
    const body = await response.text();
    throw new ApiError(response.status, `${path} failed (${response.status}): ${body}`);
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

export function getMasteryState(
  learnerId: string,
  subjectId: string,
): Promise<MasteryStateResponse> {
  return request<MasteryStateResponse>(
    `/api/learners/${learnerId}/mastery-state?subject_id=${encodeURIComponent(subjectId)}`,
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
  mean: number;
  median: number;
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

// Spec 022 FR-001/Assumptions: a small fixed preset (15/30/45/60
// minutes), matching the backend's own allowed values
// (backend/src/services/quiz/session.py's ALLOWED_TIME_LIMIT_SECONDS)
// -- shared here so the quiz and practice pickers can't drift apart.

export interface TimeLimitOption {
  label: string;
  seconds: number | null;
}

export const TIME_LIMIT_OPTIONS: TimeLimitOption[] = [
  { label: "Untimed", seconds: null },
  { label: "15 minutes", seconds: 900 },
  { label: "30 minutes", seconds: 1800 },
  { label: "45 minutes", seconds: 2700 },
  { label: "60 minutes", seconds: 3600 },
];

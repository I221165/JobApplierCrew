// Mirrors the Pydantic models in services/models.py + api/db.py

export interface Job {
  id: string;
  url: string;
  title: string;
  snippet: string;
  role_searched: string;
  location: string;
  created_at: string;

  actual_title: string | null;
  is_active: boolean | null;
  role_match: boolean | null;
  match_score: number | null;
  must_have_json: string | null;
  nice_to_have_json: string | null;
  keywords_json: string | null;
  tone: string | null;
}

export interface JobAnalysis {
  is_active: boolean;
  role_match: boolean;
  actual_title: string;
  match_score: number;
  must_have: string[];
  nice_to_have: string[];
  keywords: string[];
  tone: string;
}

export interface RequirementMatch {
  requirement: string;
  matched: boolean;
  candidate_evidence: string;
  reframe_suggestion: string;
}

export interface GapAnalysis {
  strong_matches: RequirementMatch[];
  weak_matches: RequirementMatch[];
  gaps: string[];
  cv_restructure_order: string[];
}

export type ApplicationStatus =
  | "queued"
  | "gap_analysis"
  | "tailoring"
  | "cover_letter"
  | "latex"
  | "done"
  | "failed";

export interface Application {
  id: string;
  job_id: string;
  status: ApplicationStatus;
  progress_message: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;

  gap_analysis_json: string | null;
  tailored_cv: string | null;
  cover_subject: string | null;
  cover_body: string | null;
  latex_code: string | null;
  pdf_path: string | null;
}

export interface SearchResponse {
  job_ids: string[];
  count: number;
}

export interface ScreenResponse {
  job_id: string;
  analysis: JobAnalysis;
}

export interface ApplyResponse {
  application_id: string;
  status: string;
}

export interface SavedSearch {
  id: string;
  role: string;
  location: string;
  max_jobs: number;
  min_score: number;
  enabled: boolean;
  created_at: string;
  last_run_at: string | null;
  last_run_status: string | null;
}

export interface NotificationWithJob {
  id: string;
  saved_search_id: string;
  job_id: string;
  match_score: number;
  read: boolean;
  created_at: string;
  job: Job | null;
}

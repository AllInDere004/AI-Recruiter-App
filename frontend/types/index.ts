// API contracts mirror backend/app/schemas. Dates arrive as ISO strings.
export interface User { id: number; email: string; is_active: boolean; created_at: string; }
export interface Token { access_token: string; token_type: string; }
export interface ParsedData {
  full_name: string | null; email: string | null; phone: string | null; summary: string | null;
  skills: string[]; experience: Record<string, unknown>[]; education: Record<string, unknown>[];
}
export interface Profile {
  id: number; user_id: number; full_name: string | null; raw_resume_text: string;
  parsed_data: (Partial<ParsedData> & Record<string, unknown>) | null; updated_at: string | null;
}
export interface ProfileUpdate { full_name?: string | null; parsed_data?: Record<string, unknown> | null; }
export interface JobAnalysis { title: string | null; company: string | null; required_skills: string[]; key_responsibilities: string[]; }
export interface JobCreate { title?: string | null; company?: string | null; description: string; }
export interface Job {
  id: number; user_id: number; title: string | null; company: string | null; description: string;
  extracted_skills: Partial<JobAnalysis> | null; created_at: string;
}
export interface MatchResponse { overall_score: number; matched_skills: string[]; missing_skills: string[]; summary: string; }
export interface EmailGenerateRequest { job_id: number; situation: string; tone: string; custom_notes?: string | null; }
export interface EmailGenerateResponse { draft_id: number; subject_line: string; body: string; match_score: number; hallucination_warnings: string[]; }
export type ApplicationStatus = "Draft" | "Sent" | "Replied" | "Interview" | "Rejected";
export interface Draft {
  id: number; user_id: number; job_id: number; situation: string; tone: string;
  subject_line: string | null; body: string; match_score: number | null; status: ApplicationStatus;
  created_at: string; updated_at: string | null;
}
export interface DraftUpdate { subject_line?: string | null; body?: string; situation?: string; tone?: string; status?: ApplicationStatus; }
export interface DraftWithJob extends Draft { job?: Job; }
export type SituationKey = "apply" | "cold_email" | "follow_up" | "thank_you" | "referral" | "reply_recruiter";
export interface SituationOption { key: SituationKey; title: string; description: string; badge: string; iconName: string; }
export type ToneKey = "professional" | "casual" | "confident" | "short";
export interface ToneOption { key: ToneKey; label: string; description: string; example: string; }

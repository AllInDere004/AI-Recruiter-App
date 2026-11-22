// API contracts mirror backend/app/schemas. Dates arrive as ISO strings.
export interface User { id: number; email: string; is_active: boolean; created_at: string; }
export interface Token { access_token: string; token_type: string; }
export interface ParsedData {
  full_name: string | null; email: string | null; phone: string | null; summary: string | null;
  skills: string[]; experience: Record<string, unknown>[]; education: Record<string, unknown>[];
  technical_skills?: string[]; soft_skills?: string[]; certifications?: string[]; achievements?: string[];
  projects?: ResumeProject[]; internships?: ResumeEmployment[]; employment_history?: ResumeEmployment[];
  education_details?: ResumeEducation[]; evidence?: SourceEvidence[]; uncertain_fields?: string[];
}
export interface Profile {
  id: number; user_id: number; full_name: string | null; raw_resume_text: string;
  parsed_data: (Partial<ParsedData> & Record<string, unknown>) | null; updated_at: string | null;
}
export interface ProfileUpdate { full_name?: string | null; parsed_data?: Record<string, unknown> | null; }
export interface JobAnalysis { title: string | null; company: string | null; required_skills: string[]; key_responsibilities: string[];
  location?: string | null; employment_type?: string | null; preferred_skills?: string[] | null;
  experience_requirements?: string[] | null; education_requirements?: string[] | null; other_qualifications?: string[] | null;
  evidence?: { id: string; field: string; value: string; quote: string; status: "verified" | "uncertain" }[];
  uncertain_fields?: string[];
}
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
export type SituationKey = "apply" | "cold_email" | "follow_up" | "thank_you" | "referral" | "reply_recruiter" | "internship";
export interface SituationOption { key: SituationKey; title: string; description: string; badge: string; iconName: string; }
export type ToneKey = "professional" | "casual" | "confident" | "short" | "concise" | "enthusiastic";
export interface ToneOption { key: ToneKey; label: string; description: string; example: string; }

export interface SourceEvidence {
  field: string; value: string; quote: string; confidence: number | null;
  status: "verified" | "uncertain";
}
export interface ResumeProject {
  name: string | null; description: string | null; skills: string[]; achievements: string[];
  start_date: string | null; end_date: string | null;
}
export interface ResumeEmployment {
  company: string | null; role: string | null; start_date: string | null; end_date: string | null;
  description: string | null; skills: string[]; achievements: string[];
}
export interface ResumeEducation {
  institution: string | null; degree: string | null; field_of_study: string | null;
  start_date: string | null; end_date: string | null;
}
export interface IntelligenceStatus { enabled: boolean; ready: boolean; }
export interface ResumeVersion {
  id: number; revision: number; approved: boolean; data: Record<string, unknown>;
  metadata: Record<string, unknown>; source_metadata?: Record<string, unknown>; created_at: string;
}
export interface MatchCategory {
  key: string; label: string; base_weight: number; weight: number; score: number | null;
  available: boolean; explanation: string;
}
export interface RequirementMatch {
  category: string; requirement: string; status: "exact" | "alias" | "related" | "missing" | "uncertain";
  evidence: string[]; mandatory: boolean;
}
export interface SkillGap {
  skill: string; priority: "required" | "preferred" | "unclear"; reason: string; activities: string[];
}
export interface ATSReport {
  technical_score: number; checks: { key: string; label: string; status: "pass" | "warn" | "fail"; detail: string; suggestion: string }[];
  keyword_relevance: number | null; limitations: string[]; disclaimer: string;
}
export interface IntelligenceResult {
  gap_explanation?: string; overall_score: number | null; categories: MatchCategory[]; requirements: RequirementMatch[];
  mandatory_unmet: string[]; gaps: SkillGap[]; ats: ATSReport; disclaimer: string;
}
export interface IntelligenceReport {
  id: number; job_id: number | null; resume_version_id: number; algorithm_version: string;
  profile_version: string; job_version: string | null; result: IntelligenceResult; created_at: string;
}
export type CareerDocumentKind = "tailored_resume" | "cover_letter" | "email";
export interface CareerDocument {
  id: number; job_id: number; resume_version_id: number; parent_id: number | null;
  lineage_id: string; revision: number; kind: CareerDocumentKind;
  content: { subject_line?: string | null; subject_suggestions?: string[]; body: string }; warnings: string[];
  approved: boolean; draft_id?: number | null; created_at: string;
}
export interface CareerDocumentGenerate {
  job_id: number; kind: CareerDocumentKind; parent_id?: number; tone?: string; situation?: string;
}
export interface CareerDocumentUpdate { body?: string; subject_line?: string | null; approved?: boolean; }

export interface DiscoveryStatus { enabled: boolean; ready: boolean; provider: string; provider_configured: boolean; scheduler_configured: boolean; }
export interface ExternalJobListing {
  id: number; provider: string; provider_job_id: string; title: string; company: string | null;
  location: string | null; job_type: string | null; salary_text: string | null; experience_text: string | null;
  skills: string[]; description: string; provider_url: string; application_url: string;
  published_at: string | null; fetched_at: string; freshness: "today" | "recent" | "older" | "unknown";
  saved_job_id: number | null;
}
export interface JobSearchResult { jobs: ExternalJobListing[]; total: number; page: number; page_size: number; provider: string; partial: boolean; }
export interface SavedJob {
  id: number; listing: ExternalJobListing; job_id: number | null; notes: string | null; tags: string[];
  archived_at: string | null; created_at: string; updated_at: string | null;
}
export interface JobPreferences {
  id: number; roles: string[]; locations: string[]; remote_policy: "any" | "remote" | "hybrid" | "onsite";
  experience_levels: string[]; job_types: string[]; timezone: string; version: number; updated_at: string;
}
export interface ImportPreview {
  preview_token: string; mode: "url" | "manual"; source_url: string | null; structured: boolean;
  title: string | null; company: string | null; location: string | null; job_type: string | null;
  salary_text: string | null; experience_text: string | null; skills: string[]; description: string;
  application_url: string | null; warnings: string[];
}
export type CanonicalApplicationStatus = "Saved" | "Preparing" | "Applied" | "Assessment" | "Interview" | "Offer" | "Rejected" | "Withdrawn";
export interface Application {
  id: number; saved_job_id: number; job_id: number | null; status: CanonicalApplicationStatus;
  submitted_at: string | null; application_date: string | null; recruiter_name: string | null;
  recruiter_email: string | null; notes: string | null; interview_at: string | null; deadline_at: string | null;
  resume_version_id: number | null; email_version_id: number | null; cover_letter_version_id: number | null;
  version: number; created_at: string; updated_at: string;
  job: { listing_id: number; title: string; company: string | null; location: string | null; application_url: string; provider: string } | null;
}
export interface Reminder {
  id: number; application_id: number | null; kind: "application" | "interview" | "deadline" | "follow_up";
  title: string; note: string | null; due_at: string; timezone: string;
  state: "upcoming" | "overdue" | "completed" | "snoozed" | "dismissed";
  snoozed_until: string | null; completed_at: string | null; dismissed_at: string | null;
  attempts: number; version: number; created_at: string; updated_at: string;
}
export interface InAppNotification { id: number; reminder_id: number | null; type: string; title: string; message: string; read_at: string | null; dismissed_at: string | null; created_at: string; }
export interface ActivityEvent { id: number; application_id: number; event_type: string; from_status: string | null; to_status: string | null; context: Record<string, unknown>; occurred_at: string; }
export interface ApplicationAnalytics {
  total_applications: number; submitted_applications: number; interviews: number; offers: number; rejections: number;
  response_rate: number | null; interview_rate: number | null; offer_rate: number | null;
  state_counts: Record<string, number>; weekly_trend: { date: string; applications: number }[];
  average_match_score: number | null; definitions: Record<string, string>;
}
export type InterviewType = "technical" | "hr" | "behavioral" | "project";
export type InterviewDifficulty = "beginner" | "intermediate" | "advanced";
export interface InterviewEvaluation { id:number; categories:{category:string;score:number;rationale:string}[]; evidence:string[]; strengths:string[]; improvements:string[]; sample_improved_answer:string; practice_score:number; rubric_version:string; model:string; created_at:string; }
export interface InterviewQuestion { id:number; position:number; question_type:InterviewType; question:string; competency:string; rubric:Record<string,string>; follow_up_to_id:number|null; answer:{id:number;text:string;version:number;submitted_at:string}|null; evaluation:InterviewEvaluation|null; }
export interface InterviewSession { id:number; job_id:number|null; resume_version_id:number; interview_type:InterviewType; difficulty:InterviewDifficulty; status:"in_progress"|"paused"|"completed"|"evaluated"; question_count:number; time_limit_minutes:number|null; version:number; started_at:string; paused_at:string|null; completed_at:string|null; evaluated_at:string|null; created_at:string; disclaimer:string; questions?:InterviewQuestion[]; }
export interface InterviewHistory { sessions:InterviewSession[]; total:number; page:number; page_size:number; }
export interface InterviewStatus { enabled:boolean; ready:boolean; text_only:boolean; gmail_enabled:boolean; }
export interface NotificationPreferences { categories:Record<string,boolean>; email_enabled:boolean; timezone:string; quiet_hours:Record<string,string>; version:number; updated_at:string|null; }
export interface GmailStatus { enabled:boolean; ready:boolean; connected:boolean; email_hint:string|null; scopes:string[]; privacy:string; }
export interface AdvancedAnalytics { filters:Record<string,string|null>; funnel:{saved:number;submitted:number;responses:number;interviews:number;offers:number;rejections:number;state_counts:Record<string,number>}; rates:{response:number|null;interview:number|null;offer:number|null}; weekly_applications:{date:string;applications:number}[]; interview_practice:{sessions:number;average_score:number|null;average_by_type:Record<string,number>}; definitions:Record<string,string>; }
export interface AdminOverview { health:{database:string}; counts:Record<string,number>; providers:{gemini_configured:boolean;job_provider:string;job_provider_configured:boolean;gmail_enabled:boolean}; privacy:string; }
export interface Recommendation {
  listing_id: number; compatibility_score: number; preference_score: number; ranking_score: number;
  preference_explanation: string[]; missing_required: string[]; preferred_gaps: string[];
  disclaimer: string; listing: { id: number; title: string; company: string | null; location: string | null;
    job_type: string | null; provider: string; application_url: string; published_at: string | null; fetched_at: string };
}

import type { ActivityEvent, Application, ApplicationAnalytics, CanonicalApplicationStatus, DiscoveryStatus, ExternalJobListing, ImportPreview, InAppNotification, IntelligenceStatus, JobPreferences, JobSearchResult, Recommendation, Reminder, ResumeVersion, IntelligenceReport, CareerDocument, CareerDocumentGenerate, CareerDocumentUpdate, SavedJob, User, Token, Profile, ProfileUpdate, Job, JobCreate, MatchResponse, EmailGenerateRequest, EmailGenerateResponse, Draft, DraftUpdate, InterviewStatus, InterviewHistory, InterviewSession, InterviewType, InterviewDifficulty, NotificationPreferences, GmailStatus, AdvancedAnalytics, AdminOverview } from "@/types";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8002").replace(/\/+$/, "");
const TOKEN_KEY = "ai_recruiter_token";
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = "ApiError"; }
}
export function getToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(TOKEN_KEY, token);
    window.dispatchEvent(new Event("auth-changed"));
  }
}
export function clearAuth(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(TOKEN_KEY);
    // Remove identity and demo state left by previous versions of the app.
    for (const key of ["ai_recruiter_user", "ai_recruiter_profile", "ai_recruiter_drafts", "ai_recruiter_jobs", "ai_recruiter_registered_users"]) window.localStorage.removeItem(key);
    window.dispatchEvent(new Event("auth-changed"));
  }
}
function errorDetail(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) return fallback;
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => typeof item?.msg === "string" ? item.msg : "Invalid request").join("; ");
  return fallback;
}
async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 120000, asBlob = false): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, signal: controller.signal, cache: "no-store" });
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => null);
      if (response.status === 401 && token && getToken() === token) clearAuth();
      throw new ApiError(response.status, errorDetail(payload, `Request failed (${response.status})`));
    }
    if (token && getToken() !== token) throw new ApiError(409, "Your session changed. Please retry this action.");
    if (response.status === 204) return undefined as T;
    if (asBlob) return await response.blob() as T;
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) throw new ApiError(408, "The request timed out. Please try again.");
    throw new ApiError(0, "Cannot reach the backend. Check that FastAPI is running on port 8002.");
  } finally { clearTimeout(timer); }
}
export const login = (email: string, password: string) => request<Token>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
export const register = (email: string, password: string) => request<User>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
export const getMe = () => request<User>("/api/auth/me");
export function uploadResume(file: File): Promise<Profile> {
  const form = new FormData(); form.append("file", file);
  return request<Profile>("/api/resume/upload", { method: "POST", body: form });
}
export const getProfile = () => request<Profile>("/api/profile/me");
export const updateProfile = (data: ProfileUpdate) => request<Profile>("/api/profile/me", { method: "PUT", body: JSON.stringify(data) });
export const analyzeJob = (data: JobCreate) => request<Job>("/api/jobs/analyze", { method: "POST", body: JSON.stringify(data) });
export const getJobs = () => request<Job[]>("/api/jobs/");
export const compareMatch = (jobId: number) => request<MatchResponse>("/api/match/compare", { method: "POST", body: JSON.stringify({ job_id: jobId }) }, 180000);
export const generateEmail = (data: EmailGenerateRequest) => request<EmailGenerateResponse>("/api/email/generate", { method: "POST", body: JSON.stringify(data) }, 180000);
export const getDrafts = () => request<Draft[]>("/api/drafts/");
export const getDraftById = (id: number) => request<Draft>(`/api/drafts/${id}`);
export const updateDraft = (id: number, data: DraftUpdate) => request<Draft>(`/api/drafts/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteDraft = (id: number) => request<void>(`/api/drafts/${id}`, { method: "DELETE" });

export const getIntelligenceStatus = () => request<IntelligenceStatus>("/api/intelligence/status");
export const getResumeVersions = () => request<ResumeVersion[]>("/api/intelligence/resumes");
export const getResumeVersionSource = (id: number) => request<{ resume_version_id: number; source_text: string }>(`/api/intelligence/resumes/${id}/source`);
export const saveResumeVersion = (approved: boolean) => request<ResumeVersion>("/api/intelligence/resumes", { method: "POST", body: JSON.stringify({ approved }) });
export const analyzeIntelligence = (data: { job_id?: number; resume_version_id?: number; include_explanation?: boolean }) => request<IntelligenceReport>("/api/intelligence/analyze", { method: "POST", body: JSON.stringify(data) }, 180000);
export const getIntelligenceReports = (jobId?: number) => request<IntelligenceReport[]>(`/api/intelligence/reports${jobId ? `?job_id=${jobId}` : ""}`);
export const getIntelligenceReport = (id: number) => request<IntelligenceReport>(`/api/intelligence/reports/${id}`);
export const getCareerDocuments = (jobId?: number) => request<CareerDocument[]>(`/api/intelligence/documents${jobId ? `?job_id=${jobId}` : ""}`);
export const generateCareerDocument = (data: CareerDocumentGenerate) => request<CareerDocument>("/api/intelligence/documents/generate", { method: "POST", body: JSON.stringify(data) }, 180000);
export const updateCareerDocument = (id: number, data: CareerDocumentUpdate) => request<CareerDocument>(`/api/intelligence/documents/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const exportCareerDocument = (id: number, format: "pdf" | "docx") => request<Blob>(`/api/intelligence/documents/${id}/export?format=${format}`, {}, 120000, true);

export const getDiscoveryStatus = () => request<DiscoveryStatus>("/api/discovery/status");
export const searchJobs = (params: { keywords: string; location?: string; page?: number; page_size?: number; salary_min?: number; job_type?: string; sort?: string }) => {
  const query = new URLSearchParams(); Object.entries(params).forEach(([key,value]) => { if (value !== undefined && value !== "") query.set(key,String(value)); });
  return request<JobSearchResult>(`/api/discovery/search?${query}`);
};
export const getListing = (id: number) => request<ExternalJobListing>(`/api/discovery/listings/${id}`);
export const getSavedJobs = (params: { archived?: boolean; search?: string; tag?: string } = {}) => {
  const query = new URLSearchParams(); Object.entries(params).forEach(([key,value]) => { if (value !== undefined && value !== "") query.set(key,String(value)); });
  return request<SavedJob[]>(`/api/discovery/saved-jobs${query.size ? `?${query}` : ""}`);
};
export const saveDiscoveredJob = (data: { listing_id: number; notes?: string; tags?: string[] }) => request<SavedJob>("/api/discovery/saved-jobs", { method:"POST", body:JSON.stringify(data) });
export const updateSavedJob = (id: number, data: { notes?: string | null; tags?: string[]; archived?: boolean }) => request<SavedJob>(`/api/discovery/saved-jobs/${id}`, { method:"PUT", body:JSON.stringify(data) });
export const previewJobImport = (data: { url?: string; manual_text?: string }) => request<ImportPreview>("/api/discovery/import/preview", { method:"POST", body:JSON.stringify(data) }, 180000);
export const saveJobImport = (data: Record<string, unknown>) => request<SavedJob>("/api/discovery/import/save", { method:"POST", body:JSON.stringify(data) });
export const getJobPreferences = () => request<JobPreferences>("/api/discovery/preferences");
export const updateJobPreferences = (data: Omit<JobPreferences,"id"|"version"|"updated_at">) => request<JobPreferences>("/api/discovery/preferences", { method:"PUT", body:JSON.stringify(data) });
export const getRecommendations = () => request<{ recommendations: Recommendation[]; message: string }>("/api/discovery/recommendations");
export const getApplications = (params: { status?: string; search?: string } = {}) => { const query = new URLSearchParams(params as Record<string,string>); return request<Application[]>(`/api/applications/${query.size ? `?${query}` : ""}`); };
export const createApplication = (saved_job_id: number, notes?: string) => request<Application>("/api/applications/", { method:"POST", body:JSON.stringify({ saved_job_id,notes }) });
export const updateApplication = (id: number, data: { expected_version: number; status?: CanonicalApplicationStatus; confirm_submission?: boolean; notes?: string | null; interview_at?: string | null; deadline_at?: string | null; recruiter_name?: string | null; recruiter_email?: string | null; resume_version_id?: number | null; email_version_id?: number | null; cover_letter_version_id?: number | null }) => request<Application>(`/api/applications/${id}`, { method:"PUT", body:JSON.stringify(data) });
export const getReminders = (state?: string) => request<Reminder[]>(`/api/applications/reminders/list${state ? `?state=${encodeURIComponent(state)}` : ""}`);
export const createReminder = (data: { application_id?: number; kind: string; title: string; note?: string; due_at: string; timezone: string }) => request<Reminder>("/api/applications/reminders", { method:"POST", body:JSON.stringify(data) });
export const updateReminder = (id: number, data: { expected_version: number; action: "complete" | "snooze" | "dismiss"; snoozed_until?: string }) => request<Reminder>(`/api/applications/reminders/${id}`, { method:"PUT", body:JSON.stringify(data) });
export const processMyReminders = () => request<{ delivered: number }>("/api/applications/reminders/process-mine", { method:"POST" });
export const getNotifications = () => request<InAppNotification[]>("/api/applications/notifications/list");
export const updateNotification = (id: number, data: { read?: boolean; dismissed?: boolean }) => request<{ id:number; read_at:string|null; dismissed_at:string|null }>(`/api/applications/notifications/${id}`, { method:"PUT", body:JSON.stringify(data) });
export const getActivity = (page=1) => request<{ events: ActivityEvent[]; total:number; page:number; page_size:number }>(`/api/applications/activity/list?page=${page}`);
export const getApplicationAnalytics = () => request<ApplicationAnalytics>("/api/applications/analytics/summary");

export const getInterviewStatus = () => request<InterviewStatus>("/api/interviews/status");
export const getInterviewHistory = (page=1) => request<InterviewHistory>(`/api/interviews/sessions?page=${page}`);
export const getInterviewSession = (id:number) => request<InterviewSession>(`/api/interviews/sessions/${id}`);
export const startInterview = (data:{resume_version_id:number;job_id?:number;interview_type:InterviewType;difficulty:InterviewDifficulty;question_count:number;time_limit_minutes?:number}) => request<InterviewSession>("/api/interviews/sessions",{method:"POST",body:JSON.stringify(data)},180000);
export const updateInterviewState = (id:number,data:{expected_version:number;action:"pause"|"resume"}) => request<InterviewSession>(`/api/interviews/sessions/${id}/state`,{method:"PUT",body:JSON.stringify(data)});
export const submitInterviewAnswer = (sessionId:number,questionId:number,answer:string) => request<InterviewSession>(`/api/interviews/sessions/${sessionId}/questions/${questionId}/answer`,{method:"PUT",body:JSON.stringify({answer})});
export const requestInterviewFollowUp = (sessionId:number,questionId:number) => request(`/api/interviews/sessions/${sessionId}/questions/${questionId}/follow-up`,{method:"POST"},180000);
export const evaluateInterview = (id:number) => request<InterviewSession>(`/api/interviews/sessions/${id}/evaluate`,{method:"POST"},180000);
export const getNotificationPreferences = () => request<NotificationPreferences>("/api/notifications/preferences");
export const updateNotificationPreferences = (data:{categories:Record<string,boolean>;email_enabled:boolean;timezone:string;quiet_hours:Record<string,string>;expected_version?:number}) => request<NotificationPreferences>("/api/notifications/preferences",{method:"PUT",body:JSON.stringify(data)});
export const getGmailStatus = () => request<GmailStatus>("/api/integrations/gmail/status");
export const startGmailOAuth = () => request<{authorization_url:string}>("/api/integrations/gmail/authorize",{method:"POST"});
export const finishGmailOAuth = (state:string,code:string) => request<{connected:boolean;email_hint:string|null;scopes:string[]}>("/api/integrations/gmail/callback",{method:"POST",body:JSON.stringify({state,code})});
export const disconnectGmail = () => request<{connected:boolean}>("/api/integrations/gmail",{method:"DELETE"});
export const sendApprovedGmail = (data:{generation_version_id:number;recipient:string;subject:string;body:string;confirm_review:true;idempotency_key:string}) => request<{status:string;send_record_id:number;duplicate:boolean}>("/api/integrations/gmail/send",{method:"POST",body:JSON.stringify(data)},180000);
export const getAdvancedAnalytics = (params:Record<string,string>={}) => {const query=new URLSearchParams(params);return request<AdvancedAnalytics>(`/api/analytics/career${query.size?`?${query}`:""}`)};
export const getAdminOverview = () => request<AdminOverview>("/api/admin/overview");
export const getAdminAuditEvents = () => request<{id:number;actor_user_id:number|null;action:string;metadata:Record<string,unknown>;occurred_at:string}[]>("/api/admin/audit-events");

export const api = { getNotificationPreferences,updateNotificationPreferences,getGmailStatus,startGmailOAuth,finishGmailOAuth,disconnectGmail,sendApprovedGmail,getAdvancedAnalytics,getAdminOverview,getAdminAuditEvents,getInterviewStatus,getInterviewHistory,getInterviewSession,startInterview,updateInterviewState,submitInterviewAnswer,requestInterviewFollowUp,evaluateInterview,getDiscoveryStatus, searchJobs, getListing, getSavedJobs, saveDiscoveredJob, updateSavedJob, previewJobImport, saveJobImport, getJobPreferences, updateJobPreferences, getRecommendations, getApplications, createApplication, updateApplication, getReminders, createReminder, updateReminder, processMyReminders, getNotifications, updateNotification, getActivity, getApplicationAnalytics, getIntelligenceStatus, getResumeVersions, getResumeVersionSource, saveResumeVersion, analyzeIntelligence, getIntelligenceReports, getIntelligenceReport, getCareerDocuments, generateCareerDocument, updateCareerDocument, exportCareerDocument, login, register, getMe, uploadResume, getProfile, updateProfile, analyzeJob, getJobs, compareMatch, generateEmail, getDrafts, getDraftById, updateDraft, deleteDraft, clearAuth };

import type { User, Token, Profile, ProfileUpdate, Job, JobCreate, MatchResponse, EmailGenerateRequest, EmailGenerateResponse, Draft, DraftUpdate } from "@/types";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001").replace(/\/+$/, "");
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
async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 120000): Promise<T> {
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
    if (response.status === 204) return undefined as T;
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) throw new ApiError(408, "The request timed out. Please try again.");
    throw new ApiError(0, "Cannot reach the backend. Check that FastAPI is running on port 8001.");
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
export const api = { login, register, getMe, uploadResume, getProfile, updateProfile, analyzeJob, getJobs, compareMatch, generateEmail, getDrafts, getDraftById, updateDraft, deleteDraft, clearAuth };

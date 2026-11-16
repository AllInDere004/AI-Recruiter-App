import type { Draft, DraftWithJob, Job, ParsedData, Profile } from "@/types";
export function parsedProfile(profile: Profile): ParsedData {
  const data = profile.parsed_data || {};
  return {
    ...data,
    full_name: profile.full_name ?? (typeof data.full_name === "string" ? data.full_name : null),
    email: typeof data.email === "string" ? data.email : null,
    phone: typeof data.phone === "string" ? data.phone : null,
    summary: typeof data.summary === "string" ? data.summary : null,
    skills: Array.isArray(data.skills) ? data.skills.filter((s): s is string => typeof s === "string") : [],
    experience: Array.isArray(data.experience) ? data.experience.filter((v): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)) : [],
    education: Array.isArray(data.education) ? data.education.filter((v): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)) : [],
  };
}
export function draftsWithJobs(drafts: Draft[], jobs: Job[]): DraftWithJob[] {
  const byId = new Map(jobs.map(job => [job.id, job]));
  return drafts.map(draft => ({ ...draft, job: byId.get(draft.job_id) }));
}
export const messageOf = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Please try again.";

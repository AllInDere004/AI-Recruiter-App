"use client";
import { useState } from "react";
import type { Job, JobCreate } from "@/types";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { messageOf } from "@/lib/presenters";
export function JobInput({ onJobSelected, savedJobs, onAnalyzeJob, isLoading = false }: { onJobSelected: (job: Job) => void; savedJobs: Job[]; onAnalyzeJob: (data: JobCreate) => Promise<Job>; isLoading?: boolean }) {
  const [company,setCompany] = useState(""); const [title,setTitle] = useState(""); const [description,setDescription] = useState(""); const [error,setError] = useState("");
  return <Card className="workspace-pearl"><CardHeader><CardTitle>Target job</CardTitle></CardHeader><CardContent className="space-y-5">
    {savedJobs.length > 0 && <label className="block text-sm space-y-1"><span>Saved jobs</span><select aria-label="Saved jobs" defaultValue="" className="w-full rounded-lg bg-[#0E1B38] p-3 border border-[#1E3560]" onChange={event => { const job = savedJobs.find(item => item.id === Number(event.target.value)); if (job) onJobSelected(job); }}><option value="" disabled>Select a saved job</option>{savedJobs.map(job => <option value={job.id} key={job.id}>{job.company || "Company not specified"} - {job.title || "Role not specified"}</option>)}</select></label>}
    <form className="space-y-4" onSubmit={async event => { event.preventDefault(); setError(""); try { const job = await onAnalyzeJob({ company:company.trim() || null,title:title.trim() || null,description }); onJobSelected(job); } catch (cause) { setError(messageOf(cause)); } }}>
      <div className="grid sm:grid-cols-2 gap-4"><label className="text-sm space-y-1"><span>Company (optional)</span><Input aria-label="Company" value={company} onChange={event => setCompany(event.target.value)} /></label><label className="text-sm space-y-1"><span>Role title (optional)</span><Input aria-label="Role title" value={title} onChange={event => setTitle(event.target.value)} /></label></div>
      <label className="block text-sm space-y-1"><span>Job description</span><textarea aria-label="Job description" required rows={6} className="w-full rounded-lg bg-[#0E1B38] p-3 border border-[#1E3560]" value={description} onChange={event => setDescription(event.target.value)} /></label>
      {error && <p role="alert" className="text-rose-300">{error}</p>}<Button type="submit" isLoading={isLoading}>Analyze &amp; Extract Needs</Button>
    </form>
  </CardContent></Card>;
}

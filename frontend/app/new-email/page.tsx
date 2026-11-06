"use client";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { Job, JobCreate, MatchResponse, EmailGenerateResponse, Profile, SituationKey, ToneKey } from "@/types";
import { api } from "@/lib/api";
import { messageOf, parsedProfile } from "@/lib/presenters";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { JobInput } from "@/components/JobInput";
import { SituationPicker } from "@/components/SituationPicker";
import { TonePicker } from "@/components/TonePicker";
import { MatchPoints } from "@/components/MatchPoints";
import { EmailEditor } from "@/components/EmailEditor";
import { ScorePanel } from "@/components/ScorePanel";
import { Button } from "@/components/ui/button";
function Wizard() {
  const router = useRouter(); const params = useSearchParams();
  const [profile,setProfile] = useState<Profile | null>(null); const [jobs,setJobs] = useState<Job[]>([]); const [job,setJob] = useState<Job | null>(null);
  const [step,setStep] = useState(1); const [situation,setSituation] = useState<SituationKey>("apply"); const [tone,setTone] = useState<ToneKey>("professional");
  const [notes,setNotes] = useState(""); const [match,setMatch] = useState<MatchResponse | null>(null); const [result,setResult] = useState<EmailGenerateResponse | null>(null);
  const [subject,setSubject] = useState(""); const [body,setBody] = useState(""); const [loading,setLoading] = useState(true); const [busy,setBusy] = useState(""); const [error,setError] = useState("");
  useEffect(() => { let active = true; Promise.all([api.getProfile(),api.getJobs()]).then(([savedProfile,savedJobs]) => { if (!active) return; setProfile(savedProfile); setJobs(savedJobs); const selected = savedJobs.find(item => item.id === Number(params.get("job_id"))); if (selected) { setJob(selected); setStep(2); } const requested = params.get("situation"); if (["apply","cold_email","follow_up","thank_you","referral","reply_recruiter"].includes(requested || "")) setSituation(requested as SituationKey); }).catch(cause => { if (active) setError(messageOf(cause)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [params]);
  const analyze = async (data: JobCreate) => { setBusy("analyze"); try { const saved = await api.analyzeJob(data); setJobs(previous => [saved,...previous]); return saved; } finally { setBusy(""); } };
  const compare = async () => { if (!job) return; setError(""); setBusy("match"); try { setMatch(await api.compareMatch(job.id)); setStep(3); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(""); } };
  const generate = async (overrideTone?: string) => { if (!job) return; setError(""); setBusy("generate"); try { const generated = await api.generateEmail({ job_id:job.id,situation,tone:overrideTone || tone,custom_notes:notes || null }); setResult(generated); setSubject(generated.subject_line); setBody(generated.body); setStep(4); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(""); } };
  const save = async () => { if (!result) return; setError(""); setBusy("save"); try { await api.updateDraft(result.draft_id,{ subject_line:subject,body,situation,tone }); router.push("/tracker"); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(""); } };
  const edited = !!result && (body !== result.body || subject !== result.subject_line);
  const skills = profile ? parsedProfile(profile).skills : [];
  return <WorkspaceShell section="New Email"><main className="workspace-main p-4 sm:p-8 space-y-6 max-w-6xl mx-auto">
    <h1 className="text-3xl font-bold">Your outreach studio</h1><p className="text-sm text-[#8FA0BE]">Step {step} of 4: job, situation, match, and email.</p>
    {error && <p role="alert" className="text-rose-300">{error}</p>}
    {loading ? <p role="status">Loading your workspace...</p> : !profile ? <p><Link className="text-[#FF8C38] underline" href="/onboarding">Upload your resume</Link> before generating email.</p> : <>
      {step === 1 && <><JobInput savedJobs={jobs} onAnalyzeJob={analyze} onJobSelected={setJob} isLoading={busy === "analyze"} />{job && <div className="space-y-3"><p>Selected job: {job.company || "Company not specified"} - {job.title || "Role not specified"}</p><p className="text-sm text-[#8FA0BE]">Required skills: {(job.extracted_skills?.required_skills || []).join(", ") || "None listed"}</p><Button onClick={() => setStep(2)}>Proceed to Situation</Button></div>}</>}
      {step === 2 && <><SituationPicker selectedSituation={situation} onSelectSituation={setSituation} /><TonePicker selectedTone={tone} onSelectTone={setTone} /><label className="block space-y-1 text-sm"><span>Custom notes (optional)</span><textarea aria-label="Custom notes" className="w-full bg-[#0E1B38] rounded-lg p-3 border border-[#1E3560]" value={notes} onChange={event => setNotes(event.target.value)} /></label><div className="flex gap-3"><Button variant="outline" onClick={() => setStep(1)}>Back to Job</Button><Button onClick={compare} isLoading={busy === "match"}>Compute Matching Points</Button></div></>}
      {step === 3 && <><MatchPoints match={match} /><div className="flex gap-3"><Button variant="outline" onClick={() => setStep(2)}>Back to Situation</Button><Button onClick={() => generate()} isLoading={busy === "generate"}>Generate Factual Recruiter Email</Button></div></>}
      {step === 4 && result && <><p role="status" className="text-sm text-emerald-300">Generated draft #{result.draft_id} is saved. Review it before sending.</p><div className="grid lg:grid-cols-3 gap-6"><div className="lg:col-span-2"><EmailEditor subject={subject} body={body} tone={tone} verifiedSkills={skills} warnings={edited ? [] : result.hallucination_warnings} onSubjectChange={setSubject} onBodyChange={setBody} onRegenerate={generate} isRegenerating={busy === "generate"} /></div><div className="space-y-4"><ScorePanel score={result.match_score} edited={edited} /><MatchPoints match={match} /></div></div><Button onClick={save} isLoading={busy === "save"} disabled={!body.trim()}>Save to Tracker</Button></>}
    </>}
  </main></WorkspaceShell>;
}
export default function NewEmailPage() { return <Suspense fallback={<p className="p-8">Loading...</p>}><Wizard /></Suspense>; }

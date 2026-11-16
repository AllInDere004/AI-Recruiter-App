"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { Draft, ApplicationStatus } from "@/types";
import { api } from "@/lib/api";
import { messageOf } from "@/lib/presenters";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { EmailEditor } from "@/components/EmailEditor";
import { ScorePanel } from "@/components/ScorePanel";
import { TRACKER_STATUSES } from "@/components/TrackerBoard";
import { Button } from "@/components/ui/button";
export default function DraftPage() {
  const params = useParams<{ id: string }>(); const router = useRouter(); const id = Number(params.id);
  const [draft,setDraft] = useState<Draft | null>(null); const [subject,setSubject] = useState(""); const [body,setBody] = useState(""); const [status,setStatus] = useState<ApplicationStatus>("Draft"); const [loading,setLoading] = useState(true); const [busy,setBusy] = useState(""); const [error,setError] = useState(""); const [notice,setNotice] = useState(""); const [review,setReview] = useState<{ id:number; warnings:string[] } | null>(null);
  const fill = (data: Draft) => { setDraft(data); setSubject(data.subject_line || ""); setBody(data.body); setStatus(data.status); };
  useEffect(() => { let active = true; setLoading(true); setError(""); if (!Number.isInteger(id) || id < 1) { setError("Invalid draft ID."); setLoading(false); return; } api.getDraftById(id).then(data => { if (active) fill(data); }).catch(cause => { if (active) setError(messageOf(cause)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; },[id]);
  const save = async () => { if (!draft) return; setError(""); setNotice(""); setBusy("save"); try { fill(await api.updateDraft(draft.id,{ subject_line:subject,body,status })); setNotice("Draft saved."); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(""); } };
  const regenerate = async (tone?: string) => { if (!draft) return; setError(""); setBusy("generate"); try { const generated = await api.generateEmail({ job_id:draft.job_id,situation:draft.situation,tone:tone || draft.tone }); const saved = await api.getDraftById(generated.draft_id); fill(saved); setReview({ id:saved.id,warnings:generated.hallucination_warnings }); router.replace(`/drafts/${saved.id}`); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(""); } };
  const remove = async () => { if (!draft) return; setError(""); setBusy("delete"); try { await api.deleteDraft(draft.id); router.replace("/tracker"); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(""); } };
  const edited = !!draft && (body !== draft.body || subject !== (draft.subject_line || ""));
  return <WorkspaceShell section="Draft editor"><main className="workspace-main p-4 sm:p-8 space-y-6 max-w-6xl mx-auto"><h1 className="text-3xl font-bold">Draft editor</h1>{draft && <Link href={`/new-email?job_id=${draft.job_id}`} className="text-sm text-[#FF8C38]">View job analyses and career documents</Link>}{error && <p role="alert" className="text-rose-300">{error}</p>}{notice && <p role="status" className="text-emerald-300">{notice}</p>}{loading ? <p>Loading draft...</p> : draft && <><div className="flex flex-wrap gap-3 items-center"><label className="text-sm">Application status <select aria-label="Application status" className="bg-[#101C38] border border-[#1E3560] rounded-lg p-2" value={status} onChange={event => setStatus(event.target.value as ApplicationStatus)}>{TRACKER_STATUSES.map(value => <option key={value}>{value}</option>)}</select></label><Button onClick={save} isLoading={busy === "save"} disabled={!body.trim()}>Save changes</Button><Button variant="outline" onClick={remove} isLoading={busy === "delete"}>Delete draft</Button></div><div className="grid lg:grid-cols-3 gap-6"><div className="lg:col-span-2"><EmailEditor subject={subject} body={body} tone={draft.tone} warnings={!edited && review?.id === draft.id ? review.warnings : []} onSubjectChange={setSubject} onBodyChange={setBody} onRegenerate={regenerate} isRegenerating={busy === "generate"} /></div><ScorePanel score={draft.match_score} edited={edited} /></div></>}</main></WorkspaceShell>;
}

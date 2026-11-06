"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { ApplicationStatus, DraftWithJob } from "@/types";
import { api } from "@/lib/api";
import { draftsWithJobs, messageOf } from "@/lib/presenters";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { TrackerBoard } from "@/components/TrackerBoard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
export default function TrackerPage() {
  const [drafts,setDrafts] = useState<DraftWithJob[]>([]); const [search,setSearch] = useState(""); const [loading,setLoading] = useState(true); const [pending,setPending] = useState<number | null>(null); const [error,setError] = useState("");
  const load = useCallback(async () => { setLoading(true); setError(""); try { const [saved,jobs] = await Promise.all([api.getDrafts(),api.getJobs()]); setDrafts(draftsWithJobs(saved,jobs)); } catch (cause) { setError(messageOf(cause)); } finally { setLoading(false); } },[]);
  useEffect(() => { void load(); },[load]);
  const updateStatus = async (id: number,status: ApplicationStatus) => { setPending(id); setError(""); try { const updated = await api.updateDraft(id,{ status }); setDrafts(previous => previous.map(item => item.id === id ? { ...item,...updated } : item)); } catch (cause) { setError(messageOf(cause)); } finally { setPending(null); } };
  const remove = async (id: number) => { setPending(id); setError(""); try { await api.deleteDraft(id); setDrafts(previous => previous.filter(item => item.id !== id)); } catch (cause) { setError(messageOf(cause)); } finally { setPending(null); } };
  const filtered = drafts.filter(item => `${item.job?.company || ""} ${item.job?.title || ""} ${item.subject_line || ""}`.toLowerCase().includes(search.toLowerCase()));
  return <WorkspaceShell section="Application Tracker"><main className="workspace-main p-4 sm:p-8 space-y-6"><div className="flex justify-between gap-3"><h1 className="text-3xl font-bold">Application tracker</h1><Link className="text-[#FF8C38]" href="/new-email">New email</Link></div><div className="flex gap-3"><Input aria-label="Search drafts" placeholder="Search company, role, or subject" value={search} onChange={event => setSearch(event.target.value)} /><Button onClick={load} isLoading={loading}>Refresh</Button></div>{error && <p role="alert" className="text-rose-300">{error}</p>}{loading ? <p role="status">Loading drafts...</p> : <>{drafts.length === 0 && <p>No saved drafts yet. Generate an email to get started.</p>}<TrackerBoard drafts={filtered} onStatusChange={updateStatus} onDelete={remove} pendingId={pending} /></>}</main></WorkspaceShell>;
}

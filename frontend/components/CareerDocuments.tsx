"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { CareerDocument, CareerDocumentKind } from "@/types";
import { api } from "@/lib/api";
import { messageOf } from "@/lib/presenters";
import { formatDate } from "@/lib/utils";
import { useIntelligenceAvailability } from "./CareerIntelligence";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";

const kindLabel: Record<CareerDocumentKind, string> = {
  tailored_resume: "Tailored resume", cover_letter: "Cover letter", email: "Application email",
};

export function CareerDocuments({ jobId }: { jobId: number; originalResumeText?: string }) {
  const available = useIntelligenceAvailability();
  const [documents, setDocuments] = useState<CareerDocument[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [kind, setKind] = useState<CareerDocumentKind>("tailored_resume");
  const [tone, setTone] = useState("professional");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const [originalSource, setOriginalSource] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState("");
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceReload, setSourceReload] = useState(0);
  const busy = useRef(false);
  const scope = useRef({ active: true });
  const selected = documents.find(item => item.id === Number(selectedId));
  const edited = !!selected && (body !== selected.content.body || subject !== (selected.content.subject_line || ""));

  useEffect(() => {
    const current = { active: true };
    scope.current = current;
    busy.current = false;
    setDocuments([]); setSelectedId(""); setBody(""); setSubject("");
    setReviewed(false); setError(""); setNotice(""); setPending("");
    if (!available) return;
    setLoading(true);
    api.getCareerDocuments(jobId).then(saved => {
      if (scope.current !== current || !current.active) return;
      setDocuments(saved);
      if (saved[0]) select(saved[0]);
    }).catch(cause => { if (scope.current === current && current.active) setError(messageOf(cause)); })
      .finally(() => { if (scope.current === current && current.active) setLoading(false); });
    return () => { current.active = false; };
  }, [available, jobId, reload]);

  const sourceVersionId = selected?.kind === "tailored_resume" ? selected.resume_version_id : null;
  useEffect(() => {
    let active = true;
    setOriginalSource(null); setSourceError("");
    if (!available || !sourceVersionId) { setSourceLoading(false); return; }
    setSourceLoading(true);
    api.getResumeVersionSource(sourceVersionId).then(source => {
      if (!active) return;
      if (source.resume_version_id !== sourceVersionId) {
        setSourceError("The original resume version did not match this document. Reload the source.");
        return;
      }
      setOriginalSource(source.source_text);
    }).catch(cause => { if (active) setSourceError(messageOf(cause)); })
      .finally(() => { if (active) setSourceLoading(false); });
    return () => { active = false; };
  }, [available, sourceVersionId, sourceReload, jobId]);

  function select(item: CareerDocument) {
    setSelectedId(String(item.id)); setSubject(item.content.subject_line || "");
    setBody(item.content.body); setReviewed(false); setNotice("");
  }
  function receive(item: CareerDocument) {
    setDocuments(previous => [item, ...previous.filter(value => value.id !== item.id)]);
    select(item);
  }
  async function act(action: string, operation: () => Promise<void>) {
    if (busy.current) return;
    busy.current = true;
    const current = scope.current;
    setPending(action); setError(""); setNotice("");
    try { await operation(); }
    catch (cause) { if (scope.current === current && current.active) setError(messageOf(cause)); }
    finally { if (scope.current === current && current.active) { busy.current = false; setPending(""); } }
  }
  async function generate(parent?: CareerDocument) {
    const current = scope.current;
    await act("generate", async () => {
      const saved = await api.generateCareerDocument({
        job_id: jobId, kind: parent?.kind || kind, tone, situation: "apply",
        ...(parent ? { parent_id: parent.id } : {}),
      });
      if (scope.current !== current || !current.active) return;
      receive(saved); setNotice("A new draft version is saved. Review it before approval or export.");
    });
  }
  async function saveEdits() {
    if (!selected || !edited) return;
    const current = scope.current;
    await act("save", async () => {
      const saved = await api.updateCareerDocument(selected.id, { body, subject_line: subject });
      if (scope.current !== current || !current.active) return;
      receive(saved); setNotice("Edits saved as a new version. Previous versions are unchanged.");
    });
  }
  async function approve() {
    if (!selected || edited || !reviewed) return;
    const current = scope.current;
    await act("approve", async () => {
      const saved = await api.updateCareerDocument(selected.id, { approved: true });
      if (scope.current !== current || !current.active) return;
      receive(saved); setNotice("This version is approved and ready to export.");
    });
  }
  async function download(format: "pdf" | "docx") {
    if (!selected?.approved || edited) return;
    const current = scope.current;
    await act("export", async () => {
      const blob = await api.exportCareerDocument(selected.id, format);
      if (scope.current !== current || !current.active) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${selected.kind}-v${selected.revision}.${format}`;
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice(`${format.toUpperCase()} download prepared.`);
    });
  }

  if (!available) return null;
  return <Card className="workspace-pearl"><CardHeader><CardTitle>Career documents and versions</CardTitle></CardHeader><CardContent className="space-y-5">
    <p className="text-sm text-[#8FA0BE]">Generate from your reviewed resume and selected job. Your original resume stays unchanged. Every generated or edited draft is a separate version; nothing is sent automatically.</p>
    <div className="grid sm:grid-cols-2 gap-3">
      <label className="text-sm space-y-1"><span>Document type</span><select aria-label="Career document type" value={kind} disabled={!!pending} onChange={event => setKind(event.target.value as CareerDocumentKind)} className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-3">
        <option value="tailored_resume">Tailored resume</option><option value="cover_letter">Cover letter</option><option value="email">Application email</option>
      </select></label>
      <label className="text-sm space-y-1"><span>Writing tone</span><select aria-label="Career document tone" value={tone} disabled={!!pending} onChange={event => setTone(event.target.value)} className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-3">
        <option value="professional">Professional</option><option value="concise">Concise</option><option value="enthusiastic">Enthusiastic</option>
      </select></label>
    </div>
    <Button onClick={() => generate()} isLoading={pending === "generate"} disabled={!!pending || edited}>Generate career document</Button>
    <p className="text-xs text-[#8FA0BE]">Save a reviewed resume version in the career analysis panel first. Save your current edits before switching versions or generating another draft.</p>
    {loading ? <p role="status">Loading document history...</p> : documents.length ? <label className="block text-sm space-y-1"><span>Saved document versions</span>
      <select aria-label="Saved document versions" disabled={!!pending || edited} value={selectedId} onChange={event => { const item = documents.find(value => value.id === Number(event.target.value)); if (item) select(item); }} className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-3">
        {documents.map(item => <option key={item.id} value={item.id}>{kindLabel[item.kind]} | Version {item.revision} | {item.approved ? "Approved" : "Needs review"} | {formatDate(item.created_at)}</option>)}
      </select>
    </label> : <p className="text-sm text-[#8FA0BE]">No saved career documents for this job yet.</p>}
    {error && <div className="space-y-2"><p role="alert" className="text-rose-300">{error}</p><Button variant="outline" onClick={() => setReload(value => value + 1)} disabled={!!pending || edited}>Reload document history</Button></div>}
    {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
    {selected && <>
      <div className="flex flex-wrap items-center gap-3"><h3 className="font-semibold">{kindLabel[selected.kind]} | Version {selected.revision}</h3><span className="text-xs text-[#8FA0BE]">{selected.approved && !edited ? "Approved" : "Review required"} | Resume version {selected.resume_version_id}</span></div>
      {selected.warnings.length > 0 && <div role="alert" className="border border-amber-700 rounded-xl p-3 text-amber-300"><p className="font-semibold text-sm">Review these claims</p><ul className="list-disc pl-5 mt-2 text-sm">{selected.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
      <div className={selected.kind === "tailored_resume" ? "grid lg:grid-cols-2 gap-4" : ""}>
        {selected.kind === "tailored_resume" && <div className="space-y-2"><h4 className="font-semibold text-sm">Original resume for this version</h4>
          {sourceLoading ? <p role="status" className="text-sm">Loading the original resume for this version...</p> : sourceError ? <div className="space-y-2"><p role="alert" className="text-rose-300 text-sm">{sourceError}</p><Button variant="outline" onClick={() => setSourceReload(value => value + 1)}>Reload original resume</Button></div> : originalSource !== null ? <pre aria-label="Original resume source" className="whitespace-pre-wrap break-words max-h-[32rem] overflow-auto rounded-lg border border-[#1E3560] bg-[#0E1B38] p-3 text-xs font-sans">{originalSource}</pre> : <p className="text-sm text-[#8FA0BE]">The original source is unavailable.</p>}
          <p className="text-xs text-[#8FA0BE]">This is the exact original source for resume version {selected.resume_version_id}. Later uploads do not replace it.</p></div>}
        <div className="space-y-3">
          <h4 className="font-semibold text-sm">{selected.kind === "tailored_resume" ? "Tailored draft" : "Review and edit"}</h4>
          {selected.kind !== "tailored_resume" && <label className="block text-sm space-y-1"><span>Subject or heading</span><Input aria-label="Career document subject" value={subject} disabled={!!pending} onChange={event => { setSubject(event.target.value); setReviewed(false); }} /></label>}
          {selected.kind !== "tailored_resume" && !!selected.content.subject_suggestions?.length && <label className="block text-sm space-y-1"><span>Subject suggestions</span><select aria-label="Career document subject suggestions" value="" disabled={!!pending} onChange={event => { if (event.target.value) { setSubject(event.target.value); setReviewed(false); } }} className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-3"><option value="">Choose a suggested subject</option>{selected.content.subject_suggestions.map((value,index) => <option value={value} key={index}>{value}</option>)}</select></label>}
          <label className="block text-sm space-y-1"><span>Document content</span><textarea aria-label="Career document content" rows={18} value={body} disabled={!!pending} onChange={event => { setBody(event.target.value); setReviewed(false); }} className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-3 text-sm" /></label>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button onClick={saveEdits} isLoading={pending === "save"} disabled={!edited || !body.trim() || !!pending}>Save document as new version</Button>
        {edited && <Button variant="outline" disabled={!!pending} onClick={() => select(selected)}>Discard unsaved document edits</Button>}
        <Button variant="outline" onClick={() => generate(selected)} isLoading={pending === "generate"} disabled={!!pending || edited}>Regenerate as new version</Button>
      </div>
      {!selected.approved && !edited && <div className="space-y-3">
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={reviewed} disabled={!!pending} onChange={event => setReviewed(event.target.checked)} className="mt-1" /><span>I reviewed this document, checked its facts against my resume, and approve this version.</span></label>
        <Button onClick={approve} isLoading={pending === "approve"} disabled={!reviewed || !!pending}>Approve reviewed document</Button>
      </div>}
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => download("pdf")} disabled={!selected.approved || edited || !!pending} isLoading={pending === "export"}>Download PDF</Button>
        <Button variant="outline" onClick={() => download("docx")} disabled={!selected.approved || edited || !!pending}>Download DOCX</Button>
        {selected.draft_id && <Link href={`/drafts/${selected.draft_id}`} className="text-sm text-[#FF8C38] self-center underline">Open linked email draft</Link>}
      </div>
      <p className="text-xs text-[#8FA0BE]">Exports require approval. Manual edits need a new factual review. AI suggestions and alignment scores are advisory and never guarantee an interview or ATS acceptance.</p>
    </>}
  </CardContent></Card>;
}

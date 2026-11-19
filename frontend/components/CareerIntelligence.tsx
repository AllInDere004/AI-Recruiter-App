"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { messageOf } from "@/lib/presenters";
import type { IntelligenceReport, ResumeVersion } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { AnimatedBar } from "./AnimatedMetrics";
import { formatDate } from "@/lib/utils";

export function useIntelligenceAvailability() {
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    let active = true;
    api.getIntelligenceStatus().then(status => {
      if (active) setAvailable(status.enabled && status.ready);
    }).catch(() => { if (active) setAvailable(false); });
    return () => { active = false; };
  }, []);
  return available;
}

const scoreLabel = (score: number | null | undefined) =>
  typeof score === "number" && Number.isFinite(score) ? `${score.toFixed(1)} / 100` : "Not assessed";

export function CareerIntelligence({ jobId }: { jobId?: number }) {
  const available = useIntelligenceAvailability();
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [reports, setReports] = useState<IntelligenceReport[]>([]);
  const [resumeId, setResumeId] = useState("");
  const [reportId, setReportId] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [reload, setReload] = useState(0);
  const [includeExplanation, setIncludeExplanation] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const busy = useRef(false);
  const scope = useRef({ active: true });
  const selectedVersion = versions.find(version => version.id === Number(resumeId));
  const report = reports.find(item => item.id === Number(reportId));
  const result = report?.result;

  useEffect(() => {
    const current = { active: true };
    scope.current = current;
    busy.current = false;
    setPending(""); setError(""); setNotice(""); setReports([]); setVersions([]);
    setResumeId(""); setReportId(""); setReviewed(false);
    if (!available) return;
    setLoading(true);
    Promise.all([api.getResumeVersions(), api.getIntelligenceReports(jobId)]).then(([savedVersions, savedReports]) => {
      if (scope.current !== current || !current.active) return;
      setVersions(savedVersions); setReports(savedReports);
      setResumeId(String(savedVersions.find(version => version.approved)?.id || ""));
      setReportId(String(savedReports[0]?.id || ""));
    }).catch(cause => { if (scope.current === current && current.active) setError(messageOf(cause)); })
      .finally(() => { if (scope.current === current && current.active) setLoading(false); });
    return () => { current.active = false; };
  }, [available, jobId, reload]);

  async function saveReviewedResume() {
    if (busy.current || !reviewed) return;
    busy.current = true;
    const current = scope.current;
    setPending("resume"); setError(""); setNotice("");
    try {
      const saved = await api.saveResumeVersion(true);
      if (scope.current !== current || !current.active) return;
      setVersions(previous => [saved, ...previous.filter(item => item.id !== saved.id)]);
      setResumeId(String(saved.id)); setReviewed(false);
      setNotice(`Reviewed resume version ${saved.revision} saved. Your uploaded original is unchanged.`);
    } catch (cause) { if (scope.current === current && current.active) setError(messageOf(cause)); }
    finally { if (scope.current === current && current.active) { busy.current = false; setPending(""); } }
  }

  async function analyze() {
    if (busy.current || !selectedVersion?.approved) return;
    busy.current = true;
    const current = scope.current;
    setPending("analyze"); setError(""); setNotice("");
    try {
      const saved = await api.analyzeIntelligence({
        ...(jobId ? { job_id: jobId } : {}), resume_version_id: selectedVersion.id, include_explanation: includeExplanation,
      });
      if (scope.current !== current || !current.active) return;
      setReports(previous => [saved, ...previous.filter(item => item.id !== saved.id)]);
      setReportId(String(saved.id)); setNotice("Analysis saved. You can revisit it after signing in again.");
    } catch (cause) { if (scope.current === current && current.active) setError(messageOf(cause)); }
    finally { if (scope.current === current && current.active) { busy.current = false; setPending(""); } }
  }

  if (!available) return null;
  return <section aria-label="Career intelligence" className="space-y-5">
    <Card className="workspace-pearl">
      <CardHeader><CardTitle>{jobId ? "Evidence-based career match" : "Resume intelligence and ATS readiness"}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-[#8FA0BE]">Save your profile corrections first. Review the extracted details, then save an approved resume version for repeatable analysis.</p>
        <Link href="/profile" className="text-sm text-[#FF8C38] underline">Review your profile</Link>
        {loading ? <p role="status">Loading saved analyses...</p> : <>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={reviewed} disabled={!!pending} onChange={event => setReviewed(event.target.checked)} className="mt-1" />
            <span>I reviewed the saved profile and confirm that its qualifications and experience are accurate.</span>
          </label>
          <Button variant="outline" onClick={saveReviewedResume} disabled={!reviewed || !!pending} isLoading={pending === "resume"}>Save reviewed resume version</Button>
          <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
            <label className="block flex-1 text-sm space-y-1"><span>Resume version</span>
              <select aria-label="Resume version for analysis" className="w-full bg-[#0E1B38] border border-[#1E3560] rounded-lg p-3" value={resumeId} disabled={!!pending} onChange={event => setResumeId(event.target.value)}>
                <option value="">Select a reviewed version</option>
                {versions.map(version => <option key={version.id} value={version.id} disabled={!version.approved}>Version {version.revision} | {version.approved ? "Reviewed" : "Not approved"} | {formatDate(version.created_at)}</option>)}
              </select>
            </label>
            <Button onClick={analyze} disabled={!selectedVersion?.approved || !!pending} isLoading={pending === "analyze"}>{jobId ? "Analyze career match" : "Analyze ATS readiness"}</Button>
          </div>
          {jobId && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={includeExplanation} disabled={!!pending} onChange={event => setIncludeExplanation(event.target.checked)} className="mt-1" /><span>Include AI learning guidance grounded in the identified gaps.</span></label>}
          {!versions.length && <p className="text-sm text-[#8FA0BE]">No reviewed versions yet. Save one above to begin.</p>}
          {reports.length > 0 && <label className="block text-sm space-y-1"><span>Saved analyses</span>
            <select aria-label="Saved career analysis" value={reportId} onChange={event => setReportId(event.target.value)} className="w-full bg-[#0E1B38] border border-[#1E3560] rounded-lg p-3">
              {reports.map(item => <option key={item.id} value={item.id}>Report {item.id} | {item.job_id ? `Job ${item.job_id}` : "Resume only"} | {formatDate(item.created_at)}</option>)}
            </select>
          </label>}
        </>}
        {error && <div className="space-y-2"><p role="alert" className="text-rose-300">{error}</p><p className="text-xs text-[#8FA0BE]">Your existing profile and saved reports are unchanged. Retry the action when ready.</p><Button variant="outline" disabled={!!pending} onClick={() => setReload(value => value + 1)}>Reload career analyses</Button></div>}
        {notice && <p role="status" className="text-emerald-300 text-sm">{notice}</p>}
      </CardContent>
    </Card>
    {report && result && <>
      {report.job_id && <Card className="workspace-pearl"><CardHeader><CardTitle>Explainable compatibility</CardTitle></CardHeader><CardContent className="space-y-4">
        <p className="text-3xl font-bold text-[#FF8C38]">{scoreLabel(result.overall_score)}</p>
        <p className="text-sm text-[#8FA0BE]">{result.disclaimer}</p>
        <div className="grid sm:grid-cols-2 gap-4">{(result.categories || []).map(category => <div key={category.key} className="space-y-2 border border-[#1E3560] rounded-lg p-3">
          <h3 className="font-semibold text-sm">{category.label}</h3>
          <p className="text-sm">{category.available ? scoreLabel(category.score) : "No source evidence for this category"}</p>
          {category.available && typeof category.score === "number" && <AnimatedBar value={category.score} />}
          <p className="text-xs text-[#8FA0BE]">Weight: {category.weight.toFixed(1)}%. {category.explanation}</p>
        </div>)}</div>
        {(result.mandatory_unmet || []).length > 0 && <div className="border border-amber-700 rounded-lg p-3 text-amber-300"><h3 className="font-semibold">Mandatory requirements without matching evidence</h3><ul className="list-disc pl-5 mt-2">{result.mandatory_unmet.map(item => <li key={item}>{item}</li>)}</ul></div>}
        <details><summary className="cursor-pointer font-semibold text-sm">Requirement evidence</summary><div className="mt-3 space-y-3">{(result.requirements || []).map((item, index) => <article className="border-b border-[#1E3560] pb-3" key={`${item.category}-${index}`}>
          <p className="text-sm font-semibold">{item.requirement} {item.mandatory && <span className="text-amber-300">(mandatory)</span>}</p>
          <p className="text-xs text-[#FF8C38]">{item.status} | {item.category.replaceAll("_", " ")}</p>
          <p className="text-xs text-[#8FA0BE]">{item.evidence?.join("; ") || "No verified evidence found."}</p>
        </article>)}</div></details>
      </CardContent></Card>}
      {(result.gaps || []).length > 0 && <Card className="workspace-pearl"><CardHeader><CardTitle>Skill gaps and practical next steps</CardTitle></CardHeader><CardContent className="space-y-4">
        {result.gaps.map((gap, index) => <article key={`${gap.skill}-${index}`} className="border-b border-[#1E3560] pb-3 space-y-2">
          <h3 className="text-sm font-semibold">{gap.skill} <span className="text-xs text-amber-300">({gap.priority})</span></h3>
          <p className="text-sm text-[#8FA0BE]">{gap.reason}</p>
          <ul className="list-disc pl-5 text-sm">{gap.activities.map(activity => <li key={activity}>{activity}</li>)}</ul>
        </article>)}
        {result.gap_explanation && <p className="text-sm">{result.gap_explanation}</p>}
        <p className="text-xs text-[#8FA0BE]">Only add skills to your resume after you have learned and demonstrated them.</p>
      </CardContent></Card>}
      {result.ats && <Card className="workspace-pearl"><CardHeader><CardTitle>ATS readiness</CardTitle></CardHeader><CardContent className="space-y-4">
        <p className="text-sm">Technical parseability: <strong className="text-[#FF8C38]">{scoreLabel(result.ats.technical_score)}</strong></p>
        {result.ats.keyword_relevance !== null && <p className="text-sm">Job keyword relevance: {scoreLabel(result.ats.keyword_relevance)}</p>}
        <div className="space-y-3">{(result.ats.checks || []).map(check => <article key={check.key} className="border border-[#1E3560] p-3 rounded-lg">
          <h3 className="font-semibold text-sm">{check.label} <span className={check.status === "pass" ? "text-emerald-300" : "text-amber-300"}>({check.status})</span></h3>
          <p className="text-sm text-[#8FA0BE]">{check.detail}</p>{check.suggestion && <p className="text-sm mt-1">{check.suggestion}</p>}
        </article>)}</div>
        <p className="text-xs text-[#8FA0BE]">{result.ats.disclaimer}</p>
        {(result.ats.limitations || []).map(item => <p className="text-xs text-[#8FA0BE]" key={item}>{item}</p>)}
      </CardContent></Card>}
      <p className="text-xs text-[#8FA0BE]">Report {report.id} | Algorithm {report.algorithm_version} | Resume version {report.resume_version_id}. Saved reports describe their recorded inputs; rerun analysis after profile or job changes.</p>
    </>}
  </section>;
}

export function CareerIntelligenceSummary() {
  const available = useIntelligenceAvailability();
  const [reports, setReports] = useState<IntelligenceReport[]>([]);
  const [documents, setDocuments] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    if (!available) return;
    setLoading(true); setError("");
    Promise.all([api.getIntelligenceReports(), api.getCareerDocuments()]).then(([savedReports, savedDocuments]) => {
      if (!active) return;
      setReports(savedReports); setDocuments(savedDocuments.length);
    }).catch(cause => { if (active) setError(messageOf(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [available, reload]);
  if (!available) return null;
  return <Card className="workspace-pearl"><CardHeader><CardTitle>Saved career intelligence</CardTitle></CardHeader><CardContent className="space-y-4">
    {loading ? <p role="status">Loading career analyses...</p> : error ? <><p role="alert" className="text-rose-300">{error}</p><Button variant="outline" onClick={() => setReload(value => value + 1)}>Retry analyses</Button></> : <>
      <p className="text-sm">{reports.length} saved analyses | {documents} document versions</p>
      {!reports.length && <p className="text-sm text-[#8FA0BE]">Review your profile or select a saved job to create your first analysis.</p>}
      {reports.slice(0, 3).map(report => <Link className="block text-sm text-[#FF8C38]" key={report.id} href={report.job_id ? `/new-email?job_id=${report.job_id}` : "/profile"}>Report {report.id} | {report.job_id ? `Job ${report.job_id}` : "Resume ATS"} | {formatDate(report.created_at)}</Link>)}
    </>}
  </CardContent></Card>;
}

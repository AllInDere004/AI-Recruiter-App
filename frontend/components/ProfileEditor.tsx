"use client";

import { useEffect, useRef, useState } from "react";
import type { ParsedData } from "@/types";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { messageOf } from "@/lib/presenters";

const advancedLists = [
  ["technical_skills", "Technical skills"], ["soft_skills", "Soft skills"],
  ["certifications", "Certifications"], ["achievements", "Achievements"],
] as const;
const advancedSections = [
  { key: "projects", label: "Projects", fields: ["name", "description", "start_date", "end_date", "skills", "achievements"] },
  { key: "internships", label: "Internships", fields: ["company", "role", "description", "start_date", "end_date", "skills", "achievements"] },
  { key: "employment_history", label: "Employment history", fields: ["company", "role", "description", "start_date", "end_date", "skills", "achievements"] },
  { key: "education_details", label: "Education dates and degrees", fields: ["institution", "degree", "field_of_study", "start_date", "end_date"] },
] as const;
const lines = (value: string) => value.split("\n").map(item => item.trim()).filter(Boolean);

export function ProfileEditor({ initialData, onSave, isSaving = false }: {
  initialData: ParsedData; onSave: (data: ParsedData) => Promise<void>; isSaving?: boolean;
}) {
  const [data, setData] = useState(initialData);
  const [skill, setSkill] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const busy = useRef(false);
  useEffect(() => { setData(initialData); }, [initialData]);
  const edit = (field: keyof ParsedData, value: unknown) => {
    setData(previous => ({ ...previous, [field]: value })); setSaved(false);
  };
  const text = (value: unknown): string => Array.isArray(value) ? value.join("\n") : typeof value === "string" ? value : "";
  const editItem = (section: "experience" | "education", index: number, key: string, value: string) => {
    setData(previous => ({ ...previous, [section]: previous[section].map((item, i) => i === index ? { ...item, [key]: value } : item) }));
    setSaved(false);
  };
  const save = async () => {
    if (busy.current || isSaving) return;
    busy.current = true; setSaving(true); setError(""); setSaved(false);
    try { await onSave(data); setSaved(true); }
    catch (cause) { setError(messageOf(cause)); }
    finally { busy.current = false; setSaving(false); }
  };
  return <fieldset disabled={isSaving || saving} className="space-y-6 border-0 m-0 p-0 min-w-0">
    <Card className="workspace-pearl"><CardHeader><CardTitle>Contact and summary</CardTitle></CardHeader><CardContent className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">{([["full_name", "Full name"], ["email", "Email"], ["phone", "Phone"]] as const).map(([key, label]) => <label className="text-sm space-y-1" key={key}><span>{label}</span><Input aria-label={label} value={data[key] || ""} onChange={event => edit(key, event.target.value || null)} /></label>)}</div>
      <label className="block text-sm space-y-1"><span>Summary</span><textarea aria-label="Summary" className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-3" rows={4} value={data.summary || ""} onChange={event => edit("summary", event.target.value || null)} /></label>
    </CardContent></Card>
    <Card className="workspace-pearl"><CardHeader><CardTitle>Skills</CardTitle></CardHeader><CardContent className="space-y-3">
      <form className="flex gap-2" onSubmit={event => { event.preventDefault(); if (skill.trim() && !data.skills.includes(skill.trim())) edit("skills", [...data.skills, skill.trim()]); setSkill(""); }}><Input aria-label="New skill" placeholder="Add a skill" value={skill} onChange={event => setSkill(event.target.value)} /><Button type="submit">Add Skill</Button></form>
      <div className="flex flex-wrap gap-2">{data.skills.map((value, index) => <button type="button" key={`${value}-${index}`} title={`Remove ${value}`} className="px-3 py-1 border border-[#FF6A3D]/40 rounded-full text-sm" onClick={() => edit("skills", data.skills.filter((_, i) => i !== index))}>{value} <span aria-hidden="true">x</span></button>)}</div>
    </CardContent></Card>
    {(["experience", "education"] as const).map(section => <Card className="workspace-pearl" key={section}><CardHeader><CardTitle className="capitalize">{section}</CardTitle></CardHeader><CardContent className="space-y-4">
      {data[section].map((item, index) => <div key={index} className="border border-[#1E3560] rounded-lg p-4 space-y-3"><div className="grid sm:grid-cols-2 gap-3">{(section === "experience" ? ["company", "role", "duration", "description"] : ["institution", "degree", "field_of_study", "graduation_year"]).map(key => <label key={key} className="block text-xs capitalize space-y-1"><span>{key.replaceAll("_", " ")}</span><Input aria-label={`${section} ${index + 1} ${key}`} value={text(item[key])} onChange={event => editItem(section, index, key, event.target.value)} /></label>)}</div><Button type="button" size="sm" variant="outline" onClick={() => edit(section, data[section].filter((_, i) => i !== index))}>Remove entry</Button></div>)}
      <Button type="button" variant="outline" onClick={() => edit(section, [...data[section], {}])}>Add {section === "experience" ? "experience" : "education"}</Button>
    </CardContent></Card>)}
    <details className="space-y-4">
      <summary className="cursor-pointer font-semibold">Advanced resume details and source evidence</summary>
      <p className="text-xs text-[#8FA0BE] mt-3">Review optional details against your original resume. Only enter qualifications you possess. User edits do not independently verify a claim.</p>
      <Card className="workspace-pearl mt-4"><CardHeader><CardTitle>Skills, certifications, and achievements</CardTitle></CardHeader><CardContent className="grid sm:grid-cols-2 gap-4">
        {advancedLists.map(([key, label]) => <label key={key} className="text-sm space-y-1"><span>{label} (one per line)</span><textarea aria-label={label} rows={4} value={text(data[key])} onChange={event => edit(key, lines(event.target.value))} className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-3" /></label>)}
      </CardContent></Card>
      {advancedSections.map(section => {
        const entries = (data[section.key] || []) as unknown as Record<string, unknown>[];
        const empty = Object.fromEntries(section.fields.map(key => [key, key === "skills" || key === "achievements" ? [] : null]));
        return <Card className="workspace-pearl mt-4" key={section.key}><CardHeader><CardTitle>{section.label}</CardTitle></CardHeader><CardContent className="space-y-4">
          {entries.map((item, index) => <div className="border border-[#1E3560] rounded-lg p-4 space-y-3" key={index}><div className="grid sm:grid-cols-2 gap-3">
            {section.fields.map(key => <label key={key} className="text-xs space-y-1"><span className="capitalize">{key.replaceAll("_", " ")}{key === "skills" || key === "achievements" ? " (one per line)" : ""}</span>
              <textarea rows={key === "description" ? 3 : 2} aria-label={`${section.key} ${index + 1} ${key}`} value={text(item[key])} onChange={event => edit(section.key, entries.map((value, position) => position === index ? { ...value, [key]: key === "skills" || key === "achievements" ? lines(event.target.value) : event.target.value || null } : value))} className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-2" />
            </label>)}
          </div><Button variant="outline" size="sm" onClick={() => edit(section.key, entries.filter((_, position) => position !== index))}>Remove {section.label.toLowerCase()} entry</Button></div>)}
          <Button variant="outline" onClick={() => edit(section.key, [...entries, empty])}>Add {section.label.toLowerCase()} entry</Button>
        </CardContent></Card>;
      })}
      <Card className="workspace-pearl mt-4"><CardHeader><CardTitle>Extracted source evidence</CardTitle></CardHeader><CardContent className="space-y-4">
        {data.uncertain_fields?.length ? <p className="text-sm text-amber-300">Needs review: {data.uncertain_fields.join(", ")}</p> : null}
        {data.evidence?.length ? data.evidence.map((item, index) => <article key={index} className="border-b border-[#1E3560] pb-3 space-y-1">
          <p className="text-sm font-semibold">{item.field}: {item.value}</p>
          <blockquote className="text-sm text-[#8FA0BE]">{item.quote}</blockquote>
          <p className="text-xs text-[#8FA0BE]">{item.status === "verified" ? "Source text found" : "Uncertain source evidence"}{typeof item.confidence === "number" ? ` | Extraction confidence ${Math.round(item.confidence * 100)}%` : ""}</p>
        </article>) : <p className="text-sm text-[#8FA0BE]">No structured evidence was recorded for this extraction. Existing resume details remain editable.</p>}
        <p className="text-xs text-[#8FA0BE]">Evidence refers to the uploaded source. The backend rechecks claims; a confidence value is not proof of a qualification.</p>
      </CardContent></Card>
    </details>
    <p className="text-xs text-[#8FA0BE]">Review extracted details before saving. Email generation uses your uploaded resume as its factual source.</p>
    {error && <p role="alert" className="text-rose-300">{error}</p>}{saved && <p role="status" className="text-emerald-300">Profile saved.</p>}
    <Button onClick={save} isLoading={isSaving || saving}>Save Profile</Button>
  </fieldset>;
}

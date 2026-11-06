"use client";
import { useEffect, useState } from "react";
import type { ParsedData } from "@/types";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { messageOf } from "@/lib/presenters";

export function ProfileEditor({ initialData, onSave, isSaving = false }: { initialData: ParsedData; onSave: (data: ParsedData) => Promise<void>; isSaving?: boolean }) {
  const [data, setData] = useState(initialData);
  const [skill, setSkill] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => { setData(initialData); }, [initialData]);
  const edit = (field: keyof ParsedData, value: unknown) => { setData(previous => ({ ...previous, [field]: value })); setSaved(false); };
  const text = (value: unknown): string => Array.isArray(value) ? value.join("\n") : typeof value === "string" ? value : "";
  const editItem = (section: "experience" | "education", index: number, key: string, value: string) => {
    setData(previous => ({ ...previous, [section]: previous[section].map((item, i) => i === index ? { ...item, [key]: value } : item) })); setSaved(false);
  };
  const save = async () => { setError(""); setSaved(false); try { await onSave(data); setSaved(true); } catch (cause) { setError(messageOf(cause)); } };
  return <div className="space-y-6">
    <Card className="workspace-pearl"><CardHeader><CardTitle>Contact and summary</CardTitle></CardHeader><CardContent className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">{([['full_name','Full name'],['email','Email'],['phone','Phone']] as const).map(([key,label]) => <label className="text-sm space-y-1" key={key}><span>{label}</span><Input aria-label={label} value={data[key] || ""} onChange={event => edit(key,event.target.value || null)} /></label>)}</div>
      <label className="block text-sm space-y-1"><span>Summary</span><textarea aria-label="Summary" className="w-full rounded-lg bg-[#0E1B38] border border-[#1E3560] p-3" rows={4} value={data.summary || ""} onChange={event => edit("summary",event.target.value || null)} /></label>
    </CardContent></Card>
    <Card className="workspace-pearl"><CardHeader><CardTitle>Skills</CardTitle></CardHeader><CardContent className="space-y-3">
      <form className="flex gap-2" onSubmit={event => { event.preventDefault(); if (skill.trim() && !data.skills.includes(skill.trim())) edit("skills",[...data.skills,skill.trim()]); setSkill(""); }}><Input aria-label="New skill" placeholder="Add a skill" value={skill} onChange={event => setSkill(event.target.value)} /><Button type="submit">Add Skill</Button></form>
      <div className="flex flex-wrap gap-2">{data.skills.map((value,index) => <button type="button" key={`${value}-${index}`} title={`Remove ${value}`} className="px-3 py-1 border border-[#FF6A3D]/40 rounded-full text-sm" onClick={() => edit("skills",data.skills.filter((_,i) => i !== index))}>{value} <span aria-hidden="true">x</span></button>)}</div>
    </CardContent></Card>
    {(["experience","education"] as const).map(section => <Card className="workspace-pearl" key={section}><CardHeader><CardTitle className="capitalize">{section}</CardTitle></CardHeader><CardContent className="space-y-4">
      {data[section].map((item,index) => <div key={index} className="border border-[#1E3560] rounded-lg p-4 space-y-3"><div className="grid sm:grid-cols-2 gap-3">{(section === "experience" ? ["company","role","duration","description"] : ["institution","degree","field_of_study","graduation_year"]).map(key => <label key={key} className="block text-xs capitalize space-y-1"><span>{key.replaceAll("_"," ")}</span><Input aria-label={`${section} ${index+1} ${key}`} value={text(item[key])} onChange={event => editItem(section,index,key,event.target.value)} /></label>)}</div><Button type="button" size="sm" variant="outline" onClick={() => edit(section,data[section].filter((_,i) => i !== index))}>Remove entry</Button></div>)}
      <Button type="button" variant="outline" onClick={() => edit(section,[...data[section],{}])}>Add {section === "experience" ? "experience" : "education"}</Button>
    </CardContent></Card>)}
    <p className="text-xs text-[#8FA0BE]">Review extracted details before saving. Email generation uses your uploaded resume as its factual source.</p>
    {error && <p role="alert" className="text-rose-300">{error}</p>}{saved && <p role="status" className="text-emerald-300">Profile saved.</p>}
    <Button onClick={save} isLoading={isSaving}>Save Profile</Button>
  </div>;
}

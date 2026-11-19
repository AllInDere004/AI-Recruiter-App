"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { ParsedData, Profile } from "@/types";
import { api, ApiError, getToken } from "@/lib/api";
import { parsedProfile, messageOf } from "@/lib/presenters";
import { ResumeUpload } from "@/components/ResumeUpload";
import { ProfileEditor } from "@/components/ProfileEditor";
export default function OnboardingPage() {
  const router = useRouter(); const [profile,setProfile] = useState<Profile | null>(null); const [loading,setLoading] = useState(true); const [saving,setSaving] = useState(false); const [error,setError] = useState("");
  useEffect(() => { let active = true; async function load() {
    if (!getToken()) { router.replace("/login"); return; }
    try { await api.getMe(); const saved = await api.getProfile(); if (active) setProfile(saved); }
    catch (cause) { if (cause instanceof ApiError && cause.status === 401) router.replace("/login"); else if (!(cause instanceof ApiError && cause.status === 404) && active) setError(messageOf(cause)); }
    finally { if (active) setLoading(false); }
  } void load(); return () => { active = false; }; }, [router]);
  const parsed = useMemo(() => profile ? parsedProfile(profile) : null,[profile]);
  const save = async (data: ParsedData) => { if (!profile) return; setSaving(true); try { const updated = await api.updateProfile({ full_name:data.full_name,parsed_data:{ ...profile.parsed_data,...data } }); setProfile(updated); router.push("/dashboard"); } finally { setSaving(false); } };
  return <main className="min-h-screen bg-[#0A1128] text-[#F1F5F9] px-4 py-12"><div className="max-w-4xl mx-auto space-y-6"><h1 className="text-3xl font-bold">{profile ? "Review your profile" : "Upload your resume"}</h1><p className="text-sm text-[#8FA0BE]">Upload a text-based PDF, then review the extracted information.</p>{error && <p role="alert" className="text-rose-300">{error}</p>}{loading ? <p role="status">Loading your profile...</p> : <><ResumeUpload onParsed={setProfile} />{profile && <ProfileEditor initialData={parsed!} onSave={save} isSaving={saving} />}</>}</div></main>;
}

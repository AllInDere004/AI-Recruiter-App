"use client";
import { useEffect, useMemo, useState } from "react";
import type { Profile, ParsedData } from "@/types";
import { api, ApiError } from "@/lib/api";
import { parsedProfile, messageOf } from "@/lib/presenters";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ResumeUpload } from "@/components/ResumeUpload";
import { ProfileEditor } from "@/components/ProfileEditor";
export default function ProfilePage() {
  const [profile,setProfile] = useState<Profile | null>(null); const [loading,setLoading] = useState(true); const [saving,setSaving] = useState(false); const [error,setError] = useState("");
  useEffect(() => { let active = true; api.getProfile().then(data => { if (active) setProfile(data); }).catch(cause => { if (active && !(cause instanceof ApiError && cause.status === 404)) setError(messageOf(cause)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  const parsed = useMemo(() => profile ? parsedProfile(profile) : null,[profile]);
  const save = async (data: ParsedData) => { if (!profile) return; setSaving(true); try { setProfile(await api.updateProfile({ full_name:data.full_name,parsed_data:{ ...profile.parsed_data,...data } })); } finally { setSaving(false); } };
  return <WorkspaceShell section="Your Profile"><main className="workspace-main p-4 sm:p-8 space-y-6 max-w-5xl mx-auto"><h1 className="text-3xl font-bold">Your profile</h1>{error && <p role="alert" className="text-rose-300">{error}</p>}{loading ? <p role="status">Loading...</p> : <><ResumeUpload onParsed={setProfile} />{profile ? <ProfileEditor initialData={parsed!} onSave={save} isSaving={saving} /> : <p>Upload your resume to create your profile.</p>}</>}</main></WorkspaceShell>;
}

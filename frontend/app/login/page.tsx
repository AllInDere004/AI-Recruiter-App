"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { api, ApiError } from "@/lib/api";
import { messageOf } from "@/lib/presenters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
export default function LoginPage() {
  const { login } = useAuth(); const router = useRouter(); const [email,setEmail] = useState(""); const [password,setPassword] = useState(""); const [busy,setBusy] = useState(false); const [error,setError] = useState(""); const [registered,setRegistered] = useState(false);
  useEffect(() => { const params = new URLSearchParams(window.location.search); setEmail(params.get("email") || ""); setRegistered(params.get("registered") === "1"); }, []);
  return <main className="min-h-screen grid place-items-center bg-[#0A1128] px-4"><form className="w-full max-w-md space-y-5 bg-[#101C38] border border-[#1E3560] rounded-2xl p-8" onSubmit={async event => { event.preventDefault(); setBusy(true); setError(""); try { await login(email.trim(),password); try { await api.getProfile(); router.replace("/dashboard"); } catch (cause) { if (cause instanceof ApiError && cause.status === 404) router.replace("/onboarding"); else throw cause; } } catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); } }}><Link href="/" className="text-[#FF8C38]">AI Recruiter</Link><h1 className="text-3xl font-bold">Welcome back</h1>{registered && <p role="status" className="text-emerald-300">Account created. Sign in to continue.</p>}<label className="block space-y-1"><span>Email</span><Input id="email" name="email" type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} /></label><label className="block space-y-1"><span>Password</span><Input id="password" name="password" type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} /></label>{error && <p role="alert" className="text-rose-300">{error}</p>}<Button type="submit" isLoading={busy}>Sign in</Button><p className="text-sm">New here? <Link href="/signup" className="text-[#FF8C38]">Create an account</Link></p></form></main>;
}

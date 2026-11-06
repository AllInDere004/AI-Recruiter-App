"use client";
import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { messageOf } from "@/lib/presenters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
export default function SignupPage() {
  const { signup } = useAuth(); const [email,setEmail] = useState(""); const [password,setPassword] = useState(""); const [busy,setBusy] = useState(false); const [error,setError] = useState("");
  return <main className="min-h-screen grid place-items-center bg-[#0A1128] px-4"><form className="w-full max-w-md space-y-5 bg-[#101C38] border border-[#1E3560] rounded-2xl p-8" onSubmit={async event => { event.preventDefault(); setError(""); setBusy(true); try { await signup(email.trim(),password); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); } }}><Link href="/" className="text-[#FF8C38]">AI Recruiter</Link><h1 className="text-3xl font-bold">Create an account</h1><label className="block space-y-1"><span>Email</span><Input id="email" name="email" type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} /></label><label className="block space-y-1"><span>Password</span><Input id="new-password" name="password" type="password" autoComplete="new-password" required minLength={6} value={password} onChange={event => setPassword(event.target.value)} /></label>{error && <p role="alert" className="text-rose-300">{error}</p>}<Button type="submit" isLoading={busy}>Create account</Button><p className="text-sm">Already registered? <Link href="/login" className="text-[#FF8C38]">Sign in</Link></p></form></main>;
}
